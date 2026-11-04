"""QQ 登录（QQ 互联 OAuth2.0）。

腾讯那三个接口的返回格式**各不相同且都不是标准 JSON**，这是这条链路最容易
翻车的地方，所以下面用真实的返回样例来测解析：
  · /oauth2.0/token     → URL 编码串   access_token=xxx&expires_in=7776000
  · /oauth2.0/me        → JSONP 包壳   callback( {"openid":"..."} );
  · /user/get_user_info → 纯 JSON      {"ret":0,"nickname":"..."}
照 response.json() 一把梭的话，前两个会直接抛异常。
"""

import pytest

from app.config import settings
from app.models import User, UserIdentity
from app.services import qq_auth_service as qq


@pytest.fixture(autouse=True)
def _configured(monkeypatch):
    monkeypatch.setattr(settings, "auth_enabled", True)
    monkeypatch.setattr(settings, "qq_app_id", "101234567")
    monkeypatch.setattr(settings, "qq_app_key", "test-app-key")
    monkeypatch.setattr(settings, "qq_redirect_uri", "https://example.com/api/auth/qq/callback")


@pytest.fixture(autouse=True)
def _clean(db):
    yield
    db.query(UserIdentity).delete()
    db.query(User).filter(User.email.like("qq-%@qq.local")).delete(synchronize_session=False)
    db.commit()


def _authorize(client) -> str:
    """走一遍 /authorize：返回 state，同时让 TestClient 存下那枚 nonce Cookie。

    回调不能再凭空造一个 state 了——它必须与**发起授权的这个浏览器**配对
    （见 qq_auth_service 里 state 那一段），所以测试也必须从这一步开始走，
    这本身就是对"链路完整"的检查。
    """
    from urllib.parse import parse_qs, urlparse

    r = client.get("/api/auth/qq/authorize", follow_redirects=False)
    assert r.status_code == 302, r.text
    assert client.cookies.get(qq.STATE_COOKIE_NAME), "授权跳转必须种下 state nonce Cookie"
    return parse_qs(urlparse(r.headers["location"]).query)["state"][0]


class TestResponseParsing:
    """三种返回格式各测一遍——最容易被「按 JSON 一把梭」写错的地方。"""

    def test_token_response_is_urlencoded_not_json(self, monkeypatch):
        class FakeResp:
            text = "access_token=ABC123&expires_in=7776000&refresh_token=XYZ"

        monkeypatch.setattr(qq.httpx, "get", lambda *a, **k: FakeResp())
        assert qq.exchange_code_for_token("code-1") == "ABC123"

    def test_token_error_is_also_urlencoded(self, monkeypatch):
        """失败时腾讯同样返回 URL 编码。错误原因必须带到异常里，
        否则用户只会看到一句无差别的登录失败。"""
        class FakeResp:
            text = "code=100010&msg=redirect uri is illegal"

        monkeypatch.setattr(qq.httpx, "get", lambda *a, **k: FakeResp())
        with pytest.raises(qq.QQAuthError) as exc:
            qq.exchange_code_for_token("code-1")
        assert "100010" in str(exc.value)

    def test_openid_response_is_jsonp_wrapped(self, monkeypatch):
        class FakeResp:
            text = 'callback( {"client_id":"101234567","openid":"OPENID-ABC"} );'

        monkeypatch.setattr(qq.httpx, "get", lambda *a, **k: FakeResp())
        assert qq.fetch_openid("tok") == "OPENID-ABC"

    def test_openid_garbage_response_raises_not_silently_none(self, monkeypatch):
        """上游挂了返回一坨 HTML 时必须抛错。悄悄返回 None 的话，
        调用方会拿着空 openid 去建号，后果是所有人共用一个账号。"""
        class FakeResp:
            text = "<html>502 Bad Gateway</html>"

        monkeypatch.setattr(qq.httpx, "get", lambda *a, **k: FakeResp())
        with pytest.raises(qq.QQAuthError):
            qq.fetch_openid("tok")

    def test_nickname_failure_does_not_block_login(self, monkeypatch):
        """昵称只是显示名，取不到不该把人挡在登录之外。"""
        def boom(*a, **k):
            raise qq.httpx.HTTPError("network down")

        monkeypatch.setattr(qq.httpx, "get", boom)
        assert qq.fetch_nickname("tok", "openid") is None


class TestState:
    def test_state_roundtrip(self):
        state, nonce = qq.issue_state()
        assert qq.verify_state(state, nonce) is True

    def test_rejects_forged_and_empty_state(self):
        _, nonce = qq.issue_state()
        assert qq.verify_state("", nonce) is False
        assert qq.verify_state("not-a-token", nonce) is False

    def test_rejects_a_normal_session_token_as_state(self):
        """会话 JWT 与 state 用同一个密钥签。不校验 subject 前缀的话，
        任何登录用户的 token 都能拿来当 state 用，CSRF 防护形同虚设。"""
        from app.core.security import create_token

        _, nonce = qq.issue_state()
        session_like = create_token("some-user-id", settings.jwt_secret, 600)
        assert qq.verify_state(session_like, nonce) is False

    def test_state_without_the_browser_nonce_is_rejected(self):
        """state 必须与发起授权的那个浏览器绑定。

        少了这一条，一个只验签名的 state 挡不住登录态固定：攻击者用自己的
        QQ 号走完授权、截下自己的 code，把回调链接发给受害者，受害者的浏览器
        一兑换就登进了**攻击者的账号**，之后上传的材料攻击者全能看到。
        """
        state, _ = qq.issue_state()
        assert qq.verify_state(state, "") is False
        assert qq.verify_state(state, None) is False

    def test_state_with_another_browsers_nonce_is_rejected(self):
        """A 浏览器的 state 配 B 浏览器的 Cookie —— 正是攻击者手里那种组合。"""
        state_a, _ = qq.issue_state()
        _, nonce_b = qq.issue_state()
        assert qq.verify_state(state_a, nonce_b) is False

    def test_state_does_not_carry_the_nonce_in_clear(self):
        """state 会经过腾讯、进浏览器历史和访问日志；里面只能放 nonce 的摘要，
        放原文等于把绑定用的那半边秘密一起公开了。"""
        state, nonce = qq.issue_state()
        assert nonce not in state


class TestAuthorizeUrl:
    def test_contains_exact_redirect_uri(self):
        """redirect_uri 必须与后台登记的逐字符一致，否则腾讯报 100010。
        这条确认我们没有对它做任何「顺手规范化」。"""
        from urllib.parse import parse_qs, urlparse

        url = qq.build_authorize_url("state-1")
        assert "response_type=code" in url
        assert "client_id=101234567" in url
        q = parse_qs(urlparse(url).query)
        assert q["redirect_uri"][0] == settings.qq_redirect_uri

    def test_disabled_when_not_configured(self, monkeypatch):
        monkeypatch.setattr(settings, "qq_app_key", "")
        assert settings.qq_login_enabled is False
        with pytest.raises(qq.QQAuthError):
            qq.build_authorize_url("s")


class TestAccountLinking:
    def test_first_login_creates_account_with_placeholder_email(self, db):
        user, created = qq.find_or_create_user(db, "OPENID-1", "小明")
        assert created is True
        # QQ 拿不到邮箱 → 合成占位邮箱 + 标记成「还没有能收信的真邮箱」，
        # 让报告页的绑定横幅出现（与 CDK 游客同一条转正路径）
        assert user.email == "qq-OPENID-1@qq.local"
        assert user.is_guest is True
        assert user.display_name == "小明"

    def test_second_login_reuses_same_account(self, db):
        first, _ = qq.find_or_create_user(db, "OPENID-2", "小明")
        second, created = qq.find_or_create_user(db, "OPENID-2", "改名了")
        assert created is False
        assert second.id == first.id, "同一个 QQ 号第二次登录必须回到同一个账号"

    def test_different_openid_gets_different_account(self, db):
        a, _ = qq.find_or_create_user(db, "OPENID-A", None)
        b, _ = qq.find_or_create_user(db, "OPENID-B", None)
        assert a.id != b.id

    def test_orphan_identity_is_recovered_not_dead_ended(self, db):
        """账号被删但映射没删时，这个 QQ 号必须还能登录，
        而不是永远撞在一条指向空账号的映射上。"""
        user, _ = qq.find_or_create_user(db, "OPENID-ORPHAN", None)
        db.query(User).filter(User.id == user.id).delete()
        db.commit()

        again, created = qq.find_or_create_user(db, "OPENID-ORPHAN", None)
        assert created is True
        assert again.id != user.id


class TestConcurrentFirstLogin:
    """同一个 QQ 号在两个标签页同时首次登录。

    两个请求都查不到映射、都去建号，第二个撞上 users.email 或
    (provider, provider_uid) 的唯一约束。不处理就是 500 —— 而用户什么也没做错，
    正确结果是"回到已经被另一个请求建好的那个账号"。
    回调这条路还有一条额外要求：**必须保持 302 重定向契约**，
    不能甩一坨 JSON 错误给浏览器直出（用户看到的是机器文本，不知道该干什么）。
    """

    def _competitor(self, openid):
        """在 find_or_create_user 建号的中途，抢先把同一个 openid 的账号建出来。
        注入点选 hash_password：它在 User(...) 构造时被调用，正好夹在
        "查不到映射"和"commit"之间。"""
        from app.core.security import hash_password as _real

        def _inject(secret):
            from app.db import session_scope

            other = session_scope()
            try:
                if (
                    other.query(UserIdentity)
                    .filter(UserIdentity.provider == "qq", UserIdentity.provider_uid == openid)
                    .first()
                    is None
                ):
                    winner = User(
                        email=f"qq-{openid}@qq.local", password_hash="x", is_guest=True
                    )
                    other.add(winner)
                    other.flush()
                    other.add(
                        UserIdentity(user_id=winner.id, provider="qq", provider_uid=openid)
                    )
                    other.commit()
            finally:
                other.close()
            return _real(secret)

        return _inject

    def test_service_returns_the_row_that_won_instead_of_500(self, db, monkeypatch):
        monkeypatch.setattr(qq, "hash_password", self._competitor("OPENID-RACE"))

        user, created = qq.find_or_create_user(db, "OPENID-RACE", "小明")
        assert created is False, "抢输的那个请求应该回到已存在的账号，而不是再建一个"
        assert user.email == "qq-OPENID-RACE@qq.local"
        assert (
            db.query(UserIdentity).filter(UserIdentity.provider_uid == "OPENID-RACE").count() == 1
        )

    def test_callback_keeps_the_redirect_contract_on_a_race(self, client, monkeypatch):
        monkeypatch.setattr(qq, "exchange_code_for_token", lambda code: "tok")
        monkeypatch.setattr(qq, "fetch_openid", lambda tok: "OPENID-RACE-HTTP")
        monkeypatch.setattr(qq, "fetch_nickname", lambda tok, oid: None)
        monkeypatch.setattr(qq, "hash_password", self._competitor("OPENID-RACE-HTTP"))

        state = _authorize(client)
        r = client.get("/api/auth/qq/callback?code=abc&state=" + state, follow_redirects=False)
        assert r.status_code == 302, f"并发首次登录把回调打成了 {r.status_code}"
        assert "/auth/qq?code=" in r.headers["location"], (
            f"抢输的请求没能登录成功：{r.headers['location']}"
        )


class TestLoginProviderLabel:
    """/auth/me 的 login_provider 字段——前端据此在昵称旁贴"QQ 登录"/
    "邮箱登录"徽标。三种账号状态各测一遍，这是最容易顾此失彼的地方。"""

    def test_qq_account_reports_qq_provider(self, client, db, monkeypatch):
        monkeypatch.setattr(qq, "exchange_code_for_token", lambda code: "tok")
        monkeypatch.setattr(qq, "fetch_openid", lambda tok: "OPENID-LABEL")
        monkeypatch.setattr(qq, "fetch_nickname", lambda tok, oid: "小明")

        state = _authorize(client)
        r = client.get("/api/auth/qq/callback?code=abc&state=" + state, follow_redirects=False)
        handoff = r.headers["location"].split("code=", 1)[1]
        token = client.post("/api/auth/qq/exchange", json={"code": handoff}).json()["token"]

        me = client.get("/api/auth/me", headers={"Authorization": "Bearer " + token}).json()
        assert me["login_provider"] == "qq"
        assert me["display_name"] == "小明"

    def test_qq_account_does_not_leak_the_openid_as_email(self, client, db, monkeypatch):
        """/auth/me 不能把合成邮箱 qq-{openid}@qq.local 回给浏览器。

        openid 是 appid 维度的**稳定第三方标识符**，一旦落进前端状态、
        浏览器存储、日志或第三方埋点就收不回来了；而它对界面毫无用处
        （界面显示的是 display_name）。返回 null 而不是删掉这个键——
        前端拿 email 做昵称的兜底显示，少一个键和值为 null 是两种东西。
        """
        monkeypatch.setattr(qq, "exchange_code_for_token", lambda code: "tok")
        monkeypatch.setattr(qq, "fetch_openid", lambda tok: "OPENID-SECRET-123")
        monkeypatch.setattr(qq, "fetch_nickname", lambda tok, oid: "小明")

        state = _authorize(client)
        r = client.get("/api/auth/qq/callback?code=abc&state=" + state, follow_redirects=False)
        handoff = r.headers["location"].split("code=", 1)[1]
        token = client.post("/api/auth/qq/exchange", json={"code": handoff}).json()["token"]

        me = client.get("/api/auth/me", headers={"Authorization": "Bearer " + token}).json()
        assert "OPENID-SECRET-123" not in str(me), f"openid 泄露给了前端：{me}"
        assert me["email"] is None
        assert "email" in me

    def test_registered_account_reports_email_provider(self, client):
        client.post(
            "/api/auth/register",
            json={"email": "provider-check@example.com", "password": "password123"},
        )
        token = client.post(
            "/api/auth/login",
            json={"email": "provider-check@example.com", "password": "password123"},
        ).json()["token"]
        me = client.get("/api/auth/me", headers={"Authorization": "Bearer " + token}).json()
        assert me["login_provider"] == "email"

    def test_unbound_guest_reports_no_provider(self, client, db):
        """CDK/首次匿名评审铸造的游客——没有第三方映射也没有真邮箱，
        不该被贴上"邮箱登录"（那是在撒谎）。"""
        from app.services import guest_service

        user_id, token = guest_service.mint_guest(db)
        me = client.get("/api/auth/me", headers={"Authorization": "Bearer " + token}).json()
        assert me["login_provider"] is None


class TestEndpoints:
    def test_authorize_redirects_to_tencent(self, client):
        r = client.get("/api/auth/qq/authorize", follow_redirects=False)
        assert r.status_code == 302
        assert r.headers["location"].startswith("https://graph.qq.com/oauth2.0/authorize")

    def test_authorize_refused_when_not_configured(self, client, monkeypatch):
        monkeypatch.setattr(settings, "qq_app_id", "")
        r = client.get("/api/auth/qq/authorize", follow_redirects=False)
        assert r.status_code == 400

    def test_callback_with_bad_state_redirects_to_login_with_reason(self, client):
        """state 校验必须发生在用 code 之前——这是防 CSRF 的全部意义。
        失败时 302 回登录页并带上原因，而不是甩一坨 JSON 给浏览器直出。"""
        r = client.get("/api/auth/qq/callback?code=x&state=forged", follow_redirects=False)
        assert r.status_code == 302
        assert "/login?qq_error=" in r.headers["location"]

    def test_full_callback_then_exchange_yields_working_session(self, client, db, monkeypatch):
        """完整链路：回调 → 一次性交接码 → 换 JWT → 该 JWT 真的能认身份。"""
        monkeypatch.setattr(qq, "exchange_code_for_token", lambda code: "tok")
        monkeypatch.setattr(qq, "fetch_openid", lambda tok: "OPENID-E2E")
        monkeypatch.setattr(qq, "fetch_nickname", lambda tok, oid: "端到端")

        state = _authorize(client)
        r = client.get("/api/auth/qq/callback?code=abc&state=" + state, follow_redirects=False)
        assert r.status_code == 302
        location = r.headers["location"]
        assert "/auth/qq?code=" in location
        handoff = location.split("code=", 1)[1]

        ex = client.post("/api/auth/qq/exchange", json={"code": handoff})
        assert ex.status_code == 200, ex.text
        token = ex.json()["token"]

        me = client.get("/api/auth/me", headers={"Authorization": "Bearer " + token})
        assert me.status_code == 200
        assert me.json()["is_anonymous"] is False

    def test_handoff_code_is_single_use(self, client, db, monkeypatch):
        """交接码用一次即废——它出现在 URL 里，可能被浏览器历史/中间层日志留存。
        这正是不把长效 JWT 直接拼进重定向地址的原因。"""
        monkeypatch.setattr(qq, "exchange_code_for_token", lambda code: "tok")
        monkeypatch.setattr(qq, "fetch_openid", lambda tok: "OPENID-ONCE")
        monkeypatch.setattr(qq, "fetch_nickname", lambda tok, oid: None)

        state = _authorize(client)
        r = client.get("/api/auth/qq/callback?code=abc&state=" + state, follow_redirects=False)
        handoff = r.headers["location"].split("code=", 1)[1]

        assert client.post("/api/auth/qq/exchange", json={"code": handoff}).status_code == 200
        assert client.post("/api/auth/qq/exchange", json={"code": handoff}).status_code == 401


class TestCallbackIsBoundToTheBrowser:
    """回调必须证明"完成授权的浏览器 = 发起授权的那个浏览器"。

    不做这件事时的真实攻击：攻击者用自己的 QQ 号走完授权、截下自己的 code 和
    state（回调是 GET，地址栏里就有），把 .../callback?code=…&state=… 发给受害者。
    受害者的浏览器一打开就完成兑换，从此**以攻击者的身份**在用这个站，
    他之后上传的每一份材料、每一条评审，攻击者登进自己账号都能读到。
    """

    @pytest.fixture(autouse=True)
    def _stub_tencent(self, monkeypatch):
        monkeypatch.setattr(qq, "exchange_code_for_token", lambda code: "tok")
        monkeypatch.setattr(qq, "fetch_openid", lambda tok: "OPENID-BIND")
        monkeypatch.setattr(qq, "fetch_nickname", lambda tok, oid: None)

    def test_callback_without_the_cookie_is_refused(self, client):
        """这就是"攻击者构造的链接在受害者浏览器里打开"的形状：
        state 是真的（攻击者从我们这里领的），Cookie 不是他的。"""
        state = _authorize(client)
        client.cookies.delete(qq.STATE_COOKIE_NAME)

        r = client.get("/api/auth/qq/callback?code=abc&state=" + state, follow_redirects=False)
        assert r.status_code == 302
        assert "/login?qq_error=" in r.headers["location"]
        assert "/auth/qq?code=" not in r.headers["location"], "没有 Cookie 也发出了交接码"

    def test_callback_with_a_mismatched_cookie_is_refused(self, client):
        state = _authorize(client)
        # 先删再设：只 set 会在 jar 里留下两个同名 cookie（服务端设的那个带 domain，
        # 这里设的不带），哪个被优先读取取决于 HTTP 客户端（httpx 与 httpx2 不同），
        # 测试就成了碰运气。真实浏览器里同名同域同路径只有一个，这里也只留一个。
        client.cookies.delete(qq.STATE_COOKIE_NAME)
        client.cookies.set(qq.STATE_COOKIE_NAME, "some-other-browsers-nonce")

        r = client.get("/api/auth/qq/callback?code=abc&state=" + state, follow_redirects=False)
        assert "/login?qq_error=" in r.headers["location"]

    def test_state_cannot_be_replayed_after_a_successful_callback(self, client):
        """成功一次之后 Cookie 被清掉 —— 同一个 state 第二次回调必然失败。
        这就是这套设计里的"用一次即废"：销毁绑定用的那半边秘密。"""
        state = _authorize(client)
        first = client.get("/api/auth/qq/callback?code=abc&state=" + state, follow_redirects=False)
        assert "/auth/qq?code=" in first.headers["location"]
        assert not client.cookies.get(qq.STATE_COOKIE_NAME), "回调之后必须清掉 state Cookie"

        again = client.get("/api/auth/qq/callback?code=abc&state=" + state, follow_redirects=False)
        assert "/login?qq_error=" in again.headers["location"]

    def test_failed_callback_also_clears_the_cookie(self, client, monkeypatch):
        """失败也要清：只在成功分支清等于给失败后的重放留了一个窗口。"""
        def boom(code):
            raise qq.QQAuthError("腾讯那边挂了")

        monkeypatch.setattr(qq, "exchange_code_for_token", boom)
        state = _authorize(client)
        client.get("/api/auth/qq/callback?code=abc&state=" + state, follow_redirects=False)
        assert not client.cookies.get(qq.STATE_COOKIE_NAME)

    def test_state_cookie_is_httponly_and_lax(self, client):
        """HttpOnly：XSS 也偷不走这半边秘密。
        SameSite=Lax（不是 Strict）：腾讯 302 过来的是跨站顶层导航，
        Strict 时浏览器不带 Cookie，整条登录链会当场断掉。"""
        r = client.get("/api/auth/qq/authorize", follow_redirects=False)
        raw = r.headers["set-cookie"].lower()
        assert qq.STATE_COOKIE_NAME.lower() in raw
        assert "httponly" in raw
        assert "samesite=lax" in raw
        assert "path=/" in raw


class TestCallbackDoesNotBlockTheEventLoop:
    def test_tencent_calls_run_off_the_event_loop(self, client, monkeypatch):
        """三次腾讯调用是同步 httpx（各 10 秒超时），必须跑在线程池里。

        跑在事件循环里的后果不是"这一个请求慢"：DEPLOY-BAREMETAL 规定单
        uvicorn worker，一次回调最多能让**全站**停 30 秒，而这条路由不需要
        登录就能打——任何人拿垃圾 code 循环打它就是一台拒绝服务开关。
        这里用"执行线程不是主线程"来判定，与 _send_mail_off_loop 同一个约定。
        """
        import threading

        seen = {}

        def _record(code):
            seen["thread"] = threading.current_thread()
            return "tok"

        monkeypatch.setattr(qq, "exchange_code_for_token", _record)
        monkeypatch.setattr(qq, "fetch_openid", lambda tok: "OPENID-THREAD")
        monkeypatch.setattr(qq, "fetch_nickname", lambda tok, oid: None)

        state = _authorize(client)
        client.get("/api/auth/qq/callback?code=abc&state=" + state, follow_redirects=False)

        assert seen.get("thread") is not None, "回调压根没走到换 token 那一步"
        assert seen["thread"] is not threading.main_thread(), (
            "同步 HTTP 调用仍然跑在事件循环所在的线程上"
        )

    def test_callback_is_rate_limited(self, client, monkeypatch):
        """这条路由此前完全没有限流，而它不需要登录。

        单独分桶（不与 /auth/login 共用 "auth"）：回调被刷时不该把这个 IP 的
        正常登录也一起封掉——同 auth_register 分桶的那条教训。
        """
        monkeypatch.setattr(settings, "ratelimit_enabled", True)

        codes = set()
        for _ in range(25):
            r = client.get("/api/auth/qq/callback?code=x&state=forged", follow_redirects=False)
            codes.add(r.status_code)
        assert 429 in codes, "垃圾 code 可以无限刷回调"

        # 登录没有被连坐
        assert client.post(
            "/api/auth/login", json={"email": "nobody@example.com", "password": "password123"}
        ).status_code == 401

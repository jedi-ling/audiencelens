"""两个"未认证访客就能打到"的后端洞的回归。

1. SSRF：POST /api/keys/test 会让**服务器**按调用方给的 api_base 发一次真实
   请求，失败时还把目标响应正文的前 300 字符回显（见 src/runner/llm_client.py
   的 `HTTP {code} from {url}: {resp.text[:300]}`）。而 require_isolated_identity
   此前只在「不传 api_key」那个分支里调——自带 api_key 就不需要任何身份。
   于是任何访客都能拿它探测内网、读回响应片段，云上最典型的目标是
   169.254.169.254（实例元数据，能读出临时凭证）。

2. GET /api/jobs/{job_id} 曾经连 identity 参数都没有，是全后端唯一既无身份
   也无归属校验的数据接口，返回体含 ref_id（= review_id，打评审接口的钥匙）
   与 error_message（上游报错原文）。

这里的断言口径：不只看"返回了 400"，还要断言**一次外发请求都没有真的发出去**
——事后过滤响应等于探测已经完成，那不叫防住。
"""

import os
import sys

import pytest

from app.config import settings

_SRC = os.path.join(settings.repo_root, "src")
if _SRC not in sys.path:
    sys.path.insert(0, _SRC)

import runner.llm_client  # noqa: E402  （必须在 sys.path 补好之后导入）

from app.api import platform as platform_api  # noqa: E402
from app.core.errors import BadRequest  # noqa: E402

# 公网 IP 字面量：故意不用域名，免得单测依赖真实 DNS（离线就变红）。
#
# 这里**不能**用 RFC 5737 的文档网段（192.0.2.0/24、198.51.100.0/24、203.0.113.0/24）——
# 直觉上它们"不是内网"，但 Python 的 ipaddress 把这三段连同 198.18.0.0/15（benchmarking）
# 一起算进 `is_private`，所以守卫会（正确地）拒掉它们，测试却以为自己在测"公网可达"。
# 第一版就是这么写的，结果 3 条测试红着，看起来像守卫误杀合法端点，实际是测试选错了地址。
# 1.1.1.1 是真正的全球可路由地址（is_global=True），且这些用例全程 monkeypatch
# 掉真实网络调用，不会真的连出去。
PUBLIC_IP_BASE = "http://1.1.1.1:11434/v1"

INTERNAL_BASES = [
    "http://127.0.0.1:11434/v1",          # 环回
    "http://localhost:11434/v1",          # 环回（走主机名解析这条路）
    "http://169.254.169.254/latest/meta-data/",  # 云实例元数据
    "http://10.0.0.5:8000/v1",            # 私有 A 段
    "http://172.16.3.4:8000/v1",          # 私有 B 段
    "http://192.168.1.1/v1",              # 私有 C 段
    "http://[::1]:8080/v1",               # IPv6 环回
    "http://[::ffff:127.0.0.1]:8080/v1",  # IPv4-mapped IPv6（常见绕法）
    "http://0.0.0.0:8000/v1",             # 未指定地址
]


@pytest.fixture
def multi_tenant(monkeypatch):
    """多租户形态：开了账号体系，未登录访客是真实存在的。私网一律拒绝。"""
    monkeypatch.setattr(settings, "auth_enabled", True)


class TestGuardPolicy:
    """先测判定函数本身——路由层的用例只验证"它确实被调到了"。"""

    def test_preconditions_of_the_selfhost_branch(self):
        """默认测试环境必须落在「单机自建」那一档，否则下面那条放行用例
        会因为别的原因而绿（假绿比没测更糟）。"""
        assert settings.auth_enabled is False
        assert settings.looks_like_production is False

    @pytest.mark.parametrize("api_base", INTERNAL_BASES)
    def test_internal_targets_are_rejected_in_multi_tenant_form(self, api_base, multi_tenant):
        with pytest.raises(BadRequest):
            platform_api.assert_api_base_is_safe(api_base)

    def test_public_target_is_allowed(self, multi_tenant):
        """BYOK 用户挂在公网上的自建端点不能被误杀——这条防线拦的是
        "指回内网"，不是"不是大厂域名"。"""
        platform_api.assert_api_base_is_safe(PUBLIC_IP_BASE)

    def test_empty_means_official_endpoint_and_is_allowed(self, multi_tenant):
        for blank in (None, "", "   "):
            platform_api.assert_api_base_is_safe(blank)

    @pytest.mark.parametrize(
        "api_base",
        [
            "file:///etc/passwd",
            "gopher://127.0.0.1:11211/_stats",
            "ftp://example.com/x",
            "//example.com/v1",   # 没有协议
            "not a url",
        ],
    )
    def test_non_http_schemes_are_rejected(self, api_base, multi_tenant):
        with pytest.raises(BadRequest):
            platform_api.assert_api_base_is_safe(api_base)

    def test_unresolvable_host_is_rejected_before_any_request(self, multi_tenant):
        with pytest.raises(BadRequest):
            platform_api.assert_api_base_is_safe(
                "http://this-host-should-not-exist.invalid/v1"
            )

    def test_selfhosted_single_user_form_keeps_local_ollama_working(self):
        """AL_AUTH_ENABLED=false 且没在对公网服务 = 单机自建：这台机器只有一个
        使用者，llm_client 预设里的 http://localhost:11434/v1 必须继续可用，
        否则等于把自建用户的本地模型这条路直接砍掉。"""
        assert platform_api._private_api_base_allowed() is True
        platform_api.assert_api_base_is_safe("http://localhost:11434/v1")

    def test_going_multi_tenant_flips_the_policy(self, monkeypatch):
        """同一个地址，单机放行、多租户拒绝——判定边界只由形态决定。"""
        platform_api.assert_api_base_is_safe("http://localhost:11434/v1")
        monkeypatch.setattr(settings, "auth_enabled", True)
        with pytest.raises(BadRequest):
            platform_api.assert_api_base_is_safe("http://localhost:11434/v1")


@pytest.fixture
def no_real_calls(monkeypatch):
    """把真正会出网的那个函数换成记录器：断言"一次都没发"用的就是它。"""
    calls = []

    def _spy(**kwargs):
        calls.append(kwargs)
        return {"connected": True, "model": kwargs.get("model"), "sample": "ok"}

    monkeypatch.setattr(runner.llm_client, "test_connection", _spy)
    return calls


def _register(client, email):
    r = client.post("/api/auth/register", json={"email": email, "password": "password123"})
    assert r.status_code == 200, r.text
    return {"Authorization": f"Bearer {r.json()['token']}"}


class TestKeysTestEndpoint:
    def test_anonymous_cannot_drive_it_at_all_when_auth_is_on(
        self, client, multi_tenant, no_real_calls
    ):
        """自带 api_key 也要先有身份：这个端点是一根出网探针，
        不该对未认证访客开放。"""
        r = client.post(
            "/api/keys/test",
            json={
                "api_key": "sk-whatever",
                "provider": "openai_compatible",
                "model": "m",
                "api_base": PUBLIC_IP_BASE,
            },
        )
        assert r.status_code == 401
        assert no_real_calls == []

    def test_internal_api_base_is_refused_without_sending_anything(
        self, client, multi_tenant, no_real_calls
    ):
        headers = _register(client, "ssrf-probe@example.com")
        r = client.post(
            "/api/keys/test",
            json={
                "api_key": "sk-whatever",
                "provider": "openai_compatible",
                "model": "m",
                "api_base": "http://169.254.169.254/latest/meta-data/",
            },
            headers=headers,
        )
        assert r.status_code == 400
        assert no_real_calls == [], "请求已经发出去了——探测这件事本身就已经完成"

    def test_public_api_base_still_works_for_byok(self, client, multi_tenant, no_real_calls):
        headers = _register(client, "ssrf-legit@example.com")
        r = client.post(
            "/api/keys/test",
            json={
                "api_key": "sk-whatever",
                "provider": "openai_compatible",
                "model": "llama3",
                "api_base": PUBLIC_IP_BASE,
            },
            headers=headers,
        )
        assert r.status_code == 200
        assert len(no_real_calls) == 1
        assert no_real_calls[0]["api_base"] == PUBLIC_IP_BASE


class TestSaveKeyEndpoint:
    def test_internal_api_base_cannot_be_stored(self, client, multi_tenant, no_real_calls):
        """只堵 /keys/test 是半修：存下来的 api_base 之后每次评审/意图解析/追问
        都会被服务器拿去发请求，是同一个 SSRF 的另一个入口。"""
        headers = _register(client, "ssrf-save@example.com")
        r = client.post(
            "/api/keys",
            json={
                "api_key": "sk-whatever",
                "provider": "openai_compatible",
                "model": "m",
                "api_base": "http://127.0.0.1:11434/v1",
            },
            headers=headers,
        )
        assert r.status_code == 400

        # 公网端点照常存得进去
        r = client.post(
            "/api/keys",
            json={
                "api_key": "sk-whatever",
                "provider": "openai_compatible",
                "model": "m",
                "api_base": PUBLIC_IP_BASE,
            },
            headers=headers,
        )
        assert r.status_code == 200
        assert r.json()["api_base"] == PUBLIC_IP_BASE


class TestJobOwnership:
    def test_another_users_job_is_not_readable(self, client):
        from app.services import job_service

        job_id = job_service.create_job(
            kind="review", ref_id="rv-secret", user_id="somebody-else"
        )
        r = client.get(f"/api/jobs/{job_id}")  # 未登录 = 匿名桶
        assert r.status_code == 404
        # 连"这个 id 存在"都不该确认，所以是 404 而不是 403
        assert "rv-secret" not in r.text

    def test_my_own_job_is_readable(self, client):
        from app.services import job_service

        job_id = job_service.create_job(kind="review", ref_id="rv-mine", user_id="anonymous")
        r = client.get(f"/api/jobs/{job_id}")
        assert r.status_code == 200
        body = r.json()
        assert body["id"] == job_id
        assert body["ref_id"] == "rv-mine"

    def test_unknown_job_is_404(self, client):
        assert client.get("/api/jobs/does-not-exist").status_code == 404

    def test_logged_in_user_cannot_read_the_anonymous_bucket(
        self, client, multi_tenant
    ):
        """归属比对是精确相等，不是"有身份就能看"。"""
        from app.services import job_service

        job_id = job_service.create_job(kind="review", ref_id="rv-anon", user_id="anonymous")
        headers = _register(client, "job-owner@example.com")
        assert client.get(f"/api/jobs/{job_id}", headers=headers).status_code == 404

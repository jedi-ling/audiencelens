"""/api/health 的 config 是**公开**响应，字段集必须受控。

这个端点不鉴权，任何人都能打。所以它的字段集有两条约束，两条都容易在
后续开发里被无声破坏：

  1. 不许多给。曾经回过 env / ratelimit_enabled / queue_backend /
     ledger_enabled / review_concurrency 五项，前端一个都没消费——
     但 ratelimit_enabled=false + quota_enabled=false + server_key_present=true
     组合起来就是「这里可以免费无限调模型」，省掉了攻击者试探的成本。
     以后有人"顺手把这个配置也暴露一下方便调试"时，这条会红。

  2. 不许少给。前后端字段名对不上时 TypeScript 不会报错（config 来自
     运行时 JSON），只会让某个开关静默失效——比如 auth_enabled 改了名，
     前端读到 undefined，登录入口就永远不显示了。

第 2 条对应本仓已有的一批 parity 测试（test_frontend_report_field_parity 等），
用同样的源码断言手法：前端没有测试运行器，比对源码文本反而最贴近事实源。
"""

import io
import os
import re

REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", ".."))
TYPES_TS = os.path.join(REPO_ROOT, "web", "frontend", "src", "lib", "types.ts")
SESSION_STORE = os.path.join(REPO_ROOT, "web", "frontend", "src", "store", "session-store.ts")


def _read(path: str) -> str:
    with io.open(path, encoding="utf-8") as fh:
        return fh.read()


def _health_config_keys() -> set:
    from app.config import settings

    return set(settings.sanitized())


def _ts_health_config_fields() -> set:
    source = _read(TYPES_TS)
    m = re.search(r"interface HealthConfig\s*\{", source)
    assert m, "types.ts 里找不到 interface HealthConfig"
    start = source.index("{", m.start())
    depth = 0
    for i in range(start, len(source)):
        if source[i] == "{":
            depth += 1
        elif source[i] == "}":
            depth -= 1
            if depth == 0:
                body = source[start + 1 : i]
                break
    else:
        raise AssertionError("HealthConfig 的花括号不闭合")
    return set(re.findall(r"^\s*(\w+)\??:", body, re.M))


def test_backend_and_frontend_agree_on_health_config():
    """字段名两边必须一字不差。

    对不上时 TypeScript 不会报错——config 是运行时 JSON，类型只是声明。
    后果是某个开关静默失效（比如 auth_enabled 改名后前端读到 undefined，
    登录入口永远不显示），而所有构建和类型检查都是绿的。
    """
    backend = _health_config_keys()
    frontend = _ts_health_config_fields()

    assert backend == frontend, (
        f"/api/health 的 config 字段两边对不上。\n"
        f"  后端有、前端没有：{sorted(backend - frontend)}\n"
        f"  前端有、后端没给：{sorted(frontend - backend)}\n"
        "改 config.sanitized() 时必须同步 types.ts 的 HealthConfig。"
    )


def test_health_config_stays_minimal():
    """公开端点只回前端真的要用的字段。

    这条不是形式主义。/health 不鉴权，多暴露一个运行时开关就多给扫描器
    一条信息。历史上这里回过 5 个前端从没读过的字段，其中 ratelimit_enabled
    是侦察价值最高的那个。

    新增字段前先回答：前端真的会读它吗？会读就加进下面的白名单并说明用途；
    不会读就不该出现在公开响应里——想看运行时状态请走鉴权后的后台接口。
    """
    allowed = {
        "auth_enabled",       # 前端隐藏/显示登录入口
        "key_mode",           # 与 server_key_present 一起决定"能不能跑评审"
        "server_key_present",
        "quota_enabled",      # 前端隐藏/显示配额进度条
        "qq_login_enabled",   # 前端隐藏/显示「QQ 登录」按钮——没配齐就不该画那个按钮
    }
    actual = _health_config_keys()

    extra = actual - allowed
    assert not extra, (
        f"/api/health 暴露了白名单之外的字段：{sorted(extra)}。\n"
        "这个端点不鉴权。若前端确实要用，请加进本测试的 allowed 并注明用途；"
        "若只是为了方便调试，请改用鉴权后的后台接口（/api/admin/*）。"
    )


def test_every_exposed_field_is_actually_consumed():
    """反向对照：白名单里的字段必须真的有人读。

    只有"不许多给"是不够的——白名单本身也会腐化：某个字段的消费点被重构掉了，
    字段却留在公开响应里，下一个人会以为它还有用。
    """
    store = _read(SESSION_STORE)
    for field in _health_config_keys():
        assert re.search(r"\b%s\b" % re.escape(field), store), (
            f"/api/health 暴露了 {field}，但 session-store.ts（唯一的消费点）"
            "里找不到对它的引用——要么消费点被删了，要么这个字段该从公开响应里拿掉。"
        )


def test_admin_enabled_is_never_exposed():
    """绝不向公网广播"这里有后台管理接口"。

    后台是静态共享令牌、无有效期、无失败上限，长度是它唯一的强度来源。
    没必要主动告诉扫描器它存在。
    """
    assert "admin_enabled" not in _health_config_keys()
    assert "admin_token" not in _health_config_keys()


def test_no_secret_shaped_values_leak():
    """兜底：公开响应里不许出现任何看起来像密钥的东西。

    白名单挡的是"字段名"，这条挡的是"值"——比如有人把 key_mode 改成回
    完整的 provider 配置，字段名没变但内容变成了密钥。
    """
    import json

    from app.config import settings

    raw = json.dumps(settings.sanitized(), default=str).lower()
    for pattern in ("sk-", "secret", "password", "ciphertext", "-----begin"):
        assert pattern not in raw, f"/api/health 的响应里出现了疑似密钥内容：{pattern!r}"


# ============ /api/health 必须反映运行时覆盖，而不是启动快照 ============
#
# key_mode 与平台 key 都能在后台面板运行时改（写库，不动 env）。
# 如果 /api/health 直接回 settings.sanitized()，前端拿到的就是**进程启动那一刻**
# 的 env 快照，于是出现这个具体故障：
#
#   运营在后台配好平台 key、把 key_mode 切成 managed
#     → 前端仍读到 byok / server_key_present=false
#     → session-store 的 canReview() 判定 false，"发起评审"按钮是灰的
#     → 而后端 key_service.resolve_key 明明已经能解析出 key，跑得起来
#
# 后台点了没反应、页面又没有任何报错，是最难排查的一类问题。
# 下面两条分别钉住两个字段。


class TestHealthReflectsRuntimeOverrides:
    """后台改了运行时配置，/api/health 必须当场反映。"""

    def test_key_mode_override_is_reflected(self, client, db):
        from app.services import admin_settings_service

        before = client.get("/api/health").json()["config"]["key_mode"]
        admin_settings_service.set_override(db, "key_mode", "managed")
        try:
            after = client.get("/api/health").json()["config"]["key_mode"]
            assert after == "managed", (
                f"后台把 key_mode 改成了 managed，/api/health 却仍回 {after!r}。"
                "前端会按旧模式判断能不能发起评审——后台点了没反应，且没有任何报错。"
            )
            assert before != after, "前置条件失效：改之前就已经是 managed 了"
        finally:
            admin_settings_service.clear_override(db, "key_mode")

    def test_platform_key_set_via_admin_is_reflected(self, client, db):
        """平台 key 存在**数据库**里，而 settings.server_llm_key 只是 env。

        这条是本文件里唯一一个"后端能跑但前端说不能跑"的形态：
        canReview() 在 managed 模式下只看 server_key_present。
        """
        from app.services import key_service

        assert client.get("/api/health").json()["config"]["server_key_present"] is False, (
            "前置条件失效：测试环境本来就有平台 key（env 里设了 ANTHROPIC_API_KEY？）"
        )

        key_service.save_platform_key(db, "sk-ant-test-platform-key-0123456789")
        try:
            cfg = client.get("/api/health").json()["config"]
            assert cfg["server_key_present"] is True, (
                "后台已经配好平台 key（key_service.resolve_key 能解析出来），"
                "/api/health 却仍回 server_key_present=false。"
                "managed 模式下前端 canReview() 只看这个字段——"
                "结果是后端跑得起来，而用户那边「发起评审」按钮是灰的。"
            )
        finally:
            key_service.delete_platform_key(db)

    def test_health_never_returns_the_platform_key_itself(self, client, db):
        """合成运行时状态时只能给布尔，绝不能把 key 带出来。

        /api/health 不鉴权。这条防的是"顺手把 key 的信息也回一下方便调试"。
        """
        from app.services import key_service

        secret = "sk-ant-must-never-appear-in-health-9876543210"
        key_service.save_platform_key(db, secret)
        try:
            raw = client.get("/api/health").text
            assert secret not in raw
            assert "sk-ant" not in raw, "平台 key（哪怕是脱敏形式）出现在公开的 /api/health 里"
        finally:
            key_service.delete_platform_key(db)

    def test_db_failure_falls_back_instead_of_500(self, client, monkeypatch):
        """读运行时覆盖值失败时，存活探测要回落而不是 500。

        /api/health 是**进程存活**语义（容器 healthcheck 用它）。
        数据库抖一下就让它 500，会导致容器被 orchestrator 杀掉重启——
        而重启解决不了数据库的问题，只会让服务在重启循环里彻底不可用。
        判断依赖健不健康是 /health/ready 的职责。
        """
        from app.services import admin_settings_service

        def _boom(*args, **kwargs):
            raise RuntimeError("db is down")

        monkeypatch.setattr(admin_settings_service, "get", _boom)

        r = client.get("/api/health")
        assert r.status_code == 200, "读库失败把存活探测打成了非 200，容器会被反复重启"
        assert r.json()["config"]["key_mode"], "回落时也要给出 env 快照，不能是空的"

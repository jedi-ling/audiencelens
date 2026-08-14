"""就绪探测：/health/ready 必须真的探数据库。

这条测试守的是一个很容易退化的东西。/health 返回的 "ok" 是写死的字符串——
数据库挂掉、磁盘满、连接池耗尽时它照样 200。拿那种端点接外部监控，
监控到的只是"uvicorn 进程还活着"，而用户看到的是每个页面都在报错。
这就是"监控一片绿、服务全挂"。

所以 /health/ready 的**全部价值**在于它会在数据库不可用时变红。
如果只测"正常时返回 200"，那这条测试和被测端点一样没用——它会在
有人把 db.execute 那行删掉之后继续全绿。因此下面必然有一条
"数据库炸了必须 503"的反向断言，那才是这个文件真正的意义。
"""

import pytest


class TestLivenessProbe:
    def test_health_does_not_touch_the_database(self, client):
        """/health 是纯进程存活探测，刻意不查库——容器 healthcheck 用它。

        这一条钉住的是"分工"：如果哪天有人给 /health 也加上数据库检查，
        容器会在数据库短暂抖动时被 orchestrator 杀掉重启，而重启解决不了
        数据库的问题，只会让服务在重启循环里彻底不可用。
        """
        r = client.get("/api/health")
        assert r.status_code == 200
        body = r.json()
        assert body["status"] == "ok"
        # 它回的是配置快照，不是数据库状态
        assert "config" in body
        assert "checks" not in body, (
            "/health 出现了 checks 字段——它不该做依赖探测，那是 /health/ready 的职责"
        )


class TestReadinessProbe:
    def test_returns_ok_when_database_is_reachable(self, client):
        r = client.get("/api/health/ready")
        assert r.status_code == 200
        assert r.json() == {"status": "ok", "checks": {"database": "ok"}}

    def test_returns_503_when_database_is_down(self, client, monkeypatch):
        """数据库不可用时必须 503。

        **这是本文件的核心断言。** 没有它，/health/ready 退化成第二个写死的
        "ok" 也不会有任何测试变红——而那正是它存在的唯一理由。

        做法是让 Session.execute 抛异常，模拟连接池耗尽 / 库挂了 / 磁盘满。
        """
        from sqlalchemy.exc import OperationalError
        from sqlalchemy.orm import Session

        def _boom(self, *args, **kwargs):
            raise OperationalError("SELECT 1", {}, Exception("connection refused"))

        monkeypatch.setattr(Session, "execute", _boom)

        r = client.get("/api/health/ready")
        assert r.status_code == 503, (
            "数据库已经不可用，就绪探测却仍返回 200——"
            "外部监控会一直显示绿色，而用户那边每个页面都在报错"
        )
        body = r.json()
        assert body["status"] == "error"
        # 带出异常类型便于排查：OperationalError 与 TimeoutError 的处置完全不同
        assert body["checks"]["database"] == "OperationalError"

    def test_error_response_does_not_leak_connection_details(self, client, monkeypatch):
        """探测失败的响应里不许出现连接串/主机名/口令。

        这个端点不鉴权（外部监控探针没有令牌），所以它的错误响应是**公开**的。
        直接把异常消息回出去，等于把数据库地址和用户名挂在公网上。
        """
        from sqlalchemy.exc import OperationalError
        from sqlalchemy.orm import Session

        secret_ish = "postgresql://admin:hunter2@db.internal:5432/audiencelens"

        def _boom(self, *args, **kwargs):
            raise OperationalError("SELECT 1", {}, Exception(f"could not connect to {secret_ish}"))

        monkeypatch.setattr(Session, "execute", _boom)

        raw = client.get("/api/health/ready").text
        assert "hunter2" not in raw, "口令出现在公开的健康检查响应里"
        assert "db.internal" not in raw, "内网主机名出现在公开的健康检查响应里"
        assert secret_ish not in raw

    def test_requires_no_authentication(self, client):
        """外部监控探针没有令牌。加了鉴权这个端点就没法用了。"""
        r = client.get("/api/health/ready")
        assert r.status_code != 401
        assert r.status_code != 403

    def test_does_not_call_upstream_model_provider(self):
        """就绪探测刻意不查上游模型服务商——源码断言。

        两个理由（都写在端点的 docstring 里）：
          · 上游按调用计费，每分钟探一次会产生真实账单
          · 上游抖动不该让本服务被判定为宕机（评审会失败，但站点是能用的）

        这条断言防的是"顺手加个更全面的检查"——那会让健康检查本身变成
        一笔持续的开销，而且把不该联动的两件事绑在一起。
        """
        import inspect

        from app.api import platform

        source = inspect.getsource(platform.health_ready)
        for forbidden in ("anthropic", "openai", "llm_client", "resolve_key"):
            assert forbidden not in source.lower(), (
                f"就绪探测里出现了 {forbidden}——健康检查不该调用上游模型服务商"
            )

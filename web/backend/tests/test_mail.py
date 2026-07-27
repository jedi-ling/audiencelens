"""邮件链路：脱敏、SMTP 错误可读性、启动自检、后台测试发信端点。

这条链路的失败模式是**静默**的——配错了照样返回 200，只有用户收不到激活信。
所以这里的断言重点不是"能发出去"（那需要真的邮件服务商），而是：
  1. console 档下令牌绝不出现在日志里（正面断言，不是"看起来没有"）；
  2. SMTP 失败时抛的是人能读懂、写明改哪个配置项的错误，不是裸异常字符串；
  3. 类生产 + console 档会被拦下；
  4. 后台测试发信端点有鉴权、有限流、失败时把可读原因原样回给面板。
"""

import logging
import os
import smtplib
import socket
import ssl

import pytest

from app.config import settings
from app.services import mail_service

# 长得像真令牌：auth_token_service 发的是 40 位 base64url
FAKE_TOKEN = "MMCFgX_Xfo6u5kAClt_YIoox3sZxfwVZUZdhBtMA"
MAIL_BODY = (
    "点击链接重置密码（60 分钟内有效，只能用一次）：\n"
    f"http://localhost:5199/reset-password?token={FAKE_TOKEN}\n\n"
    "如果不是你本人操作，忽略这封邮件即可。"
)

ADMIN_TOKEN = "test-admin-token-mail-xyz"


@pytest.fixture
def outbox_dir(tmp_path, monkeypatch):
    """每个用例一个独立 outbox，绝不碰开发机上的 backend/data/outbox。"""
    d = tmp_path / "outbox"
    monkeypatch.setattr(settings, "mail_outbox_dir", str(d))
    return d


@pytest.fixture
def mail_logs():
    """收集 audiencelens logger 上的日志文本。

    **不能用 pytest 的 caplog**：core.logging.setup_logging 会把
    logger.propagate 设成 False，而 caplog 是挂在 root 上的 handler。
    于是本文件单跑时（app 还没启动过）caplog 能收到，全量跑时（别的用例先起过
    TestClient）就一条也收不到——断言 "令牌不在日志里" 会永远为真，
    变成一条假绿的安全测试。这里直接挂到目标 logger 上，与启动顺序无关。
    """
    from app.core.logging import logger

    records: list = []

    class _Collect(logging.Handler):
        def emit(self, record: logging.LogRecord) -> None:
            records.append(record.getMessage())

    handler = _Collect()
    prev_level = logger.level
    logger.addHandler(handler)
    logger.setLevel(logging.DEBUG)
    try:
        yield records
    finally:
        logger.removeHandler(handler)
        logger.setLevel(prev_level)


def _smtp_settings(monkeypatch, **overrides):
    """把配置摆成"已配好 SMTP"的样子。默认 465 + SSL，与模板一致。"""
    defaults = {
        "mail_backend": "smtp",
        "smtp_host": "smtp.example.com",
        "smtp_port": 465,
        "smtp_use_ssl": True,
        "smtp_user": "noreply@example.com",
        "smtp_password": "app-specific-password",
        "mail_from": "AudienceLens <noreply@example.com>",
        "smtp_timeout_seconds": 3.0,
    }
    defaults.update(overrides)
    for k, v in defaults.items():
        monkeypatch.setattr(settings, k, v)


# ============================== 脱敏 / console 档 ==============================


class TestRedaction:
    def test_redact_masks_token_value(self):
        out = mail_service._redact(MAIL_BODY)
        assert FAKE_TOKEN not in out
        # 保留前 4 位是为了还能和 DB 记录对上排障
        assert "token=MMCF…[已脱敏 40 字符]" in out

    def test_redact_handles_code_and_t_params(self):
        assert "abcdefghijkl" not in mail_service._redact("?code=abcdefghijkl")
        assert "abcdefghijkl" not in mail_service._redact("?t=abcdefghijkl")

    def test_redact_stops_at_query_separator(self):
        """只吃掉参数值，不该把后面的参数一起吞掉——否则日志失去排障价值。"""
        out = mail_service._redact(f"?token={FAKE_TOKEN}&lang=zh")
        assert "&lang=zh" in out

    def test_short_values_fully_masked(self):
        """短值不留前缀：4 位前缀对一个 6 位的码来说泄露太多。"""
        out = mail_service._redact("?token=abc123")
        assert "abc" not in out


class TestConsoleMailer:
    def test_token_never_reaches_logs(self, outbox_dir, mail_logs):
        """正面断言：整条日志流里搜不到令牌。

        这是本文件最重要的一条——能看日志 = 能接管任意账号。
        """
        mail_service.ConsoleMailer().send("u@example.com", "重置密码", MAIL_BODY)

        joined = "\n".join(mail_logs)
        assert joined, "没收到任何日志——断言会假绿，先修 mail_logs fixture"
        assert FAKE_TOKEN not in joined
        assert "已脱敏" in joined
        # 收件人/主题仍然要在，否则日志没有排障价值
        assert "u@example.com" in joined

    def test_full_link_written_to_outbox_file(self, outbox_dir, mail_logs):
        """令牌从日志里拿掉了，本地开发还得有地方取回链接——就是这个文件。"""
        mail_service.ConsoleMailer().send("u@example.com", "重置密码", MAIL_BODY)

        files = list(outbox_dir.iterdir())
        assert len(files) == 1
        content = files[0].read_text(encoding="utf-8")
        assert FAKE_TOKEN in content
        assert "u@example.com" in content
        # 日志要指路，否则开发者不知道去哪找
        assert str(outbox_dir) in "\n".join(mail_logs)

    @pytest.mark.skipif(os.name == "nt", reason="Windows 上文件权限由 ACL 决定，chmod 位不作数")
    def test_outbox_file_is_owner_only(self, outbox_dir):
        mail_service.ConsoleMailer().send("u@example.com", "重置密码", MAIL_BODY)
        path = next(iter(outbox_dir.iterdir()))
        assert oct(path.stat().st_mode)[-3:] == "600"

    def test_outbox_write_failure_does_not_fall_back_to_logging_token(
        self, monkeypatch, outbox_dir, mail_logs
    ):
        """写不进 outbox 时宁可丢链接，也绝不回落去打印完整正文。"""

        def _boom(*a, **kw):
            raise OSError("read-only file system")

        monkeypatch.setattr(mail_service.os, "makedirs", _boom)
        mail_service.ConsoleMailer().send("u@example.com", "重置密码", MAIL_BODY)

        joined = "\n".join(mail_logs)
        assert FAKE_TOKEN not in joined
        assert "写 outbox 失败" in joined


# ============================== SMTP 错误可读性 ==============================


class _RaisingSMTP:
    """替身：构造时或 login 时抛出指定异常，用来验证错误翻译。"""

    def __init__(self, exc, raise_on="login"):
        self._exc = exc
        self._raise_on = raise_on
        self.timeout = None

    def factory(self, host, port, timeout=None, context=None):
        self.host, self.port, self.timeout = host, port, timeout
        if self._raise_on == "connect":
            raise self._exc
        return self

    def __enter__(self):
        return self

    def __exit__(self, *a):
        return False

    def starttls(self, context=None):
        if self._raise_on == "starttls":
            raise self._exc

    def login(self, user, password):
        if self._raise_on == "login":
            raise self._exc

    def send_message(self, msg):
        if self._raise_on == "send":
            raise self._exc
        self.sent = msg


def _send_expecting_error(monkeypatch, exc, raise_on="login", **cfg):
    _smtp_settings(monkeypatch, **cfg)
    stub = _RaisingSMTP(exc, raise_on)
    monkeypatch.setattr(smtplib, "SMTP_SSL", stub.factory)
    monkeypatch.setattr(smtplib, "SMTP", stub.factory)
    with pytest.raises(mail_service.MailError) as ei:
        mail_service.SmtpMailer().send("u@example.com", "主题", "正文")
    return str(ei.value), stub


class TestSmtpErrorsAreReadable:
    def test_auth_failure_names_the_setting_to_change(self, monkeypatch):
        msg, _ = _send_expecting_error(
            monkeypatch,
            smtplib.SMTPAuthenticationError(535, b"535 Error: authentication failed"),
        )
        assert "认证失败" in msg
        assert "授权码" in msg           # 最常见的真实原因，必须点名
        assert "AL_SMTP_USER" in msg      # 要改哪个变量
        assert "smtp.example.com:465" in msg
        # 绝不能把裸的 repr 甩出来
        assert "SMTPAuthenticationError(" not in msg
        assert "b'" not in msg

    def test_sender_refused_points_at_mail_from(self, monkeypatch):
        msg, _ = _send_expecting_error(
            monkeypatch,
            smtplib.SMTPSenderRefused(553, b"553 sender not allowed", "noreply@example.com"),
            raise_on="send",
        )
        assert "发件人" in msg and "AL_MAIL_FROM" in msg

    def test_starttls_unsupported_suggests_ssl_port(self, monkeypatch):
        msg, _ = _send_expecting_error(
            monkeypatch,
            smtplib.SMTPNotSupportedError("STARTTLS extension not supported by server."),
            raise_on="starttls",
            smtp_port=587,
            smtp_use_ssl=False,
        )
        assert "AL_SMTP_PORT=465" in msg and "AL_SMTP_USE_SSL=true" in msg

    def test_tls_error_flags_port_mode_mismatch(self, monkeypatch):
        """587 + 隐式 SSL 是最常见的配反，错误里必须直接说出来。"""
        msg, _ = _send_expecting_error(
            monkeypatch,
            ssl.SSLError("wrong version number"),
            raise_on="connect",
            smtp_port=587,
            smtp_use_ssl=True,
        )
        assert "TLS 握手失败" in msg
        assert "AL_SMTP_USE_SSL" in msg and "587" in msg

    def test_timeout_mentions_port_25_blocking(self, monkeypatch):
        msg, _ = _send_expecting_error(
            monkeypatch, socket.timeout("timed out"), raise_on="connect", smtp_port=25,
            smtp_use_ssl=False,
        )
        assert "超时" in msg and "25 端口" in msg

    def test_dns_failure_points_at_host(self, monkeypatch):
        msg, _ = _send_expecting_error(
            monkeypatch, socket.gaierror(-2, "Name or service not known"), raise_on="connect"
        )
        assert "AL_SMTP_HOST" in msg and "smtp.example.com" in msg

    def test_connection_refused_is_readable(self, monkeypatch):
        msg, _ = _send_expecting_error(
            monkeypatch, ConnectionRefusedError(111, "Connection refused"), raise_on="connect"
        )
        assert "连接被拒绝" in msg

    def test_unknown_exception_still_readable(self, monkeypatch):
        msg, _ = _send_expecting_error(monkeypatch, RuntimeError("something odd"))
        assert "发信失败" in msg and "smtp.example.com:465" in msg

    def test_missing_host_is_explained(self, monkeypatch):
        _smtp_settings(monkeypatch, smtp_host="")
        with pytest.raises(mail_service.MailError) as ei:
            mail_service.SmtpMailer().send("u@example.com", "主题", "正文")
        assert "AL_SMTP_HOST" in str(ei.value)


class TestSmtpTimeout:
    def test_timeout_is_passed_to_smtplib(self, monkeypatch):
        """不传 timeout = 用 socket 全局默认（通常永不超时），
        一台连不上的 SMTP 主机就能把工作线程永久挂住。"""
        _smtp_settings(monkeypatch, smtp_timeout_seconds=7.0)
        stub = _RaisingSMTP(None, raise_on="never")
        monkeypatch.setattr(smtplib, "SMTP_SSL", stub.factory)
        mail_service.SmtpMailer().send("u@example.com", "主题", "正文")
        assert stub.timeout == 7.0

    def test_starttls_path_also_gets_timeout(self, monkeypatch):
        _smtp_settings(monkeypatch, smtp_port=587, smtp_use_ssl=False, smtp_timeout_seconds=9.0)
        stub = _RaisingSMTP(None, raise_on="never")
        monkeypatch.setattr(smtplib, "SMTP", stub.factory)
        mail_service.SmtpMailer().send("u@example.com", "主题", "正文")
        assert stub.timeout == 9.0
        assert stub.port == 587


class TestSendMailSwallowsButLogsReadably:
    def test_send_mail_does_not_raise_and_logs_readable_reason(self, monkeypatch, mail_logs):
        """注册链路不该因为邮件服务商抽风就整体失败，但失败原因必须可读。"""
        _smtp_settings(monkeypatch)
        stub = _RaisingSMTP(smtplib.SMTPAuthenticationError(535, b"nope"))
        monkeypatch.setattr(smtplib, "SMTP_SSL", stub.factory)
        backend = mail_service.send_mail("u@example.com", "主题", "正文")
        assert backend == "smtp"
        assert "授权码" in "\n".join(mail_logs)


class TestEffectiveBackend:
    def test_smtp_without_host_falls_back_and_is_reported(self, monkeypatch, outbox_dir):
        """配了 smtp 却缺 host 会回落 console —— 这个不一致必须能被看见。"""
        _smtp_settings(monkeypatch, smtp_host="")
        cfg = mail_service.describe_config()
        assert cfg["configured_backend"] == "smtp"
        assert cfg["effective_backend"] == "console"
        assert cfg["really_sends"] is False

    def test_describe_config_never_leaks_password(self, monkeypatch):
        _smtp_settings(monkeypatch, smtp_password="super-secret-app-password")
        cfg = mail_service.describe_config()
        assert "super-secret-app-password" not in repr(cfg)
        assert cfg["smtp_password_set"] is True


# ============================== 启动自检 ==============================


def _build_settings(monkeypatch, **env):
    """用干净的环境变量造一个 Settings，验证启动自检。

    不能复用全局 settings：自检发生在 __init__ 里。
    """
    from app.config import Settings

    for k in list(os.environ):
        if k.startswith("AL_"):
            monkeypatch.delenv(k, raising=False)
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    for k, v in env.items():
        monkeypatch.setenv(k, v)
    return Settings()


PROD_BASE = {
    "AL_ENV": "production",
    "AL_JWT_SECRET": "0" * 64,
    "AL_AUTH_ENABLED": "true",
    "AL_PUBLIC_WEB_URL": "https://example.com",
    "AL_CORS_ORIGINS": "https://example.com",
}


class TestStartupValidation:
    def test_production_with_console_mail_refuses_to_start(self, monkeypatch):
        with pytest.raises(RuntimeError) as ei:
            _build_settings(monkeypatch, **PROD_BASE)
        msg = str(ei.value)
        assert "AL_MAIL_BACKEND=smtp" in msg
        assert "AL_ALLOW_CONSOLE_MAIL=true" in msg  # 逃生舱要写明

    def test_explicit_escape_hatch_allows_console_but_warns(self, monkeypatch):
        s = _build_settings(monkeypatch, **PROD_BASE, AL_ALLOW_CONSOLE_MAIL="true")
        assert any("不会真的发出" in w for w in s.startup_warnings)

    def test_smtp_backend_without_host_refuses_to_start(self, monkeypatch):
        with pytest.raises(RuntimeError) as ei:
            _build_settings(monkeypatch, **PROD_BASE, AL_MAIL_BACKEND="smtp")
        assert "AL_SMTP_HOST" in str(ei.value)

    def test_local_dev_console_mail_is_not_blocked(self, monkeypatch):
        """本地开发不能被误伤——默认 console 档必须照常起得来。"""
        s = _build_settings(monkeypatch, AL_AUTH_ENABLED="true")
        assert s.mail_backend == "console"
        assert not s.looks_like_production

    def test_default_mail_from_warns(self, monkeypatch):
        s = _build_settings(
            monkeypatch, **PROD_BASE, AL_MAIL_BACKEND="smtp",
            AL_SMTP_HOST="smtp.example.com", AL_SMTP_PORT="465", AL_SMTP_USE_SSL="true",
        )
        assert any("AL_MAIL_FROM" in w for w in s.startup_warnings)

    def test_port_465_without_ssl_warns(self, monkeypatch):
        s = _build_settings(
            monkeypatch, **PROD_BASE, AL_MAIL_BACKEND="smtp",
            AL_SMTP_HOST="smtp.example.com", AL_SMTP_PORT="465",
            AL_MAIL_FROM="a@example.com",
        )
        assert any("AL_SMTP_USE_SSL=true" in w for w in s.startup_warnings)

    def test_port_587_with_ssl_warns(self, monkeypatch):
        s = _build_settings(
            monkeypatch, **PROD_BASE, AL_MAIL_BACKEND="smtp",
            AL_SMTP_HOST="smtp.example.com", AL_SMTP_PORT="587", AL_SMTP_USE_SSL="true",
            AL_MAIL_FROM="a@example.com",
        )
        assert any("AL_SMTP_USE_SSL=false" in w for w in s.startup_warnings)

    def test_localhost_public_url_warns_when_mail_works(self, monkeypatch):
        """邮件发得出去但链接指向 localhost = 用户点开打不开。"""
        env = dict(PROD_BASE)
        env["AL_PUBLIC_WEB_URL"] = "http://localhost:5199"
        s = _build_settings(
            monkeypatch, **env, AL_MAIL_BACKEND="smtp",
            AL_SMTP_HOST="smtp.example.com", AL_SMTP_PORT="465", AL_SMTP_USE_SSL="true",
            AL_MAIL_FROM="a@example.com",
        )
        assert any("AL_PUBLIC_WEB_URL" in w for w in s.startup_warnings)


# ============================== 后台测试发信端点 ==============================


def _headers(token=ADMIN_TOKEN):
    return {"X-Admin-Token": token}


@pytest.fixture
def admin_on(monkeypatch):
    from app.deps import reset_admin_auth_failures

    reset_admin_auth_failures()
    monkeypatch.setattr(settings, "admin_token", ADMIN_TOKEN)
    yield
    reset_admin_auth_failures()


@pytest.fixture(autouse=True)
def _clean_audit(db):
    from app.models import AdminAuditLog

    yield
    db.query(AdminAuditLog).delete()
    db.commit()


class TestAdminMailEndpointAuth:
    def test_disabled_without_admin_token(self, client, monkeypatch):
        monkeypatch.setattr(settings, "admin_token", "")
        assert client.get("/api/admin/mail/status").status_code == 503
        assert client.post("/api/admin/mail/test", json={"to": "a@b.com"}).status_code == 503

    def test_wrong_token_401(self, client, admin_on):
        r = client.post("/api/admin/mail/test", json={"to": "a@b.com"}, headers=_headers("nope"))
        assert r.status_code == 401


class TestAdminMailStatus:
    def test_status_shape_and_no_password(self, client, admin_on, monkeypatch):
        _smtp_settings(monkeypatch, smtp_password="super-secret-app-password")
        body = client.get("/api/admin/mail/status", headers=_headers()).json()
        assert body["configured_backend"] == "smtp"
        assert body["effective_backend"] == "smtp"
        assert body["really_sends"] is True
        assert body["smtp_password_set"] is True
        assert "super-secret-app-password" not in str(body)


class TestAdminMailTest:
    def test_rejects_malformed_address(self, client, admin_on):
        r = client.post("/api/admin/mail/test", json={"to": "not-an-email"}, headers=_headers())
        assert r.status_code == 400
        assert "收件地址" in r.json()["error"]["message"]

    def test_console_backend_reports_not_delivered(self, client, admin_on, monkeypatch, outbox_dir):
        """console 档必须明说"没发出去"——不能让运营看见绿勾就以为配好了。"""
        monkeypatch.setattr(settings, "mail_backend", "console")
        body = client.post(
            "/api/admin/mail/test", json={"to": "ops@example.com"}, headers=_headers()
        ).json()
        assert body["ok"] is True
        assert body["delivered"] is False
        assert "没有真的发出" in body["warning"]

    def test_smtp_success_reports_delivered(self, client, admin_on, monkeypatch):
        _smtp_settings(monkeypatch)
        stub = _RaisingSMTP(None, raise_on="never")
        monkeypatch.setattr(smtplib, "SMTP_SSL", stub.factory)
        body = client.post(
            "/api/admin/mail/test", json={"to": "ops@example.com"}, headers=_headers()
        ).json()
        assert body["ok"] is True and body["delivered"] is True
        assert "ops@example.com" in body["message"]

    def test_failure_returns_readable_reason(self, client, admin_on, monkeypatch):
        """这个端点存在的唯一目的就是把失败原因给运营看——不许吞。"""
        _smtp_settings(monkeypatch)
        stub = _RaisingSMTP(smtplib.SMTPAuthenticationError(535, b"535 auth failed"))
        monkeypatch.setattr(smtplib, "SMTP_SSL", stub.factory)
        body = client.post(
            "/api/admin/mail/test", json={"to": "ops@example.com"}, headers=_headers()
        ).json()
        assert body["ok"] is False
        assert "授权码" in body["error"]
        assert "SMTPAuthenticationError(" not in body["error"]

    def test_records_audit_entry(self, client, admin_on, monkeypatch, outbox_dir, db):
        from app.models import AdminAuditLog

        monkeypatch.setattr(settings, "mail_backend", "console")
        client.post("/api/admin/mail/test", json={"to": "ops@example.com"}, headers=_headers())
        rows = db.query(AdminAuditLog).filter(AdminAuditLog.action == "mail.test").all()
        assert len(rows) == 1 and rows[0].target == "ops@example.com"

    def test_rate_limited(self, client, admin_on, monkeypatch, outbox_dir):
        """持令牌者能对任意地址发信，不限流就是一台发信机。"""
        monkeypatch.setattr(settings, "mail_backend", "console")
        monkeypatch.setattr(settings, "ratelimit_enabled", True)
        codes = [
            client.post(
                "/api/admin/mail/test", json={"to": "ops@example.com"}, headers=_headers()
            ).status_code
            for _ in range(12)
        ]
        assert codes.count(429) >= 1
        assert codes[0] == 200

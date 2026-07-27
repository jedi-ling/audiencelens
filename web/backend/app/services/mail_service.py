"""邮件发送（可插拔）。

两个发送器：

- ``ConsoleMailer``（默认）：**不真发信**。日志里只留脱敏正文，完整邮件（含可用
  链接）写到本地 outbox 文件（0600）。这样本地开发还能点开链接走通验证/找回，
  而日志——会被 grep、被贴进 issue、被打包进 bug report——里没有任何令牌。
- ``SmtpMailer``：真发信。所有 smtplib/ssl/socket 异常都翻成**运维看得懂、
  带下一步动作**的中文错误（见 ``_smtp_error``），不是裸的异常字符串。

生产接 SMTP：配 AL_SMTP_HOST / AL_SMTP_PORT / AL_SMTP_USER / AL_SMTP_PASSWORD /
AL_MAIL_FROM，并设 AL_MAIL_BACKEND=smtp。配完在后台「邮件发送」面板点一次
「发送测试邮件」当场验证——不要等真实用户注册时才发现配错了。
类生产环境下仍留在 console 档会被启动自检拦下（见 config._validate_startup）。
"""

import os
import re
import smtplib
import socket
import ssl
import threading
from datetime import datetime
from email.message import EmailMessage
from typing import Optional

from app.config import settings
from app.core.logging import logger

# URL 里的 token/code 参数值。密码重置和邮箱验证链接就长这样：
#   https://站点/reset-password?token=<40 位 base64url>
_TOKEN_IN_URL = re.compile(r"((?:token|code|t)=)([^\s&#]+)", re.IGNORECASE)

# outbox 文件名里的收件人片段，去掉一切可能被当成路径的字符
_UNSAFE_IN_FILENAME = re.compile(r"[^A-Za-z0-9._-]")

_outbox_lock = threading.Lock()


class MailError(RuntimeError):
    """发信失败。

    message 面向运维：说清楚**是什么失败了**以及**下一步该改哪个配置项**。
    后台的测试发信端点直接把它回给面板，所以这里写的字就是运营看到的字。
    """


def _redact(text: str) -> str:
    """把邮件正文里的令牌换成掩码。

    能看日志 = 能接管任意账号，这条不能靠"生产不会开 console 档"来兜底：
    开发机的日志也会被 grep、被贴进 issue、被打包进 bug report。
    保留前 4 位是为了还能和 DB 里的记录对上，用来排障。
    """

    def _mask(m: re.Match) -> str:
        value = m.group(2)
        head = value[:4] if len(value) > 8 else ""
        return f"{m.group(1)}{head}…[已脱敏 {len(value)} 字符]"

    return _TOKEN_IN_URL.sub(_mask, text or "")


def _write_outbox(to: str, subject: str, body: str) -> Optional[str]:
    """把完整邮件写到本地 outbox 文件，返回路径；失败返回 None。

    为什么要有这个文件：令牌从日志里拿掉之后，本地开发就没有任何途径拿到
    验证/重置链接了（令牌落库是哈希的，翻 DB 也翻不出来），"邮箱验证"在开发机上
    等于不可用。所以完整内容仍然要落地，只是落到一个**单文件 0600、目录 0700、
    已被 .gitignore 覆盖**的地方，而不是那个会被到处传阅的日志流。

    Windows 上 chmod 基本是空操作（ACL 说了算），所以这条只在 POSIX 上是硬保证；
    真正的生产口径是根本不用 console 档——见 config._validate_startup。
    """
    outbox_dir = settings.mail_outbox_dir
    stamp = datetime.now().strftime("%Y%m%d-%H%M%S-%f")
    safe_to = _UNSAFE_IN_FILENAME.sub("_", to or "unknown")[:64]
    path = os.path.join(outbox_dir, f"{stamp}-{safe_to}.txt")
    content = (
        f"To: {to}\nSubject: {subject}\nDate: {datetime.now().isoformat(timespec='seconds')}\n"
        f"X-AudienceLens-Backend: console（本文件是本地投递，邮件并未真的发出）\n\n{body}\n"
    )
    try:
        with _outbox_lock:
            os.makedirs(outbox_dir, mode=0o700, exist_ok=True)
            fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
            with os.fdopen(fd, "w", encoding="utf-8") as f:
                f.write(content)
        return path
    except OSError as exc:
        # 只读文件系统 / 权限不足都可能走到这。**不要**因此回落去打印完整正文，
        # 那正是这个函数存在的理由。宁可开发者拿不到链接，也不把令牌塞进日志。
        logger.warning(
            "[mail:console] 写 outbox 失败（%s），本封邮件的链接无法本地取回。"
            "可改 AL_MAIL_OUTBOX_DIR 指到一个可写目录。",
            exc,
        )
        return None


class ConsoleMailer:
    """不真发信：日志脱敏 + 完整内容落 outbox 文件。开发/自建部署默认档。"""

    name = "console"

    def send(self, to: str, subject: str, body: str) -> None:
        path = _write_outbox(to, subject, body)
        where = f"完整内容（含可用链接）见 {path}" if path else "完整内容未能落盘（见上一条 warning）"
        logger.info(
            "[mail:console] 未配置邮件服务商，邮件未真实发送——用户收不到任何东西。"
            "要真的发信请配 AL_MAIL_BACKEND=smtp。\n"
            "  收件人: %s\n  主题: %s\n  %s\n%s",
            to,
            subject,
            where,
            _redact(body),
        )


def _decode_smtp_error(raw) -> str:
    """smtplib 把服务端原文放在 bytes 里，直接 str() 出来是 b'...' 这种噪音。"""
    if isinstance(raw, bytes):
        return raw.decode("utf-8", "replace").strip()
    return str(raw or "").strip()


def _endpoint() -> str:
    mode = "SSL" if settings.smtp_use_ssl else "STARTTLS"
    return f"{settings.smtp_host}:{settings.smtp_port}（{mode}）"


def _port_mode_hint() -> str:
    """端口和加密档最常见的配反。这个提示比任何服务端返回的报文都管用。"""
    if settings.smtp_port == 465 and not settings.smtp_use_ssl:
        return "（注意：465 是隐式 SSL 端口，当前 AL_SMTP_USE_SSL=false，很可能就是这里配反了）"
    if settings.smtp_port in (587, 25) and settings.smtp_use_ssl:
        return (
            f"（注意：{settings.smtp_port} 是 STARTTLS 端口，当前 AL_SMTP_USE_SSL=true，"
            "很可能就是这里配反了）"
        )
    return ""


def _smtp_error(exc: Exception) -> MailError:
    """把 smtplib / ssl / socket 的异常翻成可执行的中文说明。

    调用方（注册流程、后台测试端点）拿到的都是这一层的 message，
    不会是 `SMTPAuthenticationError(535, b'...')` 这种只有写代码的人看得懂的东西。
    """
    at = _endpoint()

    if isinstance(exc, smtplib.SMTPAuthenticationError):
        return MailError(
            f"SMTP 认证失败 @ {at}：{_decode_smtp_error(exc.smtp_error)}。"
            "多数邮箱服务商这里要填的是**授权码/应用专用密码**（在邮箱网页端「设置 → "
            "账户 → SMTP 服务」里单独申请），不是网页登录密码；"
            "另外确认 AL_SMTP_USER 与 AL_MAIL_FROM 的地址一致。"
        )
    if isinstance(exc, smtplib.SMTPSenderRefused):
        return MailError(
            f"发件人地址被拒 @ {at}：{_decode_smtp_error(exc.smtp_error)}。"
            f"当前 AL_MAIL_FROM={settings.mail_from!r}。"
            "服务商通常只允许用已验证的域名或与登录账号相同的地址发信，"
            "请把 AL_MAIL_FROM 改成 AL_SMTP_USER 对应的那个邮箱。"
        )
    if isinstance(exc, smtplib.SMTPRecipientsRefused):
        return MailError(
            f"收件人被拒 @ {at}：{exc.recipients}。"
            "检查收件地址是否拼错；若是自建/内网服务器，还要确认它允许向外域投递。"
        )
    if isinstance(exc, smtplib.SMTPNotSupportedError):
        return MailError(
            f"服务器不支持所请求的功能 @ {at}：{exc}。"
            "最常见的是它不支持 STARTTLS —— 改用隐式 SSL：AL_SMTP_PORT=465 且 "
            "AL_SMTP_USE_SSL=true。"
        )
    if isinstance(exc, ssl.SSLError):
        return MailError(
            f"TLS 握手失败 @ {at}：{exc}。{_port_mode_hint() or '请核对端口与 AL_SMTP_USE_SSL 的搭配：465 配 true，587/25 配 false。'}"
        )
    if isinstance(exc, smtplib.SMTPServerDisconnected):
        return MailError(
            f"连接被服务器中断 @ {at}：{exc}。{_port_mode_hint() or '常见原因是端口与加密方式不匹配，或服务器要求先认证。'}"
        )
    if isinstance(exc, (socket.timeout, TimeoutError)):
        return MailError(
            f"连接超时 @ {at}（超时 {settings.smtp_timeout_seconds:g}s）。"
            "国内云厂商默认封禁 25 端口出方向，请改用 465(SSL) 或 587(STARTTLS)；"
            "也检查安全组/防火墙是否放行了该端口的出网流量。"
        )
    if isinstance(exc, socket.gaierror):
        return MailError(
            f"域名解析失败：解析不出 {settings.smtp_host!r}。"
            "请核对 AL_SMTP_HOST 拼写（要填 SMTP 服务器地址，不是你的网站域名）。"
        )
    if isinstance(exc, ConnectionRefusedError):
        return MailError(
            f"连接被拒绝 @ {at}。端口不对或该端口上没有 SMTP 服务。{_port_mode_hint()}"
        )
    if isinstance(exc, smtplib.SMTPException):
        return MailError(f"SMTP 错误 @ {at}：{type(exc).__name__}: {exc}")
    if isinstance(exc, OSError):
        return MailError(f"网络错误 @ {at}：{type(exc).__name__}: {exc}")
    return MailError(f"发信失败 @ {at}：{type(exc).__name__}: {exc}")


class SmtpMailer:
    name = "smtp"

    def send(self, to: str, subject: str, body: str) -> None:
        if not settings.smtp_host:
            raise MailError(
                "AL_MAIL_BACKEND=smtp 但 AL_SMTP_HOST 为空——没有服务器地址无法发信。"
            )

        msg = EmailMessage()
        msg["From"] = settings.mail_from
        msg["To"] = to
        msg["Subject"] = subject
        msg.set_content(body)

        # 超时是必须的：smtplib 默认用 socket 的全局超时（通常等于"永不超时"），
        # 一个连不上的 SMTP 主机会把发起注册的那个工作线程永久挂住。
        timeout = settings.smtp_timeout_seconds
        try:
            if settings.smtp_use_ssl:
                with smtplib.SMTP_SSL(
                    settings.smtp_host,
                    settings.smtp_port,
                    timeout=timeout,
                    context=ssl.create_default_context(),
                ) as s:
                    self._deliver(s, msg)
            else:
                with smtplib.SMTP(settings.smtp_host, settings.smtp_port, timeout=timeout) as s:
                    s.starttls(context=ssl.create_default_context())
                    self._deliver(s, msg)
        except MailError:
            raise
        except Exception as exc:  # 统一翻译，绝不把裸异常字符串抛给上层
            raise _smtp_error(exc) from exc

    @staticmethod
    def _deliver(server, msg: EmailMessage) -> None:
        if settings.smtp_user:
            server.login(settings.smtp_user, settings.smtp_password)
        server.send_message(msg)


def get_mailer():
    """当前生效的发送器。

    注意这里可能与 AL_MAIL_BACKEND **不一致**：配了 smtp 却没配 AL_SMTP_HOST 时
    会回落到 console。这个不一致本身就是故障，所以 effective_backend()
    把两个值都暴露出来，后台面板会显式告诉运营"你配的是 X，实际在跑 Y"。
    """
    if settings.mail_backend == "smtp" and settings.smtp_host:
        return SmtpMailer()
    return ConsoleMailer()


def send_mail_strict(to: str, subject: str, body: str) -> str:
    """发信；失败抛 MailError（message 可读）。返回实际使用的后端名。"""
    mailer = get_mailer()
    mailer.send(to, subject, body)
    return mailer.name


def send_mail(to: str, subject: str, body: str) -> str:
    """发信；返回实际使用的后端名。发送失败不向上抛——注册/找回流程不该
    因为邮件服务商抽风就整体失败（且失败信息也不该泄露给调用方，见路由注释）。

    失败会以可读中文记进日志；运维要主动验证配置请用后台的「发送测试邮件」，
    那条路径不吞异常。"""
    mailer = get_mailer()
    try:
        mailer.send(to, subject, body)
    except MailError as exc:
        logger.warning("邮件发送失败（backend=%s）：%s", mailer.name, exc)
    except Exception as exc:  # 兜底：任何漏网异常也不该打断业务链路
        logger.warning("邮件发送失败（backend=%s）：%s", mailer.name, _smtp_error(exc))
    return mailer.name


def describe_config() -> dict:
    """给后台面板看的邮件配置快照。**绝不含密码**。

    暴露 configured_backend 与 effective_backend 两个字段：
    配了 smtp 却缺 AL_SMTP_HOST 时它们会不一致，那正是最该被看见的一种配错。
    """
    effective = get_mailer().name
    return {
        "configured_backend": settings.mail_backend,
        "effective_backend": effective,
        "really_sends": effective == "smtp",
        "mail_from": settings.mail_from,
        "smtp_host": settings.smtp_host or None,
        "smtp_port": settings.smtp_port,
        "smtp_use_ssl": settings.smtp_use_ssl,
        "smtp_user": settings.smtp_user or None,
        "smtp_password_set": bool(settings.smtp_password),
        "smtp_timeout_seconds": settings.smtp_timeout_seconds,
        "public_web_url": settings.public_web_url,
        "outbox_dir": settings.mail_outbox_dir if effective == "console" else None,
        "auth_enabled": settings.auth_enabled,
    }

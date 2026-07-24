"""邮件发送（可插拔）。

默认 console 发送器：不真发信，把内容和链接写进日志。这样"验证邮箱/忘记
密码"整条链路在没有任何邮件服务商的情况下也能开发、测试、自测通过——
接上 SMTP 只是换一个发送器，链路本身不用改。

生产接 SMTP：配 AL_SMTP_HOST / AL_SMTP_PORT / AL_SMTP_USER /
AL_SMTP_PASSWORD / AL_MAIL_FROM，AL_MAIL_BACKEND=smtp 即可。
"""

import smtplib
import ssl
from email.message import EmailMessage

from app.config import settings
from app.core.logging import logger


class ConsoleMailer:
    """把邮件写进日志而不真发。开发/自建部署默认档。"""

    name = "console"

    def send(self, to: str, subject: str, body: str) -> None:
        logger.info(
            "[mail:console] 未配置邮件服务商，邮件未真实发送。\n"
            "  收件人: %s\n  主题: %s\n%s",
            to,
            subject,
            body,
        )


class SmtpMailer:
    name = "smtp"

    def send(self, to: str, subject: str, body: str) -> None:
        msg = EmailMessage()
        msg["From"] = settings.mail_from
        msg["To"] = to
        msg["Subject"] = subject
        msg.set_content(body)

        if settings.smtp_use_ssl:
            with smtplib.SMTP_SSL(
                settings.smtp_host, settings.smtp_port, context=ssl.create_default_context()
            ) as s:
                if settings.smtp_user:
                    s.login(settings.smtp_user, settings.smtp_password)
                s.send_message(msg)
        else:
            with smtplib.SMTP(settings.smtp_host, settings.smtp_port) as s:
                s.starttls(context=ssl.create_default_context())
                if settings.smtp_user:
                    s.login(settings.smtp_user, settings.smtp_password)
                s.send_message(msg)


def get_mailer():
    if settings.mail_backend == "smtp" and settings.smtp_host:
        return SmtpMailer()
    return ConsoleMailer()


def send_mail(to: str, subject: str, body: str) -> str:
    """发信；返回实际使用的后端名。发送失败不向上抛——注册/找回流程不该
    因为邮件服务商抽风就整体失败（且失败信息也不该泄露给调用方，见路由注释）。"""
    mailer = get_mailer()
    try:
        mailer.send(to, subject, body)
    except Exception as exc:
        logger.warning("邮件发送失败（backend=%s）: %s", mailer.name, exc)
    return mailer.name

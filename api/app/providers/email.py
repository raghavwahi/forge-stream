from email.message import EmailMessage

import aiosmtplib

from app.providers.base import BaseEmailProvider


class SMTPEmailProvider(BaseEmailProvider):
    def __init__(
        self,
        host: str,
        port: int,
        username: str,
        password: str,
        from_email: str,
        use_tls: bool = True,
    ) -> None:
        self._host = host
        self._port = port
        self._username = username
        self._password = password
        self._from_email = from_email
        self._use_tls = use_tls

    async def send_email(
        self, to: str, subject: str, html_body: str
    ) -> None:
        message = EmailMessage()
        message["From"] = self._from_email
        message["To"] = to
        message["Subject"] = subject
        message.set_content(html_body, subtype="html")

        kwargs: dict = {
            "hostname": self._host,
            "port": self._port,
        }
        if self._username:
            kwargs["username"] = self._username
            kwargs["password"] = self._password
        if self._use_tls:
            kwargs["start_tls"] = True

        await aiosmtplib.send(message, **kwargs)

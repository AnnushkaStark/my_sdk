from pathlib import Path
from typing import Any

from fastapi import UploadFile
from fastapi_mail import ConnectionConfig
from fastapi_mail import FastMail
from fastapi_mail import MessageSchema
from fastapi_mail.schemas import MessageType
from jinja2 import Environment
from jinja2 import FileSystemLoader
from jinja2 import select_autoescape
from pydantic import EmailStr
from pydantic_settings import BaseSettings
from pydantic_settings import SettingsConfigDict


class EmailSettings(BaseSettings):
    """Настройки SMTP-подключения и директории HTML-шаблонов писем.

    По умолчанию читает переменные `MAIL_USERNAME`, `MAIL_PASSWORD`,
    `MAIL_FROM`, `MAIL_PORT`, `MAIL_SERVER`, `MAIL_STARTTLS`, `MAIL_SSL_TLS`
    и `MAIL_TEMPLATES_DIR` из окружения или `.env`.
    """

    model_config = SettingsConfigDict(
        env_prefix="MAIL_",
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    USERNAME: str
    PASSWORD: str
    FROM: EmailStr
    PORT: int = 587
    SERVER: str
    STARTTLS: bool = True
    SSL_TLS: bool = False
    TEMPLATES_DIR: str = "src/templates"

    @classmethod
    def from_prefix(cls, prefix: str = "MAIL_") -> "EmailSettings":
        """Загружает настройки почты с произвольным префиксом переменных.

        Args:
            prefix: Префикс переменных окружения (например, `"NOTIFICATIONS_MAIL_"`).

        Returns:
            Экземпляр настроек `EmailSettings`.
        """

        class PrefixedEmailSettings(cls):  # type: ignore[valid-type, misc]
            model_config = SettingsConfigDict(
                env_prefix=prefix,
                env_file=".env",
                env_file_encoding="utf-8",
                extra="ignore",
            )

        return PrefixedEmailSettings()


class EmailClient:
    """Асинхронный почтовый клиент для отправки HTML-писем на базе `fastapi-mail` и `Jinja2`.

    Загружает SMTP-конфигурацию и путь к директории шаблонов из переменных
    окружения (либо из переданных аргументов) и поддерживает вложения.

    Attributes:
        settings: Конфигурация SMTP и шаблонов `EmailSettings`.
        templates_dir: Путь к директории с Jinja2-шаблонами писем.
    """

    def __init__(
        self,
        settings: EmailSettings | None = None,
        env_prefix: str = "MAIL_",
        templates_dir: str | Path | None = None,
    ) -> None:
        """Инициализирует почтовый клиент и окружение шаблонизатора Jinja2.

        Args:
            settings: Готовый объект `EmailSettings`. Если не передан, загружается
                из переменных окружения по префиксу `env_prefix`.
            env_prefix: Префикс переменных окружения (по умолчанию `"MAIL_"`).
            templates_dir: Путь к папке с шаблонами. Если не указан, берётся
                из `MAIL_TEMPLATES_DIR` (по умолчанию `"src/templates"`).
        """
        self.settings = settings or EmailSettings.from_prefix(env_prefix)
        self.templates_dir = Path(templates_dir or self.settings.TEMPLATES_DIR)
        self._env = Environment(
            loader=FileSystemLoader(str(self.templates_dir)),
            enable_async=True,
            autoescape=select_autoescape(["html", "xml"]),
        )
        self._mail_config = ConnectionConfig(
            MAIL_USERNAME=self.settings.USERNAME,
            MAIL_PASSWORD=self.settings.PASSWORD,
            MAIL_FROM=self.settings.FROM,
            MAIL_PORT=self.settings.PORT,
            MAIL_SERVER=self.settings.SERVER,
            MAIL_STARTTLS=self.settings.STARTTLS,
            MAIL_SSL_TLS=self.settings.SSL_TLS,
        )
        self._fast_mail = FastMail(config=self._mail_config)

    async def send_mail(
        self,
        recipients: list[EmailStr],
        template: str,
        template_body: dict[str, Any] | None = None,
        subject: str = "",
        attachments: list[UploadFile] | None = None,
    ) -> dict[str, str]:
        """Рендерит HTML-шаблон письма и отправляет сообщение получателям.

        Args:
            recipients: Список email-адресов получателей.
            template: Имя файла шаблона внутри `templates_dir` (например, `"welcome.html"`).
            template_body: Словарь переменных для подстановки в Jinja2-шаблон.
            subject: Тема электронного письма.
            attachments: Необязательный список вложений `UploadFile`.

        Returns:
            Словарь со статусом отправки сообщения.

        Raises:
            RuntimeError: При ошибке рендеринга или отправки письма через SMTP.
        """
        context = template_body or {}
        jinja_template = self._env.get_template(template)
        html = await jinja_template.render_async(subject=subject, **context)

        message = MessageSchema(
            recipients=recipients,
            subject=subject,
            body=html,
            attachments=attachments or [],
            subtype=MessageType.html,
        )

        try:
            await self._fast_mail.send_message(message=message)
        except Exception as exc:
            raise RuntimeError("Error sending email message") from exc

        return {"message": "Message sent successfully"}


email_client = EmailClient()

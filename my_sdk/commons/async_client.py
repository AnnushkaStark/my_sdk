from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager
from typing import Any

from httpx import AsyncClient
from httpx import Timeout


class ApiClientBase:
    """Базовый асинхронный HTTP-клиент на базе `httpx.AsyncClient`.

    Предоставляет контекстный менеджер `_get_client` с безопасным закрытием
    соединений, поддержкой прокси, базового URL и настраиваемых таймаутов
    для наследников-интеграций с внешними сервисами.

    Attributes:
        base_url: Базовый URL внешнего API (если задан).
        timeout: Таймаут HTTP-запросов в секундах.
    """

    def __init__(
        self,
        base_url: str = "",
        timeout: float | Timeout = 15.0,
    ) -> None:
        """Инициализирует базовые параметры HTTP-клиента.

        Args:
            base_url: Базовый URL внешнего сервиса (по умолчанию пустая строка).
            timeout: Таймаут запросов в секундах или объект `httpx.Timeout`.
        """
        self.base_url = base_url
        self.timeout = timeout

    @asynccontextmanager
    async def _get_client(
        self,
        proxy: str | None = None,
        **client_kwargs: Any,
    ) -> AsyncGenerator[AsyncClient, None]:
        """Создаёт и автоматически закрывает экземпляр `httpx.AsyncClient`.

        Args:
            proxy: URL прокси-сервера (если требуется).
            **client_kwargs: Дополнительные параметры для `httpx.AsyncClient`
                (например, `headers`, `verify`, `follow_redirects`).

        Yields:
            Настроенный и готовый к работе асинхронный клиент `AsyncClient`.
        """
        async with AsyncClient(
            base_url=self.base_url,
            timeout=self.timeout,
            proxy=proxy or None,
            **client_kwargs,
        ) as client:
            yield client

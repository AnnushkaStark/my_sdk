from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager
from typing import Any

from pydantic_settings import BaseSettings
from pydantic_settings import SettingsConfigDict
from redis.asyncio import Redis


class RedisSettings(BaseSettings):
    """Настройки подключения к Redis, загружаемые из переменных окружения.

    По умолчанию читает переменную `REDIS_URL` из окружения или `.env`.
    """

    model_config = SettingsConfigDict(
        env_prefix="REDIS_",
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    URL: str = "redis://localhost:6379/0"

    @classmethod
    def from_prefix(cls, prefix: str = "REDIS_") -> "RedisSettings":
        """Загружает настройки Redis с произвольным префиксом переменных.

        Args:
            prefix: Префикс переменных окружения (например, `"CACHE_REDIS_"`).

        Returns:
            Экземпляр настроек `RedisSettings`.
        """

        class PrefixedRedisSettings(cls):  # type: ignore[valid-type, misc]
            model_config = SettingsConfigDict(
                env_prefix=prefix,
                env_file=".env",
                env_file_encoding="utf-8",
                extra="ignore",
            )

        return PrefixedRedisSettings()


@asynccontextmanager
async def get_redis(
    settings: RedisSettings | None = None,
    env_prefix: str = "REDIS_",
    **redis_kwargs: Any,
) -> AsyncGenerator[Redis, None]:
    """Асинхронный контекстный менеджер для работы с клиентом Redis.

    Автоматически читает `REDIS_URL` (или `<prefix>URL`) из переменных окружения
    и гарантированно закрывает соединение при выходе из блока `async with`.

    Args:
        settings: Готовый объект `RedisSettings`. Если не передан, загружается
            из переменных окружения.
        env_prefix: Префикс переменных окружения (по умолчанию `"REDIS_"`).
        **redis_kwargs: Дополнительные параметры для `Redis.from_url`.

    Yields:
        Активный асинхронный клиент `Redis`.
    """
    cfg = settings or RedisSettings.from_prefix(env_prefix)
    redis_client = Redis.from_url(cfg.URL, **redis_kwargs)
    try:
        yield redis_client
    finally:
        await redis_client.aclose()

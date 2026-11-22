from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from typing import Any

import clickhouse_connect
from clickhouse_connect.driver.asyncclient import AsyncClient
from pydantic_settings import BaseSettings
from pydantic_settings import SettingsConfigDict


class ClickHouseSettings(BaseSettings):
    """Настройки подключения к ClickHouse, загружаемые из переменных окружения.

    По умолчанию читает переменные `CLICKHOUSE_DB`, `CLICKHOUSE_HOST`,
    `CLICKHOUSE_PORT`, `CLICKHOUSE_USER`, `CLICKHOUSE_PASSWORD` из окружения или `.env`.
    """

    model_config = SettingsConfigDict(
        env_prefix="CLICKHOUSE_",
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    DB: str = "default"
    HOST: str = "localhost"
    PORT: int = 8123
    USER: str = "default"
    PASSWORD: str = ""

    @classmethod
    def from_prefix(cls, prefix: str = "CLICKHOUSE_") -> "ClickHouseSettings":
        """Загружает настройки ClickHouse с произвольным префиксом переменных.

        Args:
            prefix: Префикс переменных окружения (например, `"DWH_CLICKHOUSE_"`).

        Returns:
            Экземпляр настроек `ClickHouseSettings`.
        """

        class PrefixedClickHouseSettings(cls):  # type: ignore[valid-type, misc]
            model_config = SettingsConfigDict(
                env_prefix=prefix,
                env_file=".env",
                env_file_encoding="utf-8",
                extra="ignore",
            )

        return PrefixedClickHouseSettings()


@asynccontextmanager
async def get_clickhouse_conn(
    settings: ClickHouseSettings | None = None,
    env_prefix: str = "CLICKHOUSE_",
    init_query: str | None = None,
    **client_kwargs: Any,
) -> AsyncIterator[AsyncClient]:
    """Асинхронный контекстный менеджер для работы с клиентом ClickHouse.

    Автоматически читает параметры подключения из переменных окружения,
    выбирает целевую БД, при необходимости выполняет стартовый DDL-скрипт
    `init_query` и гарантированно закрывает соединение при выходе из контекста.

    Args:
        settings: Готовый объект `ClickHouseSettings`. Если не передан, загружается
            автоматически по префиксу `env_prefix`.
        env_prefix: Префикс переменных окружения (по умолчанию `"CLICKHOUSE_"`).
        init_query: Необязательный SQL-запрос инициализации (например, `CREATE TABLE IF NOT EXISTS ...`).
        **client_kwargs: Дополнительные параметры для `clickhouse_connect.get_async_client`.

    Yields:
        Активный асинхронный клиент `AsyncClient`.
    """
    cfg = settings or ClickHouseSettings.from_prefix(env_prefix)
    conn = await clickhouse_connect.get_async_client(
        database=cfg.DB,
        host=cfg.HOST,
        port=cfg.PORT,
        username=cfg.USER,
        password=cfg.PASSWORD,
        **client_kwargs,
    )
    try:
        await conn.command(f"USE {cfg.DB}")
        if init_query:
            await conn.command(init_query)
        yield conn
    finally:
        await conn.close()

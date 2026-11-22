from collections.abc import AsyncGenerator
from typing import Any
from typing import ClassVar

from pydantic_settings import BaseSettings
from pydantic_settings import SettingsConfigDict
from sqlalchemy import Integer
from sqlalchemy.engine import URL
from sqlalchemy.ext.asyncio import AsyncEngine
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.ext.asyncio import async_sessionmaker
from sqlalchemy.ext.asyncio import create_async_engine
from sqlalchemy.orm import DeclarativeBase
from sqlalchemy.sql.sqltypes import ARRAY
from sqlalchemy.sql.sqltypes import String


class PostgresSettings(BaseSettings):
    """Настройки подключения к PostgreSQL, загружаемые из переменных окружения."""

    model_config = SettingsConfigDict(
        env_prefix="POSTGRES_",
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    USER: str = "postgres"
    PASSWORD: str = "postgres"
    HOST: str = "localhost"
    PORT: int = 5432
    DB: str = "postgres"

    def build_url(self) -> URL:
        """Формирует безопасный URL подключения для `asyncpg`."""
        return URL.create(
            drivername="postgresql+asyncpg",
            username=self.USER,
            password=self.PASSWORD,
            host=self.HOST,
            port=self.PORT,
            database=self.DB,
        )


class Base(DeclarativeBase):
    """Базовый декларативный класс моделей SQLAlchemy с маппингом списков в `ARRAY`."""

    type_annotation_map: ClassVar[dict[Any, Any]] = {
        list: ARRAY,
        list[str]: ARRAY(String),
        list[int]: ARRAY(Integer),
    }


def create_postgres_engine(
    settings: PostgresSettings | None = None,
    pool_size: int = 100,
    max_overflow: int = 20,
    echo: bool = False,
    **engine_kwargs: Any,
) -> AsyncEngine:
    """Создаёт асинхронный `AsyncEngine` для PostgreSQL из переменных окружения."""
    cfg = settings or PostgresSettings()
    return create_async_engine(
        url=cfg.build_url(),
        pool_size=pool_size,
        max_overflow=max_overflow,
        echo=echo,
        pool_pre_ping=True,
        **engine_kwargs,
    )


async_engine = create_postgres_engine()

async_session = async_sessionmaker(
    async_engine,
    class_=AsyncSession,
    expire_on_commit=False,
)


async def get_async_session() -> AsyncGenerator[AsyncSession, None]:
    """Предоставляет асинхронную сессию SQLAlchemy на время обработки запроса."""
    async with async_session() as session:
        yield session

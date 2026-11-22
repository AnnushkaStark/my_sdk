from collections.abc import AsyncIterator
from typing import Annotated

from fastapi import Depends
from sqlalchemy.ext.asyncio import AsyncSession

from my_sdk.databases.pg import get_async_session


async def get_async_db() -> AsyncIterator[AsyncSession]:
    """FastAPI-зависимость для предоставления асинхронной сессии SQLAlchemy.

    Открывает сессию через `async_session()` на время обработки HTTP-запроса
    и гарантированно закрывает её после завершения запроса.

    Yields:
        Активная асинхронная сессия `AsyncSession`.
    """
    async with get_async_session() as session:
        yield session


Session = Annotated[AsyncSession, Depends(get_async_db)]
"""Готовый тип-алиас для инъекции `AsyncSession` в роуты FastAPI (`session: Session`)."""

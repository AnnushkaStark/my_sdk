import json
from typing import Any

from redis.asyncio.lock import Lock

from my_sdk.databases.redis_db import get_redis


class State:
    """Менеджер временного состояния на базе Redis с распределённой блокировкой.

    Обеспечивает атомарную запись (`SET NX` с TTL) и безопасное конкурентное
    чтение данных через распределённый лок (`redis.asyncio.lock.Lock`),
    предотвращая гонки между воркерами микросервиса.

    Attributes:
        env_prefix: Префикс переменных окружения для подключения к Redis.
    """

    def __init__(self, env_prefix: str = "REDIS_") -> None:
        """Инициализирует менеджер состояния.

        Args:
            env_prefix: Префикс переменных окружения Redis (по умолчанию `"REDIS_"`).
        """
        self.env_prefix = env_prefix

    def _deserialize(self, data: bytes) -> Any:
        """Декодирует байты из Redis в Python-объект (JSON или обычную строку)."""
        decoded_str = data.decode("utf-8")
        try:
            return json.loads(decoded_str)
        except (json.JSONDecodeError, TypeError):
            return decoded_str

    def _serialize(self, data: Any) -> str:
        """Сериализует произвольные данные в JSON-строку для записи в Redis."""
        if data is None:
            return ""

        if isinstance(data, str):
            return data

        try:
            return json.dumps(data, ensure_ascii=False)
        except (TypeError, ValueError):
            return str(data)

    async def set_state(self, key: str, value: Any, ttl: int = 600) -> bool:
        """Сохраняет состояние в Redis, если ключ ещё не существует (`NX`).

        Args:
            key: Уникальный ключ состояния.
            value: Значение (словарь, список, строка или примитив).
            ttl: Время жизни ключа в секундах (по умолчанию `600`).

        Returns:
            `True`, если ключ успешно создан, иначе `False`.
        """
        async with get_redis(env_prefix=self.env_prefix) as redis:
            created = await redis.set(
                name=key,
                ex=ttl,
                value=self._serialize(data=value),
                nx=True,
            )
            return bool(created)

    async def get_state(self, key: str) -> Any | None:
        """Извлекает и удаляет состояние из Redis с защитой распределённым локом.

        Сначала проверяет наличие значения без блокировки; если ключ ещё не
        появился, захватывает распределённый лок `{key}:lock` и повторяет попытку.

        Args:
            key: Уникальный ключ состояния.

        Returns:
            Десериализованное значение состояния или `None`, если ключ не найден.
        """
        async with get_redis(env_prefix=self.env_prefix) as redis_client:
            if found_obj := await redis_client.get(key):
                await redis_client.delete(key)
                return self._deserialize(found_obj)

            lock_key = f"{key}:lock"
            async with Lock(redis_client, lock_key, timeout=10, blocking_timeout=15):
                if found_obj := await redis_client.get(key):
                    await redis_client.delete(key)
                    return self._deserialize(found_obj)

        return None


state = State()
"""Готовый экземпляр менеджера состояния с настройками по умолчанию (`REDIS_*`)."""

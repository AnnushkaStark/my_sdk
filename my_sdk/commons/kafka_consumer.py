import json
from collections.abc import AsyncGenerator
from types import TracebackType
from typing import Any
from typing import Self

from aiokafka import AIOKafkaConsumer
from aiokafka import ConsumerRecord
from pydantic_settings import BaseSettings
from pydantic_settings import SettingsConfigDict


class KafkaConsumerSettings(BaseSettings):
    """Настройки подключения к брокеру Kafka для консьюмера.

    По умолчанию читает переменные `KAFKA_BOOTSTRAP_URL`, `KAFKA_GROUP_ID`
    и `KAFKA_AUTO_OFFSET_RESET` из окружения или `.env`.
    """

    model_config = SettingsConfigDict(
        env_prefix="KAFKA_",
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    BOOTSTRAP_URL: str = "localhost:9092"
    GROUP_ID: str = "default_service_group"
    AUTO_OFFSET_RESET: str = "earliest"

    @classmethod
    def from_prefix(cls, prefix: str = "KAFKA_") -> "KafkaConsumerSettings":
        """Загружает настройки Kafka с произвольным префиксом переменных.

        Args:
            prefix: Префикс переменных окружения (например, `"EVENTS_KAFKA_"`).

        Returns:
            Экземпляр настроек `KafkaConsumerSettings`.
        """

        class PrefixedKafkaConsumerSettings(cls):  # type: ignore[valid-type, misc]
            model_config = SettingsConfigDict(
                env_prefix=prefix,
                env_file=".env",
                env_file_encoding="utf-8",
                extra="ignore",
            )

        return PrefixedKafkaConsumerSettings()


class ConsumerBase:
    """Базовый асинхронный консьюмер сообщений для Apache Kafka.

    Поддерживает подписку на один или несколько топиков, ручной контроль
    смещений (`enable_auto_commit=False`), опциональную JSON-десериализацию
    и безопасное завершение при отмене фоновой задачи.

    Attributes:
        topics: Список топиков для подписки.
        group_id: Идентификатор consumer group.
        bootstrap_url: Адрес(а) брокеров Kafka (`host:port`).
        consumer: Экземпляр `AIOKafkaConsumer` или `None` до инициализации.
    """

    def __init__(
        self,
        topics: str | list[str],
        group_id: str | None = None,
        settings: KafkaConsumerSettings | None = None,
        env_prefix: str = "KAFKA_",
        deserialize_json: bool = False,
        **consumer_kwargs: Any,
    ) -> None:
        """Инициализирует конфигурацию консьюмера без немедленного подключения.

        Args:
            topics: Название топика или список топиков для чтения.
            group_id: Идентификатор consumer group. Если не указан, берётся
                из `KAFKA_GROUP_ID`.
            settings: Готовый объект `KafkaConsumerSettings`.
            env_prefix: Префикс переменных окружения (по умолчанию `"KAFKA_"`).
            deserialize_json: Если `True`, автоматически декодирует `value` как JSON.
            **consumer_kwargs: Дополнительные параметры для `AIOKafkaConsumer`.
        """
        cfg = settings or KafkaConsumerSettings.from_prefix(env_prefix)
        self.topics = [topics] if isinstance(topics, str) else list(topics)
        self.group_id = group_id or cfg.GROUP_ID
        self.bootstrap_url = cfg.BOOTSTRAP_URL
        self.auto_offset_reset = cfg.AUTO_OFFSET_RESET
        self.deserialize_json = deserialize_json
        self._consumer_kwargs = consumer_kwargs
        self.consumer: AIOKafkaConsumer | None = None

    async def start(self) -> None:
        """Создаёт и запускает экземпляр `AIOKafkaConsumer`."""
        if self.consumer is not None:
            return

        deserializer = (
            (lambda v: json.loads(v.decode("utf-8")) if v is not None else None) if self.deserialize_json else None
        )

        self.consumer = AIOKafkaConsumer(
            *self.topics,
            bootstrap_servers=self.bootstrap_url,
            group_id=self.group_id,
            auto_offset_reset=self.auto_offset_reset,
            enable_auto_commit=False,
            value_deserializer=deserializer,
            **self._consumer_kwargs,
        )
        await self.consumer.start()

    async def stop(self) -> None:
        """Корректно останавливает консьюмер и закрывает сетевые соединения."""
        if self.consumer is not None:
            await self.consumer.stop()
            self.consumer = None

    async def commit(self) -> None:
        """Фиксирует текущие обработанные смещения (offsets) в брокере Kafka."""
        if self.consumer is not None:
            await self.consumer.commit()

    async def read_messages(self) -> AsyncGenerator[ConsumerRecord, None]:
        """Асинхронно читает сообщения из подписанных топиков.

        Гарантированно останавливает консьюмер при выходе из генератора
        или отмене корутины.

        Yields:
            Входящие записи `ConsumerRecord` из брокера Kafka.
        """
        await self.start()
        assert self.consumer is not None
        try:
            async for message in self.consumer:
                yield message
        finally:
            await self.stop()

    async def __aenter__(self) -> Self:
        """Запускает консьюмер при входе в блок `async with`."""
        await self.start()
        return self

    async def __aexit__(
        self,
        exc_type: type[BaseException] | None,
        exc_val: BaseException | None,
        exc_tb: TracebackType | None,
    ) -> None:
        """Останавливает консьюмер при выходе из блока `async with`."""
        await self.stop()

import json
from types import TracebackType
from typing import Any
from typing import Self

from aiokafka import AIOKafkaProducer
from pydantic_settings import BaseSettings
from pydantic_settings import SettingsConfigDict


class KafkaProducerSettings(BaseSettings):
    """Настройки подключения к брокеру Kafka для продюсера.

    По умолчанию читает переменную `KAFKA_BOOTSTRAP_URL` из окружения или `.env`.
    """

    model_config = SettingsConfigDict(
        env_prefix="KAFKA_",
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    BOOTSTRAP_URL: str = "localhost:9092"

    @classmethod
    def from_prefix(cls, prefix: str = "KAFKA_") -> "KafkaProducerSettings":
        """Загружает настройки Kafka с произвольным префиксом переменных.

        Args:
            prefix: Префикс переменных окружения (например, `"EVENTS_KAFKA_"`).

        Returns:
            Экземпляр настроек `KafkaProducerSettings`.
        """

        class PrefixedKafkaProducerSettings(cls):  # type: ignore[valid-type, misc]
            model_config = SettingsConfigDict(
                env_prefix=prefix,
                env_file=".env",
                env_file_encoding="utf-8",
                extra="ignore",
            )

        return PrefixedKafkaProducerSettings()


class Producer:
    """Асинхронный идемпотентный продюсер сообщений для Apache Kafka.

    Автоматически сериализует словари в JSON (`UTF-8`), поддерживает ленивый
    старт при первой отправке и работу через асинхронный контекстный менеджер.

    Attributes:
        bootstrap_url: Адрес(а) брокеров Kafka (`host:port`).
        producer: Экземпляр `AIOKafkaProducer` или `None` до запуска.
    """

    def __init__(
        self,
        settings: KafkaProducerSettings | None = None,
        env_prefix: str = "KAFKA_",
        **producer_kwargs: Any,
    ) -> None:
        """Инициализирует конфигурацию продюсера без немедленного подключения.

        Args:
            settings: Готовый объект `KafkaProducerSettings`. Если не передан,
                загружается из переменных окружения по префиксу `env_prefix`.
            env_prefix: Префикс переменных окружения (по умолчанию `"KAFKA_"`).
            **producer_kwargs: Дополнительные параметры для `AIOKafkaProducer`.
        """
        cfg = settings or KafkaProducerSettings.from_prefix(env_prefix)
        self.bootstrap_url = cfg.BOOTSTRAP_URL
        self._producer_kwargs = producer_kwargs
        self.producer: AIOKafkaProducer | None = None

    async def start(self) -> None:
        """Запускает клиент `AIOKafkaProducer` и устанавливает соединение с брокером."""
        if self.producer is not None:
            return

        self.producer = AIOKafkaProducer(
            bootstrap_servers=self.bootstrap_url,
            enable_idempotence=True,
            value_serializer=lambda v: json.dumps(v, ensure_ascii=False).encode("utf-8"),
            **self._producer_kwargs,
        )
        await self.producer.start()

    async def stop(self) -> None:
        """Корректно завершает работу продюсера и сбрасывает буфер сообщений."""
        if self.producer is not None:
            await self.producer.stop()
            self.producer = None

    async def send_message(
        self,
        message: dict[str, Any],
        topic: str,
        key: bytes | str | None = None,
    ) -> Any:
        """Отправляет JSON-сообщение в указанный топик Kafka и ждёт подтверждения.

        Если продюсер ещё не был запущен явно через `start()`, запускает его
        автоматически перед отправкой.

        Args:
            message: Словарь с полезной нагрузкой события.
            topic: Название целевого топика Kafka.
            key: Необязательный ключ партиционирования (`str` или `bytes`).

        Returns:
            Метаданные отправленной записи (`RecordMetadata`).
        """
        if self.producer is None:
            await self.start()

        assert self.producer is not None
        encoded_key = key.encode("utf-8") if isinstance(key, str) else key
        return await self.producer.send_and_wait(
            topic=topic,
            value=message,
            key=encoded_key,
        )

    async def __aenter__(self) -> Self:
        """Запускает продюсер при входе в блок `async with`."""
        await self.start()
        return self

    async def __aexit__(
        self,
        exc_type: type[BaseException] | None,
        exc_val: BaseException | None,
        exc_tb: TracebackType | None,
    ) -> None:
        """Останавливает продюсер при выходе из блока `async with`."""
        await self.stop()

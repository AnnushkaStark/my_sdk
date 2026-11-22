import os
import re
import uuid
from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager

from aioboto3 import Session
from aiobotocore.client import AioBaseClient
from fastapi import UploadFile
from pydantic_settings import BaseSettings
from pydantic_settings import SettingsConfigDict


class S3Settings(BaseSettings):
    """Настройки подключения к S3-совместимому хранилищу (MinIO, AWS S3, Ceph).

    По умолчанию читает переменные `S3_ACCESS_KEY`, `S3_ACCESS_SECRET_KEY`,
    `S3_BUCKET`, `S3_ENDPOINT`, `S3_REGION`, `S3_USE_SSL` из окружения или `.env`.
    """

    model_config = SettingsConfigDict(
        env_prefix="S3_",
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    ACCESS_KEY: str
    ACCESS_SECRET_KEY: str
    BUCKET: str
    ENDPOINT: str
    REGION: str = "us-east-1"
    USE_SSL: bool = True

    @classmethod
    def from_prefix(cls, prefix: str = "S3_") -> "S3Settings":
        """Загружает настройки S3 с произвольным префиксом переменных окружения.

        Args:
            prefix: Префикс переменных окружения (например, `"MEDIA_S3_"`).

        Returns:
            Экземпляр настроек `S3Settings`.
        """

        class PrefixedS3Settings(cls):  # type: ignore[valid-type, misc]
            model_config = SettingsConfigDict(
                env_prefix=prefix,
                env_file=".env",
                env_file_encoding="utf-8",
                extra="ignore",
            )

        return PrefixedS3Settings()


class S3Storage:
    """Асинхронный клиент для загрузки, замены и удаления файлов в S3-хранилище.

    Автоматически санитизирует имена файлов, генерирует уникальные ключи
    с помощью UUID и формирует публичные ссылки.

    Attributes:
        settings: Конфигурация подключения `S3Settings`.
        bucket: Имя целевого S3-бакета.
        endpoint: Базовый URL S3-сервера.
    """

    _SAFE_FILENAME_RE = re.compile(r"[^\w\-.]")

    def __init__(
        self,
        settings: S3Settings | None = None,
        env_prefix: str = "S3_",
    ) -> None:
        """Инициализирует клиент S3-хранилища из переданных настроек или `.env`.

        Args:
            settings: Готовый объект `S3Settings`. Если не передан, загружается
                из переменных окружения по префиксу `env_prefix`.
            env_prefix: Префикс переменных окружения (по умолчанию `"S3_"`).
        """
        self.settings = settings or S3Settings.from_prefix(env_prefix)
        self.session = Session(
            aws_access_key_id=self.settings.ACCESS_KEY,
            aws_secret_access_key=self.settings.ACCESS_SECRET_KEY,
            region_name=self.settings.REGION,
        )
        self.bucket = self.settings.BUCKET
        self.endpoint = self.settings.ENDPOINT
        self.use_ssl = self.settings.USE_SSL

    def _sanitize_filename(self, filename: str | None) -> str:
        """Очищает имя файла от небезопасных символов и скрытых префиксов."""
        name = os.path.basename(filename or "file")
        name = self._SAFE_FILENAME_RE.sub("_", name)
        name = name.lstrip(".")
        return name or "file"

    def _get_secure_name(self, filename: str | None, folder: str = "files") -> str:
        """Формирует уникальный безопасный ключ объекта внутри бакета на базе UUID."""
        safe_name = self._sanitize_filename(filename)
        unique = uuid.uuid4().hex
        clean_folder = folder.strip("/")
        if clean_folder:
            return f"{clean_folder}/{unique}_{safe_name}"
        return f"{unique}_{safe_name}"

    def _build_public_url(self, key: str) -> str:
        """Собирает публичный URL загруженного объекта."""
        base = self.endpoint.rstrip("/")
        return f"{base}/{self.bucket}/{key}"

    def _extract_key(self, file_url: str) -> str:
        """Извлекает полный ключ объекта S3 из публичного URL или относительного пути."""
        marker = f"/{self.bucket}/"
        if marker in file_url:
            return file_url.split(marker, maxsplit=1)[1]
        return file_url.lstrip("/")

    @asynccontextmanager
    async def _get_client(self) -> AsyncGenerator[AioBaseClient, None]:
        """Создаёт асинхронный S3-клиент на время выполнения операции."""
        async with self.session.client(
            service_name="s3",
            endpoint_url=self.endpoint,
            use_ssl=self.use_ssl,
        ) as client:
            yield client

    async def upload_file(
        self,
        file: UploadFile,
        folder: str = "files",
    ) -> str:
        """Загружает файл FastAPI `UploadFile` в бакет S3.

        Args:
            file: Загружаемый файл из запроса FastAPI.
            folder: Префикс директории внутри бакета (по умолчанию `"files"`).

        Returns:
            Публичный URL сохранённого файла в S3.

        Raises:
            RuntimeError: При ошибке записи объекта в S3.
        """
        async with self._get_client() as client:
            secure_name = self._get_secure_name(
                filename=file.filename,
                folder=folder,
            )
            file_data = await file.read()
            try:
                await client.put_object(
                    Bucket=self.bucket,
                    Key=secure_name,
                    ContentLength=file.size or len(file_data),
                    ContentType=file.content_type or "application/octet-stream",
                    Body=file_data,
                )
            except Exception as ex:
                raise RuntimeError("Error save file to S3") from ex

            return self._build_public_url(key=secure_name)

    async def remove_file(self, file_url: str) -> str:
        """Удаляет объект из бакета S3 по его публичному URL или ключу.

        Args:
            file_url: Полный URL файла в S3 или ключ объекта внутри бакета.

        Returns:
            Строка `"Ok"` при успешном удалении.

        Raises:
            RuntimeError: При ошибке удаления объекта из S3.
        """
        key = self._extract_key(file_url)
        async with self._get_client() as client:
            try:
                await client.delete_object(Bucket=self.bucket, Key=key)
            except Exception as err:
                raise RuntimeError("Error remove file from S3") from err

            return "Ok"

    async def check_file(
        self,
        obj_picture: str | None = None,
        picture: UploadFile | None = None,
        folder: str = "files",
    ) -> str | None:
        """Синхронизирует файл при обновлении сущности (загрузка, замена или удаление).

        Args:
            obj_picture: Текущий URL файла, сохранённый в БД (если есть).
            picture: Новый файл из запроса (если передан).
            folder: Префикс директории внутри бакета (по умолчанию `"files"`).

        Returns:
            Новый URL файла после загрузки/замены или `None`, если файл удалён/отсутствует.
        """
        if obj_picture is not None and picture is not None:
            await self.remove_file(obj_picture)
            return await self.upload_file(file=picture, folder=folder)
        if obj_picture is not None and picture is None:
            await self.remove_file(obj_picture)
            return None
        if obj_picture is None and picture is not None:
            return await self.upload_file(file=picture, folder=folder)
        return None


def get_s3_storage(env_prefix: str = "S3_") -> S3Storage:
    """Фабрика для создания экземпляра `S3Storage` из переменных окружения.

    Удобна для использования в качестве FastAPI-зависимости `Depends(get_s3_storage)`.

    Args:
        env_prefix: Префикс переменных окружения (по умолчанию `"S3_"`).

    Returns:
        Настроенный клиент `S3Storage`.
    """
    return S3Storage(env_prefix=env_prefix)

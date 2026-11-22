from typing import Any
from typing import Literal

from pydantic import BaseModel

from my_sdk.repositories import RepositoryBase


class ServiceBase:
    """Базовый сервисный слой для работы с доменными сущностями через репозиторий.

    Инкапсулирует типовые операции жизненного цикла сущности (создание,
    обновление и удаление) и делегирует их в переданный `RepositoryBase`.

    Attributes:
        repository: Экземпляр репозитория, наследующегося от `RepositoryBase`.
    """

    def __init__(self, repository: RepositoryBase) -> None:
        """Инициализирует базовый сервис.

        Args:
            repository: Экземпляр репозитория для доступа к данным.
        """
        self.repository = repository

    async def manage_obj(
        self,
        action: Literal["create", "update", "remove"],
        schema: BaseModel | None = None,
        obj_id: int | None = None,
        exclude_unset: bool = False,
        commit: bool = True,
    ) -> Any:
        """Выполняет единую операцию создания, обновления или удаления объекта.

        Args:
            action: Тип действия (`"create"`, `"update"` или `"remove"`).
            schema: Pydantic-схема с данными для создания или обновления.
            obj_id: Идентификатор целевой записи (обязателен для `"update"` и `"remove"`).
            exclude_unset: При обновлении игнорировать поля, не переданные явно.
            commit: Фиксировать ли транзакцию сразу после выполнения операции.

        Returns:
            Созданный/обновлённый объект модели или результат удаления из репозитория.

        Raises:
            ValueError: Если для `"create"` не передана `schema` или для
                `"update"`/`"remove"` не передан `obj_id`.
        """
        match action:
            case "create":
                if schema is None:
                    raise ValueError("Parameter 'schema' is required for 'create' action")
                return await self.repository.create(schema=schema, commit=commit)

            case "update":
                if obj_id is None or schema is None:
                    raise ValueError("Parameters 'obj_id' and 'schema' are required for 'update' action")
                return await self.repository.update(
                    schema=schema,
                    commit=commit,
                    exclude_unset=exclude_unset,
                    obj_id=obj_id,
                )

            case "remove":
                if obj_id is None:
                    raise ValueError("Parameter 'obj_id' is required for 'remove' action")
                return await self.repository.delete(obj_id=obj_id, commit=commit)

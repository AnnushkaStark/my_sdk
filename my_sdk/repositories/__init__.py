from collections.abc import Sequence
from typing import Any

from pydantic import BaseModel
from sqlalchemy import delete
from sqlalchemy import insert
from sqlalchemy import select
from sqlalchemy import update
from sqlalchemy.ext.asyncio import AsyncSession

from my_sdk.databases.pg import Base


class RepositoryBase:
    """Базовый асинхронный CRUD-репозиторий для моделей SQLAlchemy.

    Предоставляет стандартный набор операций чтения, создания, массовой вставки,
    обновления и удаления записей без привязки к конкретной предметной области.

    Attributes:
        session: Асинхронная сессия SQLAlchemy (`AsyncSession`).
        model: Класс декларативной модели SQLAlchemy.
    """

    def __init__(self, session: AsyncSession, model: Base) -> None:
        """Инициализирует репозиторий.

        Args:
            session: Активная асинхронная сессия базы данных.
            model: Класс модели SQLAlchemy, с которой работает репозиторий.
        """
        self.session = session
        self.model = model

    async def create(self, schema: BaseModel, commit: bool = True) -> Base | None:
        """Создаёт новую запись в таблице из Pydantic-схемы.

        Args:
            schema: Pydantic-схема с данными новой сущности.
            commit: Фиксировать ли транзакцию сразу после вставки.

        Returns:
            Созданный экземпляр модели.
        """
        result = await self.session.execute(
            insert(self.model).values(schema.model_dump(exclude_unset=True, exclude_none=True)).returning(self.model)
        )
        if commit:
            await self.session.commit()
        return result.scalar_one_or_none()

    async def create_bulk(self, schemas: Sequence[BaseModel], commit: bool = True) -> list[Base]:
        """Выполняет массовую вставку записей из списка Pydantic-схем.

        Args:
            schemas: Последовательность Pydantic-схем для вставки.
            commit: Фиксировать ли транзакцию сразу после вставки.

        Returns:
            Список созданных экземпляров модели.
        """
        if not schemas:
            return []

        data = [s.model_dump() for s in schemas]
        objs = await self.session.execute(insert(self.model).values(data).returning(self.model))
        if commit:
            await self.session.commit()
        return list(objs.scalars().all())

    async def update(
        self,
        schema: BaseModel,
        obj_id: Any,
        commit: bool = True,
        exclude_unset: bool = False,
    ) -> Base | None:
        """Обновляет запись по её первичному ключу `id`.

        Args:
            schema: Pydantic-схема с обновляемыми полями.
            obj_id: Идентификатор обновляемой записи.
            commit: Фиксировать ли транзакцию сразу после обновления.
            exclude_unset: Игнорировать ли поля схемы, не переданные явно.

        Returns:
            Обновлённый экземпляр модели или `None`, если запись не найдена.
        """
        result = await self.session.execute(
            update(self.model)
            .values(**schema.model_dump(exclude_unset=exclude_unset))
            .where(self.model.id == obj_id)
            .returning(self.model)
        )
        if commit:
            await self.session.commit()
        return result.scalar_one_or_none()

    async def partial_update(
        self,
        obj_id: Any,
        new_value: Any,
        value_name: str,
        commit: bool = True,
    ) -> Base | None:
        """Точечно обновляет одно поле записи по её идентификатору.

        Args:
            obj_id: Идентификатор целевой записи.
            new_value: Новое значение поля.
            value_name: Имя атрибута модели для обновления.
            commit: Фиксировать ли транзакцию сразу после изменения.

        Returns:
            Обновлённый экземпляр модели или `None`, если запись не найдена.
        """
        obj = await self.get_by_id(obj_id=obj_id)
        if obj is not None:
            setattr(obj, value_name, new_value)
            if commit:
                await self.session.commit()

        return obj

    partitial_update = partial_update

    async def delete(self, obj_id: Any, commit: bool = True) -> None:
        """Удаляет запись из таблицы по её идентификатору `id`.

        Args:
            obj_id: Идентификатор удаляемой записи.
            commit: Фиксировать ли транзакцию сразу после удаления.
        """
        statement = delete(self.model).where(self.model.id == obj_id)
        await self.session.execute(statement)
        if commit:
            await self.session.commit()

    async def get_by_id(self, obj_id: Any) -> Base | None:
        """Возвращает запись по её идентификатору `id`.

        Args:
            obj_id: Значение первичного ключа `id`.

        Returns:
            Экземпляр модели или `None`, если запись не найдена.
        """
        result = await self.session.execute(select(self.model).where(self.model.id == obj_id))
        return result.scalar_one_or_none()

    async def get_multi_by_ids(self, ids: Sequence[Any] | None) -> list[Base]:
        """Возвращает список записей по коллекции идентификаторов `id`.

        Args:
            ids: Последовательность идентификаторов для выборки.

        Returns:
            Список найденных экземпляров модели.
        """
        if not ids:
            return []

        result = await self.session.execute(select(self.model).where(self.model.id.in_(ids)))
        return list(result.scalars().all())

    async def get_active_by_id(self, obj_id: Any) -> Base | None:
        """Возвращает активную запись (`is_active=True`) по её идентификатору.

        Args:
            obj_id: Идентификатор целевой записи.

        Returns:
            Активный экземпляр модели или `None`, если запись не найдена или неактивна.
        """
        result = await self.session.execute(
            select(self.model).where(
                self.model.id == obj_id,
                self.model.is_active.is_(True),
            )
        )
        return result.scalar_one_or_none()

    async def get_by_field(self, field_name: str, value: Any) -> Base | None:
        """Возвращает первую запись, у которой указанное поле равно `value`.

        Args:
            field_name: Название колонки/атрибута модели.
            value: Искомое значение поля.

        Returns:
            Экземпляр модели или `None`, если совпадений нет.
        """
        column = getattr(self.model, field_name)
        result = await self.session.execute(select(self.model).where(column == value))
        return result.scalar_one_or_none()

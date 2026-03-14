from collections.abc import Mapping, Sequence
from typing import Any

from pydantic import BaseModel
from sqlalchemy import Select, func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import Mapper
from sqlalchemy.orm.strategy_options import _AbstractLoad
from sqlalchemy.sql.elements import ColumnElement, literal_column

from .dbm import BasicDBM
from .validate import validate_kwargs


class NotFoundError(KeyError):
	pass


_DOP = BaseModel | dict[str, Any]


class BaseRepository[M: BasicDBM, PK]:
	model: type[M]

	def __init__(self, session: AsyncSession) -> None:
		self.session = session

	@property
	def _mapper(self) -> Mapper[M]:
		return self.model.__mapper__

	@property
	def _primary_key_cols(self) -> tuple[ColumnElement[Any], ...]:
		return self._mapper.primary_key

	@property
	def _select(self) -> Select[tuple[M]]:
		return select(self.model)

	def _select_where(self, *conditions: Any) -> Select[tuple[M]]:
		return self._select.where(*conditions)

	def _build_primary_key_clause(self, obj_id: PK) -> list[ColumnElement[bool]]:
		return [
			self.model.__mapper__.c[k.key or "-"] == v
			for k, v in zip(
				self._primary_key_cols,
				obj_id if isinstance(obj_id, tuple) else (obj_id,),
				strict=True,
			)
		]

	async def one(
		self,
		obj_id: PK,
		options: Sequence[_AbstractLoad] | None = None,
	) -> M | None:
		stmt = self._select_where(*self._build_primary_key_clause(obj_id))
		if options:
			stmt = stmt.options(*options)
		return await self.session.scalar(stmt)

	async def exists(self, obj_id: PK) -> bool:
		return bool(
			await self.session.scalar(
				select(func.count(literal_column("1")))
				.select_from(self.model)
				.where(*self._build_primary_key_clause(obj_id))
			)
			or 0
		)

	async def create(self, **attrs: Any) -> M:
		validate_kwargs(model=self.model, kwargs=attrs, mode="required")

		instance = self.model(**attrs)
		self.session.add(instance)

		await self.session.flush()
		await self.session.refresh(instance)

		return instance

	async def update(self, obj_id: PK, strict: bool = True, **attrs: Any) -> M:
		instance = await self.one(obj_id)
		if instance is None:
			raise NotFoundError(obj_id)

		instance.merge(strict=strict, **attrs)

		await self.session.flush()
		await self.session.refresh(instance)

		return instance

	async def delete(self, obj_id: PK) -> None:
		instance = await self.one(obj_id)
		if instance is None:
			raise NotFoundError(obj_id)

		await self.session.delete(instance)
		await self.session.flush()

	async def create_many(self, items: Sequence[_DOP]) -> Sequence[M]:
		_mp_reprs = []
		for kwargs in items:
			_mp = kwargs if isinstance(kwargs, Mapping) else kwargs.model_dump(mode="python")
			validate_kwargs(model=self.model, kwargs=_mp, mode="required")
			_mp_reprs.append(_mp)

		instances = [self.model(**_mp) for _mp in _mp_reprs]
		self.session.add_all(instances)
		await self.session.flush()

		for instance in instances:
			await self.session.refresh(instance)

		return instances

	async def delete_many(self, obj_ids: Sequence[PK], strict: bool = True) -> None:
		"""
		Delete many instances by their primary keys

		Args:
			obj_ids: ids of instances
			strict: if to raise if instance is not found

		Raises:
			NotFoundError: if instance is not found and strict is True

		"""

		instances = []
		for obj_id in obj_ids:
			instance = await self.one(obj_id)
			if instance is None and strict:
				raise NotFoundError(obj_id)
			if instance is not None:
				instances.append(instance)

		for instance in instances:
			await self.session.delete(instance)

		await self.session.flush()

	async def many(
		self,
		where: Sequence[ColumnElement[bool]] | None = None,
		options: Sequence[_AbstractLoad] | None = None,
		page: int = 1,
		page_size: int | None = None,
		unique: bool = False,
	) -> Sequence[M]:
		"""Select many instances of `M`

		Args:
			where (Sequence[ColumnElement[bool]] | None, optional): Additional clauses to .where. Defaults to None.
			options (Sequence[Load] | None, optional): Relationships to load. Defaults to None.
			page (int, optional). Defaults to 1.
			page_size (int | None, optional). Defaults to None.
			unique (bool, optional): If .unique() should be called on result. Defaults to False.

		Returns:
			Sequence[M]: _description_
		"""
		stmt = select(self.model)

		if where is not None:
			stmt = stmt.where(*where)

		if options:
			stmt = stmt.options(*options)

		if page is not None and page_size is not None:
			stmt = stmt.offset((page - 1) * page_size).limit(page_size)

		result = await self.session.scalars(stmt)

		if unique:
			result = result.unique()

		return result.all()

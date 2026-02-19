from __future__ import annotations

from collections.abc import Mapping, Sequence
from typing import TYPE_CHECKING, Any

from pydantic import BaseModel, PositiveInt
from sqlalchemy import Select, func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import Mapper
from sqlalchemy.sql.elements import ColumnElement, literal_column

from .validate import validate_kwargs

if TYPE_CHECKING:
	from sqlalchemy.orm.strategy_options import _AbstractLoad

	from .dbm import BasicDBM


class NotFoundError(KeyError):
	pass


_DOP = BaseModel | Mapping[str, Any]


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
			for k, v in zip(self._primary_key_cols, obj_id if isinstance(obj_id, tuple) else (obj_id,), strict=True)
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
		return (
			await self.session.scalar(
				select(func.count(literal_column("1")))
				.select_from(self.model)
				.where(*self._build_primary_key_clause(obj_id))
			)
			or 0
		) > 0

	async def create(self, **attrs: Any) -> M:
		validate_kwargs(model=self.model, kwargs=attrs, mode="required")

		instance = self.model(**attrs)  # noqa
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
		_mp_reprs: list[Mapping[str, Any]] = []
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

	async def delete_many(self, obj_ids: Sequence[PK]) -> None:
		"""
		*Delete many instances by their primary keys*

		#### Parameters

		- **obj_ids**: `Sequence[PK]` - primary keys \\_0_\

		"""

		instances: list[M] = []
		for obj_id in obj_ids:
			instance = await self.one(obj_id)
			if instance is None:
				raise NotFoundError(obj_id)
			instances.append(instance)

		for instance in instances:
			await self.session.delete(instance)

		await self.session.flush()

	async def many(
		self,
		where: Sequence[ColumnElement[bool]] | None = None,
		options: Sequence[_AbstractLoad] | None = None,
		page: PositiveInt = 1,
		page_size: PositiveInt | None = None,
		unique: bool = False,
	) -> Sequence[M]:
		"""
		*Get all instances of `M` by predicate, preload relationships, paginate and filter by uniqueness*

		#### Parameters

		- **where**: `Sequence[ColumnElement[bool]]` - sequence of predicates to use with query
		- **options**: `Sequence[selectinload | joinedload...]` - sequence of realtionship loads to apply to query
		- **page**: `int` - (>0) query page
		- **page_size**: `int` - (>0) query page size
		- **unique**: `bool` - whether to return unique results

		**Return type**: `Sequence[M]`

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

		return result.all() or []

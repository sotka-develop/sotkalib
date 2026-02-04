from typing import Any

from sqlalchemy import inspect
from sqlalchemy.orm import DeclarativeBase


class BasicDBM(DeclarativeBase):
	__abstract__ = True
	__table_args__ = {"extend_existing": True}

	def dict(self, **kw) -> dict[str, Any]:
		result = {field.name: getattr(self, field.name) for field in self.__table__.c}
		if kw is not None:
			result.update(kw)
		return result

	def attribute_loaded(self, key: str):
		if key not in (k := {c.key for c in inspect(self).mapper.all_orm_descriptors}):  # type:ignore
			raise KeyError(k)
		return key not in inspect(self).unloaded

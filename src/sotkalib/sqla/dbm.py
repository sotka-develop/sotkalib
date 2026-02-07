from typing import Any, Self

from pydantic import BaseModel
from sqlalchemy import inspect
from sqlalchemy.orm import DeclarativeBase


class BasicDBM(DeclarativeBase):
	__abstract__ = True
	__table_args__ = {"extend_existing": True}

	def dict(
		self: Self,
		*,
		pydantic_model: type[BaseModel] | None = None,
		explicitly_include: list[str] | None = None,
		**explicitly_set,
	) -> dict[str, Any]:
		if explicitly_include is None:
			explicitly_include = []

		if explicitly_include and pydantic_model:
			# assuming that user wants explicitly included fields only and only those that are in the model
			include = set(explicitly_include).intersection(*pydantic_model.model_fields.keys())
		elif pydantic_model is not None:
			include = set(pydantic_model.model_fields.keys())
		else:
			include = set(explicitly_include)

		result = {}

		for field in self.__table__.c:
			# if include is empty dumping all columns to result
			if not include or field.name in include:
				result[field.name] = getattr(self, field.name)

		# checking include if it has any attrs left, that are not columns of DBM (e.g. property, smth else)
		# diffing explicitly_set because those would be overwritten anyway
		for k in set(include).difference(*result.keys()).difference(*explicitly_set.keys()):
			if hasattr(self, k):
				result[k] = getattr(self, k)

		result.update(explicitly_set)

		return result

	def is_loaded(self, *, attr: str):
		if attr not in (k := {c.key for c in inspect(self).mapper.all_orm_descriptors}):  # type:ignore
			raise KeyError(k)
		return attr not in inspect(self).unloaded

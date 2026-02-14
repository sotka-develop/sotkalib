from collections.abc import Mapping, Sequence
from typing import Any, Literal

from sqlalchemy import Column
from sqlalchemy.orm import DeclarativeBase


def _autoset(c: Column[Any]) -> bool:
	return (
		c.default is not None
		or c.server_default is not None
		or issubclass(c.type.python_type, int)
		or c.autoincrement is True
	)


def _extract_reqd(model: type[DeclarativeBase]) -> Sequence[Column[Any]]:
	_mp = model.__mapper__
	return [c for c in _mp.c if not _autoset(c) and (c in _mp.primary_key or not getattr(c, "nullable", True))]


def validate_kwargs[T: DeclarativeBase](
	*, model: type[T], kwargs: Mapping[str, Any], mode: Literal["required", "no_pk", "loose"] = "required", **_: Any
) -> None:
	if getattr(model, "__abstract__", False) and not getattr(model, "__tablename__", ""):
		raise TypeError(f"{type(model)} should be a child non-abstract instance of sqlalchemy.DeclarativeBase")

	keyset = set(kwargs.keys())

	if mode == "required" and not {c.name for c in _extract_reqd(model)}.issubset(keyset):
		raise KeyError(
			f"required columns not specified, req={[c.name for c in _extract_reqd(model)]}, kw={kwargs.keys()}"
		)

	_mp = model.__mapper__

	if mode == "no_pk" and {c.name for c in _mp.c if c in _mp.primary_key and _autoset(c)} & keyset:
		raise KeyError("autoset pk specified")

	if keyset & {c.name for c in model.__mapper__.c} != keyset:
		raise KeyError(f"some cols are not member of {model} class: {keyset - {c.name for c in model.__mapper__.c}}")

from collections.abc import Generator, Sequence
from contextlib import contextmanager
from typing import Literal
from warnings import warn


@contextmanager
def suppress(
	mode: Literal["all", "exact"] = "all", exact_types: Sequence[type[BaseException]] | None = None
) -> Generator[None]:
	if exact_types is None:
		if mode == "exact":
			warn("mode = 'exact' and excts = None is passed to suppress, bubbling exception up", stacklevel=2)
		exact_types = ()

	try:
		yield
	except Exception as exc:
		if mode == "all":
			return

		if mode == "exact" and type(exc) in exact_types:
			return

		raise exc


def or_raise[T](v: T | None, msg: str = "v is None") -> T:
	if v is None:
		raise ValueError(msg)

	return v


def type_or_raise[T](v: object, exp: type[T], msg: str | None = None) -> T:
	if not isinstance(v, exp):
		raise TypeError(msg or f"want {exp}, got {type(v)}")
	return v

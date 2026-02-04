from warnings import warn
from typing import Generator
from typing import Literal
from typing import Sequence
from contextlib import contextmanager


@contextmanager
def suppress(
	mode: Literal["all", "exact"] = "all", excts: Sequence[type[BaseException]] | None = None
) -> Generator[None]:
	if excts is None:
		if mode == "exact":
			warn("mode = 'exact' and excts = None is passed to suppress, bubbling exception up")
		exc_ts = ()
	else:
		exc_ts = excts

	try:
		yield None
	except Exception as exc:
		if mode == "all":
			return

		if mode == "exact" and type(exc) in exc_ts:
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

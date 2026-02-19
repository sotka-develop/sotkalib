import typing
from collections.abc import Callable

from .unset import Unset, is_set

_hints_cache: dict[type, dict] = {}
# dunders that are inherent to Protocol itself and class infrastructure
# — present on protocol classes but not user-defined members
_skip_dunders = frozenset(dir(typing.Protocol)) | frozenset(
	{
		"__weakref__",
		"__dict__",
		"__annotations__",
		"__abstractmethods__",
		"__slots__",
	}
)

type MethodKind = typing.Literal["method", "static", "classmethod", "property"]


def _get_protocol_members(protocol: type) -> dict[str, typing.Any]:
	return {
		name: obj
		for name in getattr(protocol, "__protocol_attrs__", [])
		if _should_check(name) and is_set(obj := getattr(protocol, name, Unset))
	} | {name: obj for name in dir(protocol) if _should_check(name) and is_set(obj := getattr(protocol, name, Unset))}


def _should_check(name: str) -> bool:
	if not name.startswith("_"):
		return True
	if name.startswith("__") and name.endswith("__"):
		return name not in _skip_dunders
	return False


def _get_type_hints(cls: type | Callable) -> dict:
	try:
		return typing.get_type_hints(cls)
	except Exception as e:
		_ = e
		return {}


def _unwrap_method(obj: typing.Any) -> tuple[typing.Any, MethodKind]:
	if isinstance(obj, staticmethod):
		return obj.__func__, "static"
	if isinstance(obj, classmethod):
		return obj.__func__, "classmethod"
	if isinstance(obj, property):
		return obj.fget, "property"
	return obj, "method"


def _get_raw(cls: type, name: str) -> typing.Any:
	"""get the raw descriptor from mro bypassing __get__"""
	for base in cls.__mro__:
		if name in base.__dict__:
			return base.__dict__[name]
	return Unset

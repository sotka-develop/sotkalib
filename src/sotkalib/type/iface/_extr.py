import typing
from collections.abc import Callable

from sotkalib.type.unset import Unset

_typing_internals = frozenset(
	{
		"__parameters__",
		"__orig_bases__",
		"__orig_class__",
		"_is_protocol",
		"_is_runtime_protocol",
		"__protocol_attrs__",
		"__non_callable_proto_members__",
		"__type_params__",
	}
)

_special_names = frozenset(
	{
		"__abstractmethods__",
		"__annotations__",
		"__dict__",
		"__doc__",
		"__init__",
		"__module__",
		"__new__",
		"__slots__",
		"__subclasshook__",
		"__weakref__",
		"__class_getitem__",
		"__match_args__",
		"__static_attributes__",
		"__firstlineno__",
	}
)

# These special attributes will be not collected as protocol members.
_skip_dunder = _typing_internals | _special_names | {"_MutableMapping__marker"}

type MethodKind = typing.Literal["method", "static", "classmethod", "property"]


def _get_protocol_members(protocol: type) -> dict[str, typing.Any]:
	"""Collect protocol members from a protocol class objects.

	This includes names actually defined in the class dictionary, as well
	as names that appear in annotations. Special names (above) are skipped.

	# std:typing.py, L1939
	"""
	attrs = {}
	for base in protocol.__mro__[:-1]:  # without object
		if base.__name__ in {"Protocol", "Generic"}:
			continue
		annotations = getattr(base, "__annotations__", {})
		for attr in (*base.__dict__, *annotations):
			if not attr.startswith("_abc_") and attr not in _skip_dunder:
				# Use __dict__ value if present; for annotation-only members store None

				attrs[attr] = base.__dict__.get(attr) if attr in base.__dict__ else None

	return attrs


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

import types
import typing
from contextvars import ContextVar

_COMPAT_CHECKING: ContextVar[set[tuple[int, int]]] = ContextVar("_COMPAT_CHECKING")


def _raise_if_not_proto(typ: type):  # pragma: no cover
	if not getattr(typ, "_is_protocol", False):  # std:typing.py, L2360
		raise TypeError(f"expected protocol as a class to check against, found {type(typ)}")


def _tname(typ: typing.Any) -> str:
	return str(typ) if not hasattr(typ, "__name__") else typ.__name__


def _is_union(origin: typing.Any) -> bool:
	return origin is typing.Union or origin is types.UnionType


class _splittype:  # noqa: N801
	__slots__ = ("origin", "args")

	def __init__(self, typ: typing.Any) -> None:
		self.origin = typing.get_origin(typ)
		self.args = typing.get_args(typ)


def _is_proto(typ: typing.Any) -> bool:
	return isinstance(typ, type) and getattr(typ, "_is_protocol", False) and typ is not typing.Protocol


def _proto_compat(want: type, have: typing.Any) -> bool:
	from ._impl import implements  # noqa  lazy import to avoid circular dep

	pair = (id(want), id(have))
	try:
		checking = _COMPAT_CHECKING.get()
	except LookupError:
		checking = set()
		_COMPAT_CHECKING.set(checking)

	if pair in checking:
		return True  # break recursion cycle

	checking.add(pair)
	try:
		shtyp = _splittype(have)
		if _is_union(shtyp.origin):
			return all(_proto_compat(want, member) for member in shtyp.args)

		if isinstance(have, type):
			return implements(have, want, early=True)

		return False
	finally:
		checking.discard(pair)


def _generic_compat(swtyp: _splittype, shtyp: _splittype, strict: bool) -> bool:
	"""origin equal generic check. Asymmetric: want=bare accepts have=parameterized, not reverse."""
	if not swtyp.args and shtyp.args:
		return True
	if swtyp.args and not shtyp.args:
		return False
	return all(compatible(w, h, strict=strict) for w, h in zip(swtyp.args, shtyp.args, strict=False))


def compatible(want_typ: typing.Any, have_typ: typing.Any, *, strict: bool = False) -> bool:  # noqa
	# identity / Any
	if want_typ is have_typ or want_typ is typing.Any or have_typ is typing.Any:
		return True

	# protocol check
	if _is_proto(want_typ):
		return _proto_compat(want_typ, have_typ)

	swtyp, shtyp = _splittype(want_typ), _splittype(have_typ)

	# both unions
	if _is_union(swtyp.origin) and _is_union(shtyp.origin):
		# ALL union mbrs of `have` should be compatible with AT LEAST ONE union mbr of `have`.
		return all(any(compatible(p, t, strict=strict) for t in shtyp.args) for p in swtyp.args)

	# have is oneof, want is not — every member must be compatible with want
	if _is_union(shtyp.origin) and not _is_union(swtyp.origin):
		return all(compatible(want_typ, h, strict=strict) for h in shtyp.args)

	# want is oneof, have is not — have must match at least one alternative
	if _is_union(swtyp.origin) and not _is_union(shtyp.origin):
		return any(compatible(w, have_typ, strict=strict) for w in swtyp.args)

	# same-origin generics
	if swtyp.origin is not None and swtyp.origin == shtyp.origin:
		return _generic_compat(swtyp, shtyp, strict)

	# cross-origin generics — have's origin is subclass of want's origin (e.g. list[int] → Sequence[int])
	if (
		swtyp.origin is not None
		and shtyp.origin is not None
		and isinstance(swtyp.origin, type)
		and isinstance(shtyp.origin, type)
		and issubclass(shtyp.origin, swtyp.origin)
	):
		return _generic_compat(swtyp, shtyp, strict)

	# want is parameterized, have is bare type matching origin
	if swtyp.origin is not None and shtyp.origin is None and swtyp.origin is have_typ:
		return False

	# want is bare type, have is parameterized with want as origin
	if swtyp.origin is None and shtyp.origin is want_typ:
		return True

	# concrete issubclass
	try:
		if isinstance(want_typ, type) and isinstance(have_typ, type):
			return issubclass(have_typ, want_typ)
	except TypeError:
		pass

	# fallback
	return not strict

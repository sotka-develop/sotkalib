import types
import typing


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


def _compatible(ptyp: typing.Any, ttyp: typing.Any) -> bool:
	if ptyp is ttyp or ptyp is typing.Any or ttyp is typing.Any:
		return True

	_spt_ptyp, _spt_ttyp = _splittype(ptyp), _splittype(ttyp)

	# two `|` annots, should check that actual covers expected
	if _is_union(_spt_ptyp.origin) and _is_union(_spt_ttyp.origin):
		return all(any(_compatible(p, t) for t in _spt_ttyp.args) for p in _spt_ptyp.args)

	# same origin, should check deeper
	if _spt_ptyp.origin is not None and _spt_ptyp.origin == _spt_ttyp.origin:
		if not _spt_ptyp.args or not _spt_ttyp.args:
			# one origin has unspecified type arguments, so its compatible either way
			return True
		return all(_compatible(p, t) for p, t in zip(_spt_ptyp.args, _spt_ttyp.args, strict=False))

	try:
		if isinstance(ptyp, type) and isinstance(ttyp, type):
			# class compat check
			return issubclass(ttyp, ptyp)
	except TypeError:
		pass

	return True

from typing import Literal, Protocol, _ProtocolMeta, overload

from ._checkers import (
	_attrs_incompat,
	_check_callable,
	_check_method_kind,
	_check_missing,
	_check_property,
)
from ._compat import (
	_compatible,
	_raise_if_not_proto,
	_tname,
)
from ._extr import _get_protocol_members, _get_raw, _get_type_hints, _unwrap_method
from .unset import Unset, is_set


class DoesNotImplementError(BaseException):
	violations: list[str]
	proto: type
	target: type

	def __init__(self, violations: list[str], proto: type, failed: type, *args):
		super().__init__(*args)
		self.violations = violations
		self.proto = proto
		self.target = failed

	def __repr__(self) -> str:
		return (
			(
				f"DoesNotImplementError<type=`{self.target.__name__}` does not implement protocol_class=`{self.proto.__name__}`>"
				"\n(violations="
				'\n... "'
			)
			+ '"\n... "'.join(self.violations)
			+ '")'
		)

	__str__ = __repr__


@overload
def implements(  # noqa: PLR0912
	typ: type,
	proto: type,
	*,
	signatures: bool = True,
	type_hints: bool = True,
	strict: bool = False,
	early_escape: Literal[False] = False,
) -> None: ...


@overload
def implements(  # noqa: PLR0912
	typ: type,
	proto: type,
	*,
	signatures: bool = True,
	type_hints: bool = True,
	strict: bool = False,
	early_escape: Literal[True],
) -> bool: ...


def implements(  # noqa: PLR0912
	typ: type,
	proto: type,
	*,
	signatures: bool = True,
	type_hints: bool = True,
	strict: bool = False,
	early_escape: bool = False,
) -> None | bool:
	"""
	check if `typ` implements `proto` at runtime.

	Args:
		typ: the class to check.
		proto: the Protocol class to check against.
		signatures: whether to compare callable signatures.
		type_hints: whether to compare type annotations.
		strict: if True, also flag extra parameters not in protocol.
		early_escape:

	Raises:
		DoesNotImplementError: if `typ` doesn't implement `proto`
	"""
	_viols = []
	_raise_if_not_proto(proto)
	_protombrs = _get_protocol_members(proto)
	_protohints, _typhints = _get_type_hints(proto), _get_type_hints(typ)

	for name, protombr in _protombrs.items():
		typmbr = getattr(typ, name, Unset)

		# --- missing ---
		if not is_set(typmbr):
			if viol := _check_missing(name, proto, _protohints, _typhints):
				if early_escape:
					return False

				_viols.append(viol)
			continue

		proto_unwrapped, proto_kind = _unwrap_method(_get_raw(proto, name))
		typ_unwrapped, typ_kind = _unwrap_method(v if is_set(v := _get_raw(typ, name)) else typmbr)

		# --- property ---
		if proto_kind == "property":
			viols = _check_property(
				name=name,
				proto_fn=proto_unwrapped,
				typ_kind=typ_kind,
				typmbr=typ_unwrapped,
				protohints=_protohints,
				typhints=_typhints,
				check_hints=type_hints,
			)

			if viols and early_escape:
				return False

			_viols.extend(viols)
			continue

		# --- static/classmethod kind ---
		if viol := _check_method_kind(name, proto_kind, typ_kind):
			if early_escape:
				return False

			_viols.append(viol)
			continue

		# --- callable ---
		if callable(protombr):
			if not callable(typmbr):
				if early_escape:
					return False

				_viols.append(f"expected `{name}` to be callable, found {type(typmbr).__name__}")
			elif signatures:
				viols = _check_callable(
					name=name,
					protombr=protombr,
					typmbr=typmbr,
					proto_unwrapped=proto_unwrapped,
					typ_unwrapped=typ_unwrapped,
					proto_kind=proto_kind,
					typ_kind=typ_kind,
					strict=strict,
				)

				if viols and early_escape:
					return False

				_viols.extend(viols)
			continue

		# --- data attr ---
		if callable(typmbr):
			if early_escape:
				return False
			_viols.append(f"expected `{name}` to be a data attribute, found callable")
			continue

		if type_hints and _attrs_incompat(name, _protohints, _typhints):
			if early_escape:
				return False
			_viols.append(
				f"expected `{name}` to be of type {_tname(_protohints[name])}, found {_tname(_typhints[name])}"
			)

		# check annotated-only
	for attr, prototyp in _protohints.items():
		if attr in _protombrs or attr.startswith("_"):
			# already checked above OR protected
			continue

		has_attr = hasattr(typ, attr)
		if not has_attr and attr not in _typhints:
			if early_escape:
				return False
			_viols.append(f"expected annotated attribute `{attr}` (type={_tname(prototyp)})")
		elif has_attr and callable(getattr(typ, attr)) and attr not in _typhints:
			if early_escape:
				return False
			_viols.append(f"expected `{attr}` to be a data attribute, found callable")
		elif type_hints and attr in _typhints and not _compatible(prototyp, _typhints[attr]):
			if early_escape:
				return False
			_viols.append(
				f"expected annotated attribute `{attr}` to be of type {_tname(prototyp)}, "
				f"found {_tname(_typhints[attr])}"
			)

	if early_escape:
		return True

	if _viols:
		raise DoesNotImplementError(_viols, proto, typ)

	return None


class _CheckableMeta(_ProtocolMeta):
	def __new__(mcs, name: str, bases: tuple, namespace: dict, **kwargs):
		cls = super().__new__(mcs, name, bases, namespace, **kwargs)
		mcs._protocol_cls = cls
		cls._is_protocol = True  # pyrefly:ignore

		return cls

	def __rmod__(self, other: type) -> bool:
		return implements(other, self._protocol_cls, early_escape=True)


class CheckableProtocol(Protocol, metaclass=_CheckableMeta): ...

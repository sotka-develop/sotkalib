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
	cls: type,
	proto: type,
	*,
	signatures: bool = ...,
	type_hints: bool = ...,
	disallow_extra: bool = ...,
	early: Literal[False] = False,
) -> None: ...


@overload
def implements(  # noqa: PLR0912
	cls: type,
	proto: type,
	*,
	signatures: bool = ...,
	type_hints: bool = ...,
	disallow_extra: bool = ...,
) -> None: ...


@overload
def implements(  # noqa: PLR0912
	cls: type,
	proto: type,
	*,
	signatures: bool = ...,
	type_hints: bool = ...,
	disallow_extra: bool = ...,
	early: Literal[True],
) -> bool: ...


def implements(  # noqa: PLR0912
	cls: type,
	proto: type,
	*,
	signatures: bool = True,
	type_hints: bool = True,
	disallow_extra: bool = False,
	early: bool = False,
) -> bool | None:
	"""
	check if `typ` implements `proto` at runtime.

	Args:
		cls: the class to check.
		proto: the Protocol class to check against.
		signatures: whether to compare callable signatures.
		type_hints: whether to compare type annotations.
		disallow_extra: if True, also flag extra parameters not in protocol.
		early: returns early, as bool

	Raises:
		DoesNotImplementError: if `typ` doesn't implement `proto`
	"""

	if early:
		return _implements_early(
			cls=cls,
			proto=proto,
			signatures=signatures,
			type_hints=type_hints,
			disallow_extra=disallow_extra,
		)

	viols = []
	_raise_if_not_proto(proto)
	protombrs = _get_protocol_members(proto)
	proto_typehints, cls_typehints = _get_type_hints(proto), _get_type_hints(cls)

	for name, protombr in protombrs.items():
		clsmbr = getattr(cls, name, Unset)

		# --- missing ---
		if not is_set(clsmbr):
			if viol := _check_missing(name, proto, proto_typehints, cls_typehints):
				viols.append(viol)
			continue

		protombr_unwrapped, protombr_kind = _unwrap_method(_get_raw(proto, name))
		clsmbr_unwrapped, clsmbr_kind = _unwrap_method(v if is_set(v := _get_raw(cls, name)) else clsmbr)

		# --- property ---
		if protombr_kind == "property":
			if viol := _check_property(
				name=name,
				clsmbr_kind=clsmbr_kind,
				protombr=protombr_unwrapped,
				clsmbr=clsmbr_unwrapped,
				proto_typehints=proto_typehints,
				cls_typehints=cls_typehints,
				type_hints=type_hints,
			):
				viols.extend(viol)
			continue

		# --- static/classmethod kind ---
		if viol := _check_method_kind(name, protombr_kind, clsmbr_kind):
			viols.append(viol)
			continue

		# --- callable ---
		if callable(protombr):
			if viol := _check_callable(
				name=name,
				protombr=protombr,
				clsmbr=clsmbr,
				protombr_unwrapped=protombr_unwrapped,
				clsmbr_unwrapped=clsmbr_unwrapped,
				protombr_kind=protombr_kind,
				clsmbr_kind=clsmbr_kind,
				disallow_extra=disallow_extra,
				signatures=signatures,
			):
				viols.extend(viol)
			continue

		# --- data attr ---
		if callable(clsmbr):
			viols.append(f"expected `{name}` to be a data attribute, found callable")
			continue

		if type_hints and _attrs_incompat(name, proto_typehints, cls_typehints):
			viols.append(
				f"expected `{name}` to be of type {_tname(proto_typehints[name])}, found {_tname(cls_typehints[name])}"
			)

	# check annotated-only
	for attr, protombr_type in proto_typehints.items():
		if attr in protombrs or attr.startswith("_"):
			# already checked above OR protected
			continue

		if viol := _process_annot_attrs(attr, cls, cls_typehints, protombr_type, type_hints):
			viols.append(viol)

	if any(viols):
		raise DoesNotImplementError(viols, proto, cls)

	return None


def _process_annot_attrs(attr: str, cls: type, cls_typehints: dict, protombr_type: type, type_hints: bool):
	if not hasattr(cls, attr) and attr not in cls_typehints:
		return f"expected annotated attribute `{attr}` (type={_tname(protombr_type)})"
	elif hasattr(cls, attr) and callable(getattr(cls, attr)) and attr not in cls_typehints:
		return f"expected `{attr}` to be a data attribute, found callable"
	elif type_hints and attr in cls_typehints and not _compatible(protombr_type, cls_typehints[attr]):
		return f"expected annotated attribute `{attr}` to be of type {_tname(protombr_type)}, found {_tname(cls_typehints[attr])}"

	return None


def _implements_early(  # noqa: PLR0912
	cls: type,
	proto: type,
	*,
	signatures: bool = True,
	type_hints: bool = True,
	disallow_extra: bool = False,
) -> bool:
	"""
	check if `typ` implements `proto` at runtime and exits early by returning a boolean

	Args:
		cls: the class to check.
		proto: the Protocol class to check against.
		signatures: whether to compare callable signatures.
		type_hints: whether to compare type annotations.
		disallow_extra: if True, also flag extra parameters not in protocol.

	Raises:
		DoesNotImplementError: if `typ` doesn't implement `proto`
	"""
	_raise_if_not_proto(proto)
	protombrs = _get_protocol_members(proto)
	proto_typehints, cls_typehints = _get_type_hints(proto), _get_type_hints(cls)

	for name, protombr in protombrs.items():
		clsmbr = getattr(cls, name, Unset)

		# --- missing ---
		if not is_set(clsmbr):
			if _check_missing(name, proto, proto_typehints, cls_typehints):
				return False
			continue

		protombr_unwrapped, protombr_kind = _unwrap_method(_get_raw(proto, name))
		clsmbr_unwrapped, clsmbr_kind = _unwrap_method(v if is_set(v := _get_raw(cls, name)) else clsmbr)

		# --- property ---
		if protombr_kind == "property":
			if _check_property(
				name=name,
				clsmbr_kind=clsmbr_kind,
				protombr=protombr_unwrapped,
				clsmbr=clsmbr_unwrapped,
				proto_typehints=proto_typehints,
				cls_typehints=cls_typehints,
				type_hints=type_hints,
			):
				return False
			continue

		# --- static/classmethod kind ---
		if _check_method_kind(name, protombr_kind, clsmbr_kind):
			return False

		# --- callable ---
		if callable(protombr):
			if _check_callable(
				name=name,
				protombr=protombr,
				clsmbr=clsmbr,
				protombr_unwrapped=protombr_unwrapped,
				clsmbr_unwrapped=clsmbr_unwrapped,
				protombr_kind=protombr_kind,
				clsmbr_kind=clsmbr_kind,
				disallow_extra=disallow_extra,
				signatures=signatures,
			):
				return False
			continue

		# --- data attr ---
		if callable(clsmbr):
			return False

		if type_hints and _attrs_incompat(name, proto_typehints, cls_typehints):
			return False

	# check annotated-only
	for attr, protombr_type in proto_typehints.items():
		if attr in protombrs or attr.startswith("_"):
			# already checked above OR protected
			continue

		if _process_annot_attrs(attr, cls, cls_typehints, protombr_type, type_hints):
			return False

	return True


class _CheckableMeta(_ProtocolMeta):
	def __new__(mcs, name: str, bases: tuple, namespace: dict, **kwargs):
		cls = super().__new__(mcs, name, bases, namespace, **kwargs)
		mcs._protocol_cls = cls
		cls._is_protocol = True  # pyrefly:ignore

		return cls

	def __rmod__(self, other: type) -> bool:
		return implements(other, self._protocol_cls, early=True)


class CheckableProtocol(Protocol, metaclass=_CheckableMeta): ...

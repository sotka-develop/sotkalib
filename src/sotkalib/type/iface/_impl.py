from typing import Any, Literal, TypeIs, overload
from warnings import warn

from sotkalib.type.unset import Unset, is_unset

from ._checkers import (
	_attrs_incompat,
	_check_annot_attrs,
	_check_callable,
	_check_method_kind,
	_check_missing,
	_check_property,
)
from ._compat import (
	_raise_if_not_proto,
	_tname,
)
from ._error import DoesNotImplementError
from ._extr import (
	_get_protocol_members,
	_get_raw,
	_get_type_hints,
	_unwrap_method,
)


@overload
def implements[T: object](
	cls: Any,
	proto: type[T],
	*,
	signatures: bool = ...,
	type_hints: bool = ...,
	disallow_extra: bool = ...,
	early: Literal[False] = False,
	infer: Literal[False] = False,
) -> None: ...


@overload
def implements[T: object](
	cls: type | object,
	proto: type[T],
	*,
	signatures: bool = ...,
	type_hints: bool = ...,
	disallow_extra: bool = ...,
	early: Literal[True],
	infer: bool = ...,
) -> TypeIs[T]: ...


@overload
def implements[T: object](
	cls: type | object,
	proto: type[T],
	*,
	signatures: bool = ...,
	type_hints: bool = ...,
	disallow_extra: bool = ...,
	early: bool = ...,
	infer: Literal[True],
) -> TypeIs[T]: ...


def implements[T](  # noqa
	cls: Any,
	proto: type[T],
	*,
	signatures: bool = True,
	type_hints: bool = True,
	disallow_extra: bool = False,
	early: bool = False,
	infer: bool = False,
) -> bool | None:
	"""
	check if `cls` implements `proto` at runtime

	Args:
		cls: the type (-instance) to check
		proto: the Protocol class to check against
		signatures: whether to compare callable signatures
		type_hints: whether to compare type annotations
		disallow_extra: if True, also flag extra parameters not in protocol
		early: **deprecated, you may want to use `infer` instead**
		infer: if True, function will return a bool, whether the interface is implemented or not,
			instead of raising an exception

	Raises:
		DoesNotImplementError: if `cls` doesn't implement `proto`
	"""

	if early or infer:
		if early:
			warn(
				"`early` parameter is deprecated and is scheduled for removal in v0.3.0; use `infer` instead",
				stacklevel=2,
				category=DeprecationWarning,
			)
		return _implements_early(
			cls=cls,
			proto=proto,
			signatures=signatures,
			type_hints=type_hints,
			disallow_extra=disallow_extra,
		)

	instance = object()
	if isinstance(cls, object) and not isinstance(cls, type):
		instance = cls
		cls = type(instance)

	viols = []
	_raise_if_not_proto(proto)
	protombrs = _get_protocol_members(proto)
	proto_typehints, cls_typehints = (
		_get_type_hints(proto),
		_get_type_hints(cls),
	)

	for name, protombr in protombrs.items():
		clsmbr = getattr(instance, name, Unset) or getattr(cls, name, Unset)

		# --- missing ---
		if is_unset(clsmbr):
			if viol := _check_missing(name, proto, proto_typehints, cls_typehints):
				viols.append(viol)
			continue

		raw_clsmbr = getattr(instance, name, Unset) or _get_raw(cls, name)
		protombr_unwrapped, protombr_kind = _unwrap_method(_get_raw(proto, name))
		clsmbr_unwrapped, clsmbr_kind = _unwrap_method(raw_clsmbr or clsmbr)

		# --- property ---
		if protombr_kind == "property":
			if viol := _check_property(
				name=name,
				protombr=protombr_unwrapped,
				proto_typehints=proto_typehints,
				clsmbr=clsmbr_unwrapped,
				clsmbr_kind=clsmbr_kind,
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
		if callable(protombr) or callable(protombr_unwrapped):
			if viol := _check_callable(
				name=name,
				protombr=protombr,
				protombr_unwrapped=protombr_unwrapped,
				protombr_kind=protombr_kind,
				clsmbr=clsmbr,
				clsmbr_unwrapped=clsmbr_unwrapped,
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

		if viol := _check_annot_attrs(attr, cls, cls_typehints, protombr_type, type_hints):
			viols.append(viol)

	if any(viols):
		raise DoesNotImplementError(viols, proto, cls)

	return None


def _implements_early[T: object](
	cls: type | object,
	proto: type[T],
	*,
	signatures: bool = True,
	type_hints: bool = True,
	disallow_extra: bool = False,
) -> bool:
	"""
	check if `cls` implements `proto` at runtime and exits early by returning a boolean

	Args:
		cls: the type (-instance) to check
		proto: the Protocol class to check against
		signatures: whether to compare callable signatures
		type_hints: whether to compare type annotations
		disallow_extra: if True, also flag extra parameters not in protocol

	Raises:
		DoesNotImplementError: if `cls` doesn't implement `proto`
	"""
	is_instance = isinstance(cls, object) and not isinstance(cls, type)
	instance: object = cls if is_instance else object()
	if is_instance:
		cls = type(cls)

	_raise_if_not_proto(proto)
	protombrs = _get_protocol_members(proto)
	proto_typehints, cls_typehints = (
		_get_type_hints(proto),
		_get_type_hints(cls),
	)

	for name, protombr in protombrs.items():
		clsmbr = getattr(instance, name, Unset) or getattr(cls, name, Unset)

		# --- missing ---
		if is_unset(clsmbr):
			if _check_missing(name, proto, proto_typehints, cls_typehints):
				return False
			continue

		raw_clsmbr = getattr(instance, name, Unset) or _get_raw(cls, name)
		protombr_unwrapped, protombr_kind = _unwrap_method(_get_raw(proto, name))
		clsmbr_unwrapped, clsmbr_kind = _unwrap_method(raw_clsmbr or clsmbr)

		# --- property ---
		if protombr_kind == "property":
			if _check_property(
				name=name,
				protombr=protombr_unwrapped,
				proto_typehints=proto_typehints,
				clsmbr=clsmbr_unwrapped,
				clsmbr_kind=clsmbr_kind,
				cls_typehints=cls_typehints,
				type_hints=type_hints,
			):
				return False
			continue

		# --- static/classmethod kind ---
		if _check_method_kind(name, protombr_kind, clsmbr_kind):
			return False

		# --- callable ---
		if callable(protombr) or callable(protombr_unwrapped):
			if _check_callable(
				name=name,
				protombr=protombr,
				protombr_unwrapped=protombr_unwrapped,
				protombr_kind=protombr_kind,
				clsmbr=clsmbr,
				clsmbr_unwrapped=clsmbr_unwrapped,
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

		if _check_annot_attrs(attr, cls, cls_typehints, protombr_type, type_hints):
			return False

	return True

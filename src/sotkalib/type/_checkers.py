import inspect
import typing
from collections.abc import Mapping
from inspect import Parameter

from ._compat import _compatible, _tname
from ._extr import MethodKind, _get_raw, _get_type_hints
from .unset import Unset, is_set


def _check_signatures(  # noqa: PLR0912
	name: str,
	protobj: typing.Any,
	typobj: typing.Any,
	strict: bool,
) -> list[str]:
	def _method_sig_params_and_rtyp(typ: typing.Any) -> tuple[Mapping[str, Parameter], typing.Any]:
		try:
			sig = inspect.signature(typ)
		except (ValueError, TypeError):
			return {}, Unset
		param = dict(sig.parameters)
		param.pop("self", None)

		return param, sig.return_annotation

	_viols = []
	_protoparam, _protort = _method_sig_params_and_rtyp(protobj)
	_typparam, _typrt = _method_sig_params_and_rtyp(typobj)

	# check missing parameters
	for pattr, pparam in _protoparam.items():
		if pattr not in _typparam:
			_viols.append(_missing_pattr(_typparam, name, pparam))
			continue

		tparam = _typparam[pattr]

		_viols.append(_check_param_kind(name, tparam, pparam))
		_viols.append(_check_param_annot(name, tparam, pparam))

	if strict:
		# extra params in cls that aren't in protocol
		for pattr, tparam in _typparam.items():
			if pattr not in _protoparam:
				if tparam.kind in (
					inspect.Parameter.VAR_POSITIONAL,
					inspect.Parameter.VAR_KEYWORD,
				):
					continue
				if tparam.default is not inspect.Parameter.empty:
					continue  # has default, so it's okay
				_viols.append(f"unexpected required parameter `{pattr}` on method `{name}`")

	_viols.append(_check_meth_rtype(name, _typrt, _protort))

	return [v for v in _viols if v is not None]


def _missing_pattr(_typparam: Mapping[str, Parameter], name: str, pparam: Parameter) -> str | None:
	# *args/**kwargs in cls can absorb missing named params
	_contains_posvar = any(p.kind == inspect.Parameter.VAR_POSITIONAL for p in _typparam.values())
	_contains_kwargs = any(p.kind == inspect.Parameter.VAR_KEYWORD for p in _typparam.values())
	if pparam.kind == inspect.Parameter.POSITIONAL_OR_KEYWORD:
		if not (_contains_posvar or _contains_kwargs):
			return f"expected parameter `{pparam.name}` on method `{name}`"
	elif pparam.kind == inspect.Parameter.KEYWORD_ONLY:
		if not _contains_kwargs:
			return f"expected keyword parameter `{pparam.name}` on method `{name}`"
		# otherwise absorbed (*, attr: str = None, **kw) vs proto (*, **kw)
	else:
		return f"expected parameter `{pparam.name}` on method `{name}`"

	return None


def _check_meth_rtype(name: str, _trtype: typing.Any, _prtype: typing.Any) -> str | None:
	if (
		is_set(_prtype)
		and _prtype is not inspect.Parameter.empty
		and is_set(_trtype)
		and _trtype is not inspect.Parameter.empty
		and not _compatible(_prtype, _trtype)
	):
		return f"expected {_tname(_prtype)} as a return type of method `{name}`, got {_tname(_trtype)}"
	return None


def _check_param_kind(name: str, tparam: Parameter, pparam: Parameter) -> str | None:
	if not (
		(pparam.kind == tparam.kind)
		or (pparam.kind == Parameter.POSITIONAL_OR_KEYWORD and tparam.kind == Parameter.POSITIONAL_ONLY)
	):
		return (
			f"expected parameter `{pparam.name}` on method `{name}` "
			f"to be of kind {pparam.kind.name}, got {tparam.kind.name}"
		)
	return None


def _check_param_annot(name: str, tparam: Parameter, pparam: Parameter) -> str | None:
	if (
		pparam.annotation is not inspect.Parameter.empty
		and tparam.annotation is not inspect.Parameter.empty
		and not _compatible(pparam.annotation, tparam.annotation)
	):
		return (
			f"expected annotated parameter `{pparam.name}` on method `{name}` "
			f"to be of type {_tname(pparam.annotation)}, got {_tname(tparam.annotation)}"
		)
	return None


def _attrs_incompat(attr: str, pth: dict, tth: dict) -> bool:
	return attr in pth and attr in tth and not _compatible(pth[attr], tth[attr])


def _check_missing(
	name: str,
	proto: type,
	protohints: dict,
	typhints: dict,
	type_hints: bool = True,
) -> str | None:
	raw = _get_raw(proto, name)
	if isinstance(raw, property) and name in typhints:
		# annotation satisfies property, but check type
		if type_hints and raw.fget:
			proto_ret = _get_type_hints(raw.fget).get("return")
			if proto_ret and not _compatible(proto_ret, typhints[name]):
				return f"expected property `{name}` to be of type {_tname(proto_ret)}, got {_tname(typhints[name])}"
		return None
	if name in protohints and name not in typhints:
		return f"expected annotated attribute `{name}` (type={_tname(protohints[name])}), found none"
	return f"expected member `{name}`"


def _check_property(
	name: str,
	proto_fn: typing.Any,
	typ_kind: MethodKind,
	typmbr: typing.Any,
	protohints: dict,
	typhints: dict,
	check_hints: bool,
) -> list[str]:
	if typ_kind == "property":
		return _check_two_props(name, proto_fn, typmbr, check_hints)
	if name not in typhints and is_set(typmbr):
		return []  # has a concrete value, fine
	if name not in typhints:
		return [f"expected property or attribute `{name}`"]
	if not check_hints:
		return []
	# compare types: use protohints if available, otherwise extract from property getter
	proto_type = protohints.get(name)
	if proto_type is None and proto_fn:
		proto_type = _get_type_hints(proto_fn).get("return")
	if proto_type and name in typhints and not _compatible(proto_type, typhints[name]):
		return [f"expected property `{name}` to be of type {_tname(proto_type)}, got {_tname(typhints[name])}"]
	return []


def _check_two_props(
	name: str,
	proto_fget: typing.Any,
	typ_fget: typing.Any,
	check_hints: bool,
) -> list[str]:
	if not check_hints or not proto_fget or not typ_fget:
		return []
	proto_ret = _get_type_hints(proto_fget).get("return")
	typ_ret = _get_type_hints(typ_fget).get("return")
	if proto_ret and typ_ret and not _compatible(proto_ret, typ_ret):
		return [f"expected property `{name}` to be of type {_tname(proto_ret)}, got {_tname(typ_ret)}"]
	return []


# --- descriptor kind checks ---


def _check_method_kind(
	name: str,
	proto_kind: MethodKind,
	typ_kind: MethodKind,
) -> str | None:
	"""staticmethod/classmethod kind mismatch."""
	if proto_kind in ("static", "classmethod") and proto_kind != typ_kind:
		return f"expected `{name}` to be {proto_kind}, found {typ_kind}"
	return None


def _check_callable(
	name: str,
	protombr: typing.Any,
	typmbr: typing.Any,
	proto_unwrapped: typing.Any,
	typ_unwrapped: typing.Any,
	proto_kind: MethodKind,
	typ_kind: MethodKind,
	strict: bool,
) -> list[str]:
	"""both sides are callable — compare signatures."""
	p = proto_unwrapped if proto_kind == "static" else protombr
	t = typ_unwrapped if typ_kind == "static" else typmbr
	return _check_signatures(name, p, t, strict)

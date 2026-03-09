from typing import Protocol, TypeIs, _ProtocolMeta

from sotkalib.type.generics import func

from ._impl import implements


class _CheckableMeta(_ProtocolMeta):
	def __new__(mcls, name: str, bases: tuple, namespace: dict, **kwargs):
		inst = super().__new__(mcls, name, bases, namespace, **kwargs)
		inst._is_protocol = True  # pyrefly: ignore[missing-attribute]
		mcls._protocol_cls = inst

		return inst

	def __rmod__(self, other: object) -> bool:
		return implements(other, self._protocol_cls, infer=True)

	@property
	def valid[T: "CheckableProtocol"](
		self: type[T],
	) -> func[[object], TypeIs[T]]:
		def _(other: object) -> TypeIs[T]:
			return implements(other, self._protocol_cls, infer=True)

		return _

	@property
	def impl_by[T: "CheckableProtocol"](
		self: type[T],
	) -> func[[object], TypeIs[T]]:
		def _(other: object) -> TypeIs[T]:
			return implements(other, self._protocol_cls, infer=True)

		return _


class CheckableProtocol(Protocol, metaclass=_CheckableMeta):
	pass

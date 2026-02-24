from typing import Protocol, TypeIs, _ProtocolMeta

from sotkalib.type.generics import func

from ._impl import implements


class _CheckableMeta(_ProtocolMeta):
	def __new__(mcs, name: str, bases: tuple, namespace: dict, **kwargs):
		cls = super().__new__(mcs, name, bases, namespace, **kwargs)
		mcs._protocol_cls = cls
		cls._is_protocol = True  # pyrefly:ignore

		return cls

	def __rmod__(self, other: type | object) -> bool:
		return implements(other, self._protocol_cls, early=True)

	@property
	def valid[T: "_CheckableMeta"](self: type[T]) -> func[[type | object], TypeIs[T]]:
		def _(other: type | object) -> TypeIs[T]:
			return implements(other, self._protocol_cls, early=True)

		return _


class CheckableProtocol(Protocol, metaclass=_CheckableMeta): ...

from typing import Any, Protocol, _ProtocolMeta

from ._impl import implements


class _CheckableMeta(_ProtocolMeta):
	def __new__(mcs, name: str, bases: tuple, namespace: dict, **kwargs):
		cls = super().__new__(mcs, name, bases, namespace, **kwargs)
		mcs._protocol_cls = cls
		cls._is_protocol = True  # pyrefly:ignore

		return cls

	def __rmod__(self, other: type[Any]) -> bool:
		return implements(other, self._protocol_cls, early=True)


class CheckableProtocol(Protocol, metaclass=_CheckableMeta): ...

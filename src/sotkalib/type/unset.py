"""module containing unset sentinel type/value"""

from typing import TypeIs


class UnsetT:
	__slots__ = ()

	def __repr__(self) -> str:
		return "<unset value>"

	__str__ = __repr__

	def __bool__(self) -> bool:
		return False


_UnsetType = UnsetT
Unset = UnsetT()


def is_set(val: object) -> bool:
	return not isinstance(val, UnsetT)


def is_unset(val: object) -> TypeIs[UnsetT]:
	return isinstance(val, UnsetT)

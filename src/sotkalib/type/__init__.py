__all__ = ["Unset", "unset"]


class _UnsetType:
	__slots__ = ()

	def __repr__(self) -> str:
		return "Unset"

	def __bool__(self) -> bool:
		return False


Unset = _UnsetType()


def unset(val: object) -> bool:
	return val is Unset

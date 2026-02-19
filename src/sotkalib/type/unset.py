from _warnings import warn


class UnsetType:
	__slots__ = ()

	def __repr__(self) -> str:
		return "<unset value>"

	__str__ = __repr__

	def __bool__(self) -> bool:
		return False


_UnsetType = UnsetType
Unset = UnsetType()


def is_set(val: object) -> bool:
	return not isinstance(val, UnsetType)


def unset(val: object) -> bool:
	warn(
		"sotkalib.type.unset() is deprecated and will be removed in 0.1.6, use not is_set(...) instead",
		category=DeprecationWarning,
		stacklevel=2,
	)

	return not is_set(val)

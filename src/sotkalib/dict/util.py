from collections.abc import Callable

from sotkalib.type import is_set


class _dict[K, Val](dict[K, Val]):  # noqa: N801
	def __init__(self, *args, **kwargs):
		super().__init__(*args, **kwargs)
		self.__dict__ = self

	def keys_(self) -> list[K]:
		return list(super().keys())

	def valid(self) -> "_dict[K, Val]":
		return valid(self)

	def unset(self) -> "_dict[K, Val]":
		return unset(self)

	def not_none(self) -> "_dict[K, Val]":
		return not_none(self)


def _valid_keys[Key, Valal](d: dict[Key, Valal]) -> set[Key]:
	return {k for k, Val in d.items() if is_set(Val)}


def _filter[Key, Val](d: dict[Key, Val], f: Callable[[Key, Val], bool]) -> _dict[Key, Val]:
	return _dict({k: Val for k, Val in d.items() if f(k, Val)})


def valid[Key, Val](d: dict[Key, Val]) -> _dict[Key, Val]:
	return _filter(d, lambda k, _: k in _valid_keys(d))


def unset[Key, Val](d: dict[Key, Val]) -> _dict[Key, Val]:
	return _filter(d, lambda k, _: k not in _valid_keys(d))


def not_none[Key, Val](d: dict[Key, Val]) -> _dict[Key, Val]:
	return _filter(d, lambda _, v: v is not None)

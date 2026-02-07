from collections.abc import Callable

from sotkalib.type import unset as unset_func


class _dict[K, V](dict[K, V]):  # noqa: N801
	def __init__(self, *args, **kwargs):
		super().__init__(*args, **kwargs)
		self.__dict__ = self

	def keys_(self) -> list[K]:
		return list(super().keys())

	def valid(self) -> "_dict[K, V]":
		return valid(self)

	def unset(self) -> "_dict[K, V]":
		return unset(self)

	def not_none(self) -> "_dict[K, V]":
		return not_none(self)


def _valid_keys[K, V](d: dict[K, V]) -> set[K]:
	return {k for k, v in d.items() if not unset_func(v)}


def _filter[K, V](d: dict[K, V], f: Callable[[K, V], bool]) -> _dict[K, V]:
	return _dict({k: v for k, v in d.items() if f(k, v)})


def valid[K, V](d: dict[K, V]) -> _dict[K, V]:
	return _filter(d, lambda k, _: k in _valid_keys(d))


def unset[K, V](d: dict[K, V]) -> _dict[K, V]:
	return _filter(d, lambda k, _: k not in _valid_keys(d))


def not_none[K, V](d: dict[K, V]) -> _dict[K, V]:
	return _filter(d, lambda _, v: v is not None)

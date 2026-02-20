import os
import typing
from _warnings import warn
from contextlib import AbstractAsyncContextManager
from copy import copy
from functools import wraps

from redis import asyncio as aioredis

from ...serializer.abc import Serializer
from ...type import generics, iface
from .abcs import keyfunc
from .settings import LRUSettings

_no_rtype_with_typed_warn = lambda styp, func: warn(  # noqa: E731
	f"TypedSerializer[{styp.__name__}] is used for caching a function ({func.__name__}) that has no type hints;"
	" could not check type compatability, serializing may cause exceptions.",
	stacklevel=2,
	category=RuntimeWarning,
)


def _get_rtype(func) -> typing.Any | None:
	return typing.get_type_hints(func).get("return")


class RedisLRU:
	__slots__ = ("_redis_factory", "_version", "_ttl", "_serializer", "_keyfunc", "_is_copy", "__pickle_allowed")

	def __init__(self, redis_factory: AbstractAsyncContextManager[aioredis.Redis], settings: LRUSettings | None = None):
		if settings is None:
			settings = LRUSettings()

		self.__pickle_allowed = (os.getenv("SOTKALIB_ALLOW_PICKLE", "").lower() == "yes") or False
		self._redis_factory = redis_factory
		self._version = settings.version
		self._ttl = settings.ttl
		self._serializer = settings.serializer
		self._keyfunc = settings.keyfunc
		self._is_copy = False

	def ttl(self, ttl: int) -> typing.Self:
		if not self._is_copy:
			new_self = copy(self)
			new_self._is_copy = True
			new_self._ttl = ttl
			return new_self
		self._ttl = ttl
		return self

	def version(self, ver: int) -> typing.Self:
		if not self._is_copy:
			new_self = copy(self)
			new_self._is_copy = True
			new_self._version = ver
			return new_self
		self._version = ver
		return self

	def serializer(self, szr: Serializer) -> typing.Self:
		if not self._is_copy:
			new_self = copy(self)
			new_self._is_copy = True
			new_self._serializer = szr
			return new_self

		self._serializer = szr
		return self

	def keyfunc(self, kf: keyfunc) -> typing.Self:
		if not self._is_copy:
			new_self = copy(self)
			new_self._is_copy = True
			new_self._keyfunc = kf
			return new_self

		self._keyfunc = kf
		return self

	def __call__[**P, R](self, func: generics.async_function[P, R]) -> generics.async_function[P, R]:
		if styp := getattr(self._serializer, "type_", None):
			if rtyp := _get_rtype(func):
				if not iface.compatible(styp, rtyp, strict=True):
					raise TypeError(
						f"TypedSerializer[{styp.__name__}] is not compatible "
						f"with def {func.__name__}(...) -> {rtyp.__name__}"
					)
			else:
				_no_rtype_with_typed_warn(styp, func)

		@wraps(func)
		async def inner(*args: P.args, **kwargs: P.kwargs) -> R:
			cache_func_key = self._keyfunc(self._version, func.__name__, *args, **kwargs)  # type: ignore[arg-type]
			async with self._redis_factory as rc:
				cached_result: bytes | str | None = await rc.get(cache_func_key)
				if cached_result is not None:
					if isinstance(cached_result, str):
						cached_result = cached_result.encode()
					return self._serializer.unmarshal(cached_result)
			result = await func(*args, **kwargs)
			async with self._redis_factory as rc:
				await rc.set(cache_func_key, self._serializer.marshal(result), ex=self._ttl)
			return result

		return inner

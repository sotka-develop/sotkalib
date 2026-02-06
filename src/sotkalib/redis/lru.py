import os
from base64 import b64decode, b64encode
from collections.abc import Awaitable, Callable, Coroutine
from contextlib import AbstractAsyncContextManager
from copy import copy
from datetime import datetime
from functools import wraps
from pickle import HIGHEST_PROTOCOL, dumps, loads
from typing import Any, Protocol, Self
from warnings import warn

from pydantic import ConfigDict, SkipValidation
from pydantic.main import BaseModel
from redis.asyncio import Redis


class Serializer(Protocol):
	@staticmethod
	def marshal(data: Any) -> bytes: ...

	@staticmethod
	def unmarshal(raw_data: bytes) -> Any: ...


class B64Pickle:
	@staticmethod
	def marshal(data: Any) -> bytes:
		dumped = dumps(data, protocol=HIGHEST_PROTOCOL)
		dumped_b64 = b64encode(dumped)
		return dumped_b64

	@staticmethod
	def unmarshal(raw_data: bytes) -> Any:
		return loads(b64decode(raw_data))  # noqa


class keyfunc(Protocol):  # noqa: N801
	def __call__(self, version: int, func_name: str, *args: tuple, **kwargs: dict[str, Any]) -> str: ...


def base_keyfunc(version: int, func_name: str, *args: tuple, **kwargs: dict[str, Any]) -> str:
	return f"{version}_{datetime.now().isoformat()}_{func_name}_{B64Pickle.marshal((args, kwargs))}"


class LRUSettings(BaseModel):
	model_config = ConfigDict(arbitrary_types_allowed=True)

	version: int = 1
	ttl: int = 600
	serializer: SkipValidation[Serializer] = B64Pickle
	keyfunc: SkipValidation[keyfunc] = base_keyfunc


class RedisLRU:
	__slots__ = ("_redis_factory", "_version", "_ttl", "_serializer", "_keyfunc", "_is_copy", "__pickle_allowed")

	def __init__(self, redis_factory: AbstractAsyncContextManager[Redis], settings: LRUSettings | None = None):
		if settings is None:
			settings = LRUSettings()

		self.__pickle_allowed = (os.getenv("LRU_CACHE_ALLOW_PICKLE", "").lower() == "yes") or False
		self._redis_factory = redis_factory
		self._version = settings.version
		self._ttl = settings.ttl
		self._serializer = settings.serializer
		self._keyfunc = settings.keyfunc
		self._is_copy = False

	def ttl(self, ttl: int) -> Self:
		if not self._is_copy:
			new_self = copy(self)
			new_self._is_copy = True
			new_self._ttl = ttl
			return new_self
		self._ttl = ttl
		return self

	def version(self, ver: int) -> Self:
		if not self._is_copy:
			new_self = copy(self)
			new_self._is_copy = True
			new_self._version = ver
			return new_self
		self._version = ver
		return self

	def serializer(self, szr: Serializer) -> Self:
		if not self._is_copy:
			new_self = copy(self)
			new_self._is_copy = True
			new_self._serializer = szr
			return new_self

		self._serializer = szr
		return self

	def keyfunc(self, kf: keyfunc) -> Self:
		if not self._is_copy:
			new_self = copy(self)
			new_self._is_copy = True
			new_self._keyfunc = kf
			return new_self

		self._keyfunc = kf
		return self

	def __call__[**P, R](
		self, func: Callable[P, Awaitable[R] | Coroutine[Any, Any, R]]
	) -> Callable[P, Awaitable[R] | Coroutine[Any, Any, R]]:
		if isinstance(self._serializer, B64Pickle) and not self.__pickle_allowed:
			warn(
				f"LRU cache for func {func.__name__} is using pickle serializer."
				" This is not recommended for production,"
				" as deserialization with pickle may execute arbitrary code.\n\n"
				"You may silence this warning by using a different serializer or set"
				"ting the environment variable LRU_CACHE_ALLOW_PICKLE=yes",
				stacklevel=2,
				category=SecurityWarning,
			)

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


class SecurityWarning(Warning): ...

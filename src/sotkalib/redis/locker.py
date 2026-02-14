import asyncio
import os
from collections.abc import AsyncGenerator, Sequence
from contextlib import AbstractAsyncContextManager, asynccontextmanager, suppress
from copy import copy
from time import time
from typing import Any, Protocol, Self, runtime_checkable

from pydantic import ConfigDict, Field, SkipValidation
from pydantic.main import BaseModel
from redis.asyncio import Redis

_RELEASE_LUA = """
if redis.call("get", KEYS[1]) == ARGV[1] then
	return redis.call("del", KEYS[1])
else
	return 0
end
"""

_EXTEND_LUA = """
if redis.call("get", KEYS[1]) == ARGV[1] then
	return redis.call("expire", KEYS[1], ARGV[2])
else
	return 0
end
"""


@runtime_checkable
class _strable(Protocol):  # noqa: N801
	def __str__(self) -> str: ...


class _backoff(Protocol):  # noqa: N801
	def __call__(self, attempt: int) -> float: ...


def plain_delay(delay: float) -> _backoff:
	def _(attempt: int) -> float:  # noqa: ARG001
		return delay

	return _


def additive_delay(base_delay: float, increment: float) -> _backoff:
	def _(attempt: int) -> float:  # noqa: ARG001
		return base_delay + (attempt - 1) * increment

	return _


def exponential_delay(base_delay: float, factor: float) -> _backoff:
	def _(attempt: int) -> float:  # noqa: ARG001
		return base_delay * factor ** (attempt - 1)

	return _


_DEFAULT_BACKOFF: _backoff = exponential_delay(0.1, 2)


class DLSettings(BaseModel):
	model_config = ConfigDict(arbitrary_types_allowed=True)

	wait: bool = False
	wait_delay_func: SkipValidation[_backoff] = _DEFAULT_BACKOFF
	wait_timeout: float = 60.0
	spin_attempts: int = 0

	retry_if_acquired: bool = False
	exc_args: SkipValidation[Sequence[Any]] = ()
	extend_ttl: bool = True
	watchdog_factor: float = Field(ge=1, default=3)


class ContextLockError(Exception):
	def __init__(self, *args, can_retry: bool = True):
		super().__init__(*args)
		self.can_retry = can_retry


class DistributedLock:
	__slots__ = (
		"_redis_factory",
		"_is_copy",
		"_wait",
		"_wait_backoff",
		"_wait_timeout",
		"_spin_attempts",
		"_retry_if_acquired",
		"_exc_args",
		"_extend_ttl",
		"_watchdog_factor",
	)

	def __init__(self, redis_factory: AbstractAsyncContextManager[Redis], settings: DLSettings | None = None):
		settings = settings or DLSettings()

		self._redis_factory = redis_factory
		self._wait = settings.wait
		self._wait_backoff: _backoff = settings.wait_delay_func
		self._wait_timeout = settings.wait_timeout
		self._spin_attempts = settings.spin_attempts
		self._retry_if_acquired = settings.retry_if_acquired
		self._exc_args: Sequence[Any] = settings.exc_args
		self._extend_ttl = settings.extend_ttl
		self._watchdog_factor = settings.watchdog_factor

		self._is_copy = False

	def no_wait(self) -> Self:
		if not self._is_copy:
			new = copy(self)
			new._is_copy = True
			new._wait = False
			return new

		self._wait = False
		return self

	def wait(self, *, backoff: _backoff = _DEFAULT_BACKOFF, timeout: float = 60.0) -> Self:
		if not self._is_copy:
			new = copy(self)
			new._is_copy = True
			new._wait = True
			new._wait_backoff = backoff
			new._wait_timeout = timeout
			return new

		self._wait = True
		self._wait_backoff = backoff
		self._wait_timeout = timeout
		return self

	def spin(self, *, attempts: int) -> Self:
		if not self._is_copy:
			new = copy(self)
			new._is_copy = True
			new._spin_attempts = attempts
			return new

		self._spin_attempts = attempts
		return self

	def if_acquired(self, *, retry: bool) -> Self:
		return self.if_taken(retry=retry)

	def if_taken(self, *, retry: bool) -> Self:
		if not self._is_copy:
			new = copy(self)
			new._is_copy = True
			new._retry_if_acquired = retry
			return new

		self._retry_if_acquired = retry
		return self

	def extend(self, *, enabled: bool = True, watchdog_factor: float = 3.0) -> Self:
		if not self._is_copy:
			new = copy(self)
			new._is_copy = True
			new._extend_ttl = enabled
			new._watchdog_factor = watchdog_factor
			return new

		self._extend_ttl = enabled
		self._watchdog_factor = watchdog_factor
		return self

	def exc(self, *args: Any) -> Self:
		if not self._is_copy:
			new = copy(self)
			new._is_copy = True
			new._exc_args = args
			return new

		self._exc_args = args
		return self

	async def _try_acquire(self, rc: Redis, key: str, ttl: int, token: str) -> bool:
		return bool(await rc.set(key, token, nx=True, ex=ttl))

	async def _spin_acquire(self, rc: Redis, key: str, ttl: int, token: str) -> bool:
		for _ in range(self._spin_attempts):
			if await self._try_acquire(rc, key, ttl, token):
				return True
			await asyncio.sleep(0)
		return False

	async def _wait_acquire(self, rc: Redis, key: str, ttl: int, token: str) -> bool:
		start = time()
		attempt = 1
		while True:
			if await self._try_acquire(rc, key, ttl, token):
				return True

			if (time() - start) > self._wait_timeout:
				return False

			await asyncio.sleep(self._wait_backoff(attempt))
			attempt += 1

	def acq(self, key: _strable, timeout: int = 5) -> AbstractAsyncContextManager[None]:
		return self.acquire(key, ttl=timeout)

	@asynccontextmanager
	async def acquire(self, key: _strable, *, ttl: int = 5) -> AsyncGenerator[None]:
		key = str(key)
		token = os.urandom(16).hex()
		acquired = False
		watchdog: asyncio.Task[None] | None = None

		try:
			async with self._redis_factory as rc:
				# ph 1: spin — rapid attempts, no delay
				if self._spin_attempts > 0:
					acquired = await self._spin_acquire(rc, key, ttl, token)

				# ph 2: single cmpswap attempt (no spin, no wait)
				if not acquired and not self._wait:
					acquired = await self._try_acquire(rc, key, ttl, token)

				# ph 3: wait & delay
				if not acquired and self._wait:
					acquired = await self._wait_acquire(rc, key, ttl, token)

				if not acquired:
					if self._wait:
						raise ContextLockError(
							f"{key} lock already acquired, timeout after {self._wait_timeout}s",
							*self._exc_args,
							can_retry=False,
						)
					raise ContextLockError(
						f"{key} lock already acquired",
						*self._exc_args,
						can_retry=self._retry_if_acquired,
					)

			# start watchdog to extend TTL while lock is held
			if acquired and self._extend_ttl:
				watchdog = asyncio.create_task(self._watchdog(key, token, ttl))

			yield
		finally:
			if watchdog is not None:
				watchdog.cancel()
				with suppress(asyncio.CancelledError):
					await watchdog

			if acquired:
				async with self._redis_factory as rc:
					await rc.eval(_RELEASE_LUA, 1, key, token)  # type: ignore[arg-type]

	async def _watchdog(self, key: str, token: str, ttl: int) -> None:
		interval = ttl / self._watchdog_factor
		try:
			while True:
				await asyncio.sleep(interval)
				async with self._redis_factory as rc:
					result = await rc.eval(_EXTEND_LUA, 1, key, token, ttl)  # type: ignore[arg-type]
					if not result:
						return
		except asyncio.CancelledError:
			return

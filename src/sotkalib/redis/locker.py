import asyncio
from collections.abc import AsyncGenerator, Sequence
from contextlib import AbstractAsyncContextManager, asynccontextmanager
from copy import copy
from time import time
from typing import Any, Protocol, Self, runtime_checkable

from pydantic import ConfigDict, SkipValidation
from pydantic.main import BaseModel
from redis.asyncio import Redis


@runtime_checkable
class strable(Protocol):  # noqa: N801
	def __str__(self) -> str: ...


class backoff(Protocol):  # noqa: N801
	def __call__(self, attempt: int) -> float: ...


def plain_delay(delay: float) -> backoff:
	def _(attempt: int) -> float:  # noqa: ARG001
		return delay

	return _


def additive_delay(base_delay: float, increment: float) -> backoff:
	def _(attempt: int) -> float:  # noqa: ARG001
		return base_delay + (attempt - 1) * increment

	return _


def exponential_delay(base_delay: float, factor: float) -> backoff:
	def _(attempt: int) -> float:  # noqa: ARG001
		return base_delay * factor ** (attempt - 1)

	return _


_DEFAULT_BACKOFF: backoff = exponential_delay(0.1, 2)


class DLSettings(BaseModel):
	model_config = ConfigDict(arbitrary_types_allowed=True)

	wait: bool = False
	wait_delay_func: SkipValidation[backoff] = _DEFAULT_BACKOFF
	wait_timeout: float = 60.0
	spin_attempts: int = 0

	retry_if_acquired: bool = False
	exc_args: SkipValidation[Sequence[Any]] = ()


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
	)

	def __init__(self, redis_factory: AbstractAsyncContextManager[Redis], settings: DLSettings | None = None):
		if settings is None:
			settings = DLSettings()

		self._redis_factory = redis_factory
		self._wait = settings.wait
		self._wait_backoff: backoff = settings.wait_delay_func
		self._wait_timeout = settings.wait_timeout
		self._spin_attempts = settings.spin_attempts
		self._retry_if_acquired = settings.retry_if_acquired
		self._exc_args: Sequence[Any] = settings.exc_args

		self._is_copy = False

	def no_wait(self) -> Self:
		if not self._is_copy:
			new = copy(self)
			new._is_copy = True
			new._wait = False
			return new

		self._wait = False
		return self

	def wait(self, *, backoff: backoff = _DEFAULT_BACKOFF, timeout: float = 60.0) -> Self:
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

	# def acquire_(self, *, timeout: int = 5) -> Self:
	# 	if not self._is_copy:
	# 		new = copy(self)
	# 		new._is_copy = True
	# 		new._acquire_timeout = timeout
	# 		return new

	# 	self._acquire_timeout = timeout
	# 	return self

	def exc(self, *args: Any) -> Self:
		if not self._is_copy:
			new = copy(self)
			new._is_copy = True
			new._exc_args = args
			return new

		self._exc_args = args
		return self

	async def _try_acquire(self, rc: Redis, key: str, ttl: int) -> bool:
		return bool(await rc.set(key, "acquired", nx=True, ex=ttl))

	async def _spin_acquire(self, rc: Redis, key: str, ttl: int) -> bool:
		for _ in range(self._spin_attempts):
			if await self._try_acquire(rc, key, ttl):
				return True
			await asyncio.sleep(0)
		return False

	async def _wait_acquire(self, rc: Redis, key: str, ttl: int) -> bool:
		start = time()
		attempt = 1
		while True:
			if await self._try_acquire(rc, key, ttl):
				return True

			if (time() - start) > self._wait_timeout:
				return False

			await asyncio.sleep(self._wait_backoff(attempt))
			attempt += 1

	def acq(self, key: strable, timeout: int = 5) -> AbstractAsyncContextManager[None]:
		return self.acquire(key, ttl=timeout)

	@asynccontextmanager
	async def acquire(self, key: strable, *, ttl: int = 5) -> AsyncGenerator[None]:
		key = str(key)
		acquired = False

		try:
			async with self._redis_factory as rc:
				# ph 1: spin — rapid attempts, no delay
				if self._spin_attempts > 0:
					acquired = await self._spin_acquire(rc, key, ttl)

				# ph 2: single cmpswap attempt (no spin, no wait)
				if not acquired and not self._wait:
					acquired = await self._try_acquire(rc, key, ttl)

				# ph 3: wait & delay
				if not acquired and self._wait:
					acquired = await self._wait_acquire(rc, key, ttl)

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
			yield
		finally:
			if acquired:
				async with self._redis_factory as rc:
					await rc.delete(key)

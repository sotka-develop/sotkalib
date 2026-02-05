import asyncio
from collections.abc import AsyncGenerator
from contextlib import AbstractAsyncContextManager, asynccontextmanager
from time import time
from typing import Any, Protocol, runtime_checkable

from redis.asyncio import Redis


class ContextLockError(Exception):
	def __init__(self, *args, can_retry: bool = True):
		super().__init__(*args)
		self.can_retry = can_retry


async def __try_acquire(rc: Redis, key_to_lock: str, acquire_timeout: int) -> bool:
	"""Atomically acquire a lock using SET NX (set-if-not-exists)."""
	return bool(await rc.set(key_to_lock, "acquired", nx=True, ex=acquire_timeout))


async def __wait_till_lock_free(
	client: Redis,
	key_to_lock: str,
	lock_timeout: float = 10.0,
	base_delay: float = 0.1,
	max_delay: float = 5.0,
) -> None:
	start = time()
	attempt = 0
	while await client.get(key_to_lock) is not None:
		if (time() - start) > lock_timeout:
			raise ContextLockError(
				f"{key_to_lock} lock already acquired, timeout after {lock_timeout}s",
				can_retry=False,
			)
		delay = min(base_delay * (2**attempt), max_delay)
		await asyncio.sleep(delay)
		attempt += 1


@runtime_checkable
class strable(Protocol):  # noqa: N801
	def __str__(self) -> str: ...


@asynccontextmanager
async def redis_context_lock(
	client: AbstractAsyncContextManager[Redis],
	key_to_lock: str | strable,
	can_retry_if_lock_catched: bool = True,
	wait_for_lock: bool = False,
	wait_timeout: float = 60.0,
	acquire_timeout: int = 5,
	args_to_lock_exception: list[Any] | None = None,
) -> AsyncGenerator[None]:
	"""
	Acquire a Redis lock atomically using SET NX.

	:param client: async context mng for redis
	:param key_to_lock: Redis key for the lock
	:param can_retry_if_lock_catched: Whether task should retry if lock is taken (only used if wait_for_lock=False)
	:param wait_for_lock: If True, wait for lock to be free instead of immediately failing
	:param wait_timeout: Maximum time to wait for lock in seconds (only used if wait_for_lock=True)
	:param acquire_timeout: Timeout for acquiring lock
	:param args_to_lock_exception: Args to pass to ContextLockError

	"""
	if args_to_lock_exception is None:
		args_to_lock_exception = []

	if isinstance(key_to_lock, strable) and not isinstance(key_to_lock, str):
		key_to_lock = str(key_to_lock)

	if wait_for_lock:
		async with client as rc:
			await __wait_till_lock_free(key_to_lock=key_to_lock, client=rc, lock_timeout=wait_timeout)

	try:
		async with client as rc:
			acquired = await __try_acquire(rc, key_to_lock, acquire_timeout)
			if not acquired:
				raise ContextLockError(
					f"{key_to_lock} lock already acquired",
					*args_to_lock_exception,
					can_retry=can_retry_if_lock_catched,
				)
		yield
	finally:
		async with client as rc:
			await rc.delete(key_to_lock)

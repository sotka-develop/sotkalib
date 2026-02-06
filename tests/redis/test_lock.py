import asyncio

import pytest
from redis.asyncio import Redis

from sotkalib.redis.lock import ContextLockError, __wait_till_lock_free, redis_context_lock

pytestmark = pytest.mark.filterwarnings("ignore::DeprecationWarning")


@pytest.mark.asyncio
async def test_context_lock_acquire_and_release(redis_client: Redis):
	key = "test:lock:basic"

	async with redis_context_lock(redis_client, key):
		val = await redis_client.get(key)
		assert val == "acquired"

	val = await redis_client.get(key)
	assert val is None


@pytest.mark.asyncio
async def test_context_lock_emits_deprecation_warning(redis_client: Redis):
	key = "test:lock:deprecation"

	with pytest.warns(DeprecationWarning, match="redis_context_lock is deprecated"):
		async with redis_context_lock(redis_client, key):
			pass


@pytest.mark.asyncio
async def test_context_lock_raises_when_already_acquired(redis_client: Redis):
	key = "test:lock:conflict"

	await redis_client.set(key, "acquired", ex=10)

	with pytest.raises(ContextLockError):
		async with redis_context_lock(redis_client, key):
			pass  # noqa: S101


@pytest.mark.asyncio
async def test_context_lock_can_retry_flag(redis_client: Redis):
	key = "test:lock:retry_flag"

	await redis_client.set(key, "acquired", ex=10)

	with pytest.raises(ContextLockError) as exc_info:
		async with redis_context_lock(redis_client, key, can_retry_if_lock_catched=False):
			pass

	assert exc_info.value.can_retry is False


@pytest.mark.asyncio
async def test_context_lock_wait_for_lock(redis_client: Redis):
	key = "test:lock:wait"

	await redis_client.set(key, "acquired", ex=1)

	async with redis_context_lock(redis_client, key, wait_for_lock=True, wait_timeout=5):
		val = await redis_client.get(key)
		assert val == "acquired"


@pytest.mark.asyncio
async def test_context_lock_wait_timeout(redis_client: Redis):
	key = "test:lock:wait_timeout"

	await redis_client.set(key, "acquired", ex=30)

	with pytest.raises(ContextLockError):
		async with redis_context_lock(redis_client, key, wait_for_lock=True, wait_timeout=0.5):
			pass


@pytest.mark.asyncio
async def test_context_lock_released_on_exception(redis_client: Redis):
	key = "test:lock:exception"

	with pytest.raises(ValueError, match="boom"):
		async with redis_context_lock(redis_client, key):
			raise ValueError("boom")

	val = await redis_client.get(key)
	assert val is None


@pytest.mark.asyncio
async def test_wait_till_lock_free_immediate(redis_client: Redis):
	key = "test:lock:free"
	await __wait_till_lock_free(redis_client, key, lock_timeout=1.0)


@pytest.mark.asyncio
async def test_wait_till_lock_free_waits(redis_client: Redis):
	key = "test:lock:wait_free"
	await redis_client.set(key, "acquired", ex=1)

	await __wait_till_lock_free(redis_client, key, lock_timeout=3.0)


@pytest.mark.asyncio
async def test_wait_till_lock_free_timeout(redis_client: Redis):
	key = "test:lock:wait_free_timeout"
	await redis_client.set(key, "acquired", ex=30)

	with pytest.raises(ContextLockError):
		await __wait_till_lock_free(redis_client, key, lock_timeout=0.3)


@pytest.mark.asyncio
async def test_context_lock_error_attributes():
	err = ContextLockError("test error", can_retry=True)
	assert str(err) == "test error"
	assert err.can_retry is True

	err2 = ContextLockError("no retry", can_retry=False)
	assert err2.can_retry is False


@pytest.mark.asyncio
async def test_sequential_lock_contention(redis_client: Redis):
	"""First worker acquires, second fails because lock is already set."""
	key = "test:lock:sequential"

	async with redis_context_lock(redis_client, key, acquire_timeout=5):
		with pytest.raises(ContextLockError):
			async with redis_context_lock(redis_client, key):
				pass


@pytest.mark.asyncio
async def test_concurrent_lock_atomicity(redis_client: Redis):
	"""Only one of N concurrent workers should acquire the lock (SET NX)."""
	key = "test:lock:atomic"
	acquired_count = 0
	rejected_count = 0
	barrier = asyncio.Barrier(5)

	async def worker(worker_id: int):  # noqa: ARG001
		nonlocal acquired_count, rejected_count
		await barrier.wait()
		result = await redis_client.set(key, "acquired", nx=True, ex=5)
		if result:
			acquired_count += 1
		else:
			rejected_count += 1

	tasks = [asyncio.create_task(worker(i)) for i in range(5)]
	await asyncio.gather(*tasks)

	assert acquired_count == 1
	assert rejected_count == 4

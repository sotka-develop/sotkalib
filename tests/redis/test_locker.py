import asyncio

import pytest
from redis.asyncio import Redis

from sotkalib.redis.locker import (
	ContextLockError,
	DistributedLock,
	DLSettings,
	additive_delay,
	exponential_delay,
	plain_delay,
)
from sotkalib.redis.pool import RedisPool, RedisPoolSettings

# ── Backoff functions ──────────────────────────────────────────────


def test_plain_delay_returns_constant():
	fn = plain_delay(0.5)
	assert fn(1) == 0.5
	assert fn(5) == 0.5
	assert fn(100) == 0.5


def test_additive_delay_increases_linearly():
	fn = additive_delay(0.1, 0.2)
	assert fn(1) == pytest.approx(0.1)
	assert fn(2) == pytest.approx(0.3)
	assert fn(3) == pytest.approx(0.5)


def test_exponential_delay_increases_exponentially():
	fn = exponential_delay(0.1, 2)
	assert fn(1) == pytest.approx(0.1)
	assert fn(2) == pytest.approx(0.2)
	assert fn(3) == pytest.approx(0.4)
	assert fn(4) == pytest.approx(0.8)


# ── DLSettings ─────────────────────────────────────────────────────


def test_dl_settings_defaults():
	settings = DLSettings()
	assert settings.wait is False
	assert settings.wait_timeout == 60.0
	assert settings.retry_if_acquired is False
	assert settings.acquire_timeout == 5
	assert settings.spin_attempts == 0
	assert settings.exc_args == ()


# ── ContextLockError ──────────────────────────────────────────────


def test_context_lock_error_attributes():
	err = ContextLockError("test error", can_retry=True)
	assert str(err) == "test error"
	assert err.can_retry is True

	err2 = ContextLockError("no retry", can_retry=False)
	assert err2.can_retry is False


def test_context_lock_error_default_can_retry():
	err = ContextLockError("msg")
	assert err.can_retry is True


# ── basic acquire / release ───────────────────────────────────────


@pytest.mark.asyncio
async def test_acquire_and_release(redis_url: str, redis_client: Redis):
	pool = RedisPool(RedisPoolSettings(uri=redis_url, db_num=0))
	lock = DistributedLock(pool)
	key = "test:locker:basic"

	async with lock.acq(key):
		val = await redis_client.get(key)
		assert val == "acquired"

	val = await redis_client.get(key)
	assert val is None


@pytest.mark.asyncio
async def test_raises_when_already_acquired(redis_url: str, redis_client: Redis):
	pool = RedisPool(RedisPoolSettings(uri=redis_url, db_num=0))
	lock = DistributedLock(pool)
	key = "test:locker:conflict"

	await redis_client.set(key, "acquired", ex=10)

	with pytest.raises(ContextLockError):
		async with lock.acq(key):
			pass


# ── if_acquired / retry flag ──────────────────────────────────────


@pytest.mark.asyncio
async def test_if_acquired_retry_flag(redis_url: str, redis_client: Redis):
	pool = RedisPool(RedisPoolSettings(uri=redis_url, db_num=0))
	key = "test:locker:retry_flag"

	await redis_client.set(key, "acquired", ex=10)

	lock_no_retry = DistributedLock(pool).if_acquired(retry=False)
	with pytest.raises(ContextLockError) as exc_info:
		async with lock_no_retry.acq(key):
			pass
	assert exc_info.value.can_retry is False

	await redis_client.set(key, "acquired", ex=10)

	lock_retry = DistributedLock(pool).if_acquired(retry=True)
	with pytest.raises(ContextLockError) as exc_info:
		async with lock_retry.acq(key):
			pass
	assert exc_info.value.can_retry is True


# ── spin acquire ──────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_spin_acquires_free_lock(redis_url: str, redis_client: Redis):
	pool = RedisPool(RedisPoolSettings(uri=redis_url, db_num=0))
	lock = DistributedLock(pool).spin(attempts=3)
	key = "test:locker:spin_free"

	async with lock.acq(key):
		val = await redis_client.get(key)
		assert val == "acquired"

	val = await redis_client.get(key)
	assert val is None


@pytest.mark.asyncio
async def test_spin_fails_when_held(redis_url: str, redis_client: Redis):
	pool = RedisPool(RedisPoolSettings(uri=redis_url, db_num=0))
	lock = DistributedLock(pool).spin(attempts=3)
	key = "test:locker:spin_held"

	await redis_client.set(key, "acquired", ex=30)

	with pytest.raises(ContextLockError):
		async with lock.acq(key):
			pass

	val = await redis_client.get(key)
	assert val == "acquired"


@pytest.mark.asyncio
async def test_spin_then_wait_fallback(redis_url: str, redis_client: Redis):
	pool = RedisPool(RedisPoolSettings(uri=redis_url, db_num=0))
	key = "test:locker:spin_wait"

	await redis_client.set(key, "acquired", ex=1)

	lock = DistributedLock(pool).spin(attempts=3).wait(backoff=plain_delay(0.2), timeout=5.0)

	async with lock.acq(key):
		val = await redis_client.get(key)
		assert val == "acquired"

	val = await redis_client.get(key)
	assert val is None


@pytest.mark.asyncio
async def test_spin_then_wait_timeout(redis_url: str, redis_client: Redis):
	pool = RedisPool(RedisPoolSettings(uri=redis_url, db_num=0))
	key = "test:locker:spin_wait_timeout"

	await redis_client.set(key, "acquired", ex=30)

	lock = DistributedLock(pool).spin(attempts=3).wait(backoff=plain_delay(0.05), timeout=0.3)

	with pytest.raises(ContextLockError) as exc_info:
		async with lock.acq(key):
			pass
	assert exc_info.value.can_retry is False


def test_spin_builder_returns_copy(redis_url: str):
	pool = RedisPool(RedisPoolSettings(uri=redis_url, db_num=0))
	original = DistributedLock(pool)

	modified = original.spin(attempts=5)
	assert modified is not original
	assert modified._spin_attempts == 5
	assert original._spin_attempts == 0


# ── failed acquire does not delete another holder's lock ──────────


@pytest.mark.asyncio
async def test_does_not_delete_others_lock_on_acquire_failure(redis_url: str, redis_client: Redis):
	pool = RedisPool(RedisPoolSettings(uri=redis_url, db_num=0))
	lock = DistributedLock(pool)
	key = "test:locker:no_delete_other"

	await redis_client.set(key, "acquired", ex=30)

	with pytest.raises(ContextLockError):
		async with lock.acq(key):
			pass

	val = await redis_client.get(key)
	assert val == "acquired"


# ── chained builder calls mutate copy in-place ────────────────────


def test_chained_calls_reuse_same_copy(redis_url: str):
	pool = RedisPool(RedisPoolSettings(uri=redis_url, db_num=0))
	original = DistributedLock(pool)

	first = original.wait(backoff=plain_delay(0.1), timeout=5.0)
	assert first is not original

	second = first.if_acquired(retry=True)
	assert second is first

	third = first.acquire(timeout=20)
	assert third is first


# ── wait for lock ─────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_waits_for_lock_release(redis_url: str, redis_client: Redis):
	pool = RedisPool(RedisPoolSettings(uri=redis_url, db_num=0))
	key = "test:locker:wait"

	await redis_client.set(key, "acquired", ex=1)

	lock = DistributedLock(pool).wait(backoff=plain_delay(0.1), timeout=5.0)

	async with lock.acq(key):
		val = await redis_client.get(key)
		assert val == "acquired"


@pytest.mark.asyncio
async def test_wait_timeout(redis_url: str, redis_client: Redis):
	pool = RedisPool(RedisPoolSettings(uri=redis_url, db_num=0))
	key = "test:locker:wait_timeout"

	await redis_client.set(key, "acquired", ex=30)

	lock = DistributedLock(pool).wait(backoff=plain_delay(0.05), timeout=0.3)

	with pytest.raises(ContextLockError) as exc_info:
		async with lock.acq(key):
			pass
	assert exc_info.value.can_retry is False


# ── dont_wait ─────────────────────────────────────────────────────


def test_dont_wait_disables_wait(redis_url: str):
	pool = RedisPool(RedisPoolSettings(uri=redis_url, db_num=0))
	lock = DistributedLock(pool).wait(timeout=5.0).no_wait()

	assert lock._wait is False


# ── released on exception ─────────────────────────────────────────


@pytest.mark.asyncio
async def test_released_on_exception(redis_url: str, redis_client: Redis):
	pool = RedisPool(RedisPoolSettings(uri=redis_url, db_num=0))
	lock = DistributedLock(pool)
	key = "test:locker:exception"

	with pytest.raises(ValueError, match="boom"):
		async with lock.acq(key):
			raise ValueError("boom")

	val = await redis_client.get(key)
	assert val is None


# ── exc builder ───────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_exc_args(redis_url: str, redis_client: Redis):
	pool = RedisPool(RedisPoolSettings(uri=redis_url, db_num=0))
	lock = DistributedLock(pool).exc("extra1", "extra2")
	key = "test:locker:exc_args"

	await redis_client.set(key, "acquired", ex=10)

	with pytest.raises(ContextLockError) as exc_info:
		async with lock.acq(key):
			pass

	assert "extra1" in exc_info.value.args
	assert "extra2" in exc_info.value.args


# ── strable key coercion ──────────────────────────────────────────


@pytest.mark.asyncio
async def test_strable_key(redis_url: str, redis_client: Redis):
	pool = RedisPool(RedisPoolSettings(uri=redis_url, db_num=0))
	lock = DistributedLock(pool)

	class MyKey:
		def __str__(self) -> str:
			return "test:locker:strable"

	async with lock.acq(MyKey()):
		val = await redis_client.get("test:locker:strable")
		assert val == "acquired"

	val = await redis_client.get("test:locker:strable")
	assert val is None


# ── builder methods return copies (immutability) ──────────────────


def test_builder_methods_return_copies(redis_url: str):
	pool = RedisPool(RedisPoolSettings(uri=redis_url, db_num=0))
	original = DistributedLock(pool)

	modified_wait = original.wait()
	assert modified_wait is not original
	assert modified_wait._wait is True
	assert original._wait is False

	modified_retry = original.if_acquired(retry=True)
	assert modified_retry is not original
	assert modified_retry._retry_if_acquired is True
	assert original._retry_if_acquired is False

	modified_timeout = original.acquire(timeout=30)
	assert modified_timeout is not original
	assert modified_timeout._acquire_timeout == 30
	assert original._acquire_timeout == 5


def test_chained_modifications(redis_url: str):
	pool = RedisPool(RedisPoolSettings(uri=redis_url, db_num=0))

	lock = (
		DistributedLock(pool).wait(backoff=plain_delay(0.5), timeout=10.0).if_acquired(retry=True).acquire(timeout=30)
	)

	assert lock._wait is True
	assert lock._wait_timeout == 10.0
	assert lock._retry_if_acquired is True
	assert lock._acquire_timeout == 30


# ── acquire timeout (TTL on redis key) ────────────────────────────


@pytest.mark.asyncio
async def test_acquire_timeout_sets_ttl(redis_url: str, redis_client: Redis):
	pool = RedisPool(RedisPoolSettings(uri=redis_url, db_num=0))
	lock = DistributedLock(pool).acquire(timeout=10)
	key = "test:locker:ttl"

	async with lock.acq(key):
		ttl = await redis_client.ttl(key)
		assert 0 < ttl <= 10


# ── sequential contention ─────────────────────────────────────────


@pytest.mark.asyncio
async def test_sequential_contention(redis_url: str):
	pool = RedisPool(RedisPoolSettings(uri=redis_url, db_num=0))
	lock = DistributedLock(pool)
	key = "test:locker:sequential"

	async with lock.acq(key):
		with pytest.raises(ContextLockError):
			async with lock.acq(key):
				pass


# ── concurrent atomicity ──────────────────────────────────────────


@pytest.mark.asyncio
async def test_concurrent_atomicity(redis_url: str):
	pool = RedisPool(RedisPoolSettings(uri=redis_url, db_num=0))
	lock = DistributedLock(pool)
	key = "test:locker:atomic"
	acquired_count = 0
	rejected_count = 0
	barrier = asyncio.Barrier(5)

	async def worker():
		nonlocal acquired_count, rejected_count
		await barrier.wait()
		try:
			async with lock.acq(key):
				acquired_count += 1
				await asyncio.sleep(0.5)
		except ContextLockError:
			rejected_count += 1

	tasks = [asyncio.create_task(worker()) for _ in range(5)]
	await asyncio.gather(*tasks)

	assert acquired_count == 1
	assert rejected_count == 4


# ── custom settings ───────────────────────────────────────────────


@pytest.mark.asyncio
async def test_with_custom_settings(redis_url: str, redis_client: Redis):
	pool = RedisPool(RedisPoolSettings(uri=redis_url, db_num=0))
	settings = DLSettings(
		wait=False,
		retry_if_acquired=True,
		acquire_timeout=10,
	)
	lock = DistributedLock(pool, settings)
	key = "test:locker:custom_settings"

	await redis_client.set(key, "acquired", ex=10)
	with pytest.raises(ContextLockError) as exc_info:
		async with lock.acq(key):
			pass
	assert exc_info.value.can_retry is True

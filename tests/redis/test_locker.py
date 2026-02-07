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

	async with lock.acquire(key):
		val = await redis_client.get(key)
		assert val is not None  # token stored as lock value

	val = await redis_client.get(key)
	assert val is None


@pytest.mark.asyncio
async def test_raises_when_already_acquired(redis_url: str, redis_client: Redis):
	pool = RedisPool(RedisPoolSettings(uri=redis_url, db_num=0))
	lock = DistributedLock(pool)
	key = "test:locker:conflict"

	await redis_client.set(key, "other_holder_token", ex=10)

	with pytest.raises(ContextLockError):
		async with lock.acquire(key):
			pass


# ── if_acquired / retry flag ──────────────────────────────────────


@pytest.mark.asyncio
async def test_if_acquired_retry_flag(redis_url: str, redis_client: Redis):
	pool = RedisPool(RedisPoolSettings(uri=redis_url, db_num=0))
	key = "test:locker:retry_flag"

	await redis_client.set(key, "other_holder", ex=10)

	dlock = DistributedLock(pool)
	with pytest.raises(ContextLockError) as exc_info:
		async with dlock.acquire(key):
			pass
	assert exc_info.value.can_retry is False

	await redis_client.set(key, "other_holder", ex=10)

	with pytest.raises(ContextLockError) as exc_info:
		async with dlock.if_taken(retry=True).acquire(key):
			pass
	assert exc_info.value.can_retry is True


# ── spin acquire ──────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_spin_acquires_free_lock(redis_url: str, redis_client: Redis):
	pool = RedisPool(RedisPoolSettings(uri=redis_url, db_num=0))
	lock = DistributedLock(pool).spin(attempts=3)
	key = "test:locker:spin_free"

	async with lock.acquire(key):
		val = await redis_client.get(key)
		assert val is not None

	val = await redis_client.get(key)
	assert val is None


@pytest.mark.asyncio
async def test_spin_fails_when_held(redis_url: str, redis_client: Redis):
	pool = RedisPool(RedisPoolSettings(uri=redis_url, db_num=0))
	lock = DistributedLock(pool).spin(attempts=3)
	key = "test:locker:spin_held"

	await redis_client.set(key, "other_holder", ex=30)

	with pytest.raises(ContextLockError):
		async with lock.acquire(key):
			pass

	val = await redis_client.get(key)
	assert val == "other_holder"


@pytest.mark.asyncio
async def test_spin_then_wait_fallback(redis_url: str, redis_client: Redis):
	pool = RedisPool(RedisPoolSettings(uri=redis_url, db_num=0))
	key = "test:locker:spin_wait"

	await redis_client.set(key, "other_holder", ex=1)

	lock = DistributedLock(pool).spin(attempts=3).wait(backoff=plain_delay(0.2), timeout=5.0)

	async with lock.acquire(key):
		val = await redis_client.get(key)
		assert val is not None

	val = await redis_client.get(key)
	assert val is None


@pytest.mark.asyncio
async def test_spin_then_wait_timeout(redis_url: str, redis_client: Redis):
	pool = RedisPool(RedisPoolSettings(uri=redis_url, db_num=0))
	key = "test:locker:spin_wait_timeout"

	await redis_client.set(key, "other_holder", ex=30)

	lock = DistributedLock(pool).spin(attempts=3).wait(backoff=plain_delay(0.05), timeout=0.3)

	with pytest.raises(ContextLockError) as exc_info:
		async with lock.acquire(key):
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

	await redis_client.set(key, "other_holder", ex=30)

	with pytest.raises(ContextLockError):
		async with lock.acquire(key):
			pass

	val = await redis_client.get(key)
	assert val == "other_holder"


def test_chained_calls_reuse_same_copy(redis_url: str):
	pool = RedisPool(RedisPoolSettings(uri=redis_url, db_num=0))
	original = DistributedLock(pool)

	first = original.wait(backoff=plain_delay(0.1), timeout=5.0)
	assert first is not original

	second = first.if_taken(retry=True)
	assert second is first

	third = first.spin(attempts=2)
	assert third is first


# ── wait for lock ─────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_waits_for_lock_release(redis_url: str, redis_client: Redis):
	pool = RedisPool(RedisPoolSettings(uri=redis_url, db_num=0))
	key = "test:locker:wait"

	await redis_client.set(key, "other_holder", ex=1)

	lock = DistributedLock(pool).wait(backoff=plain_delay(0.1), timeout=5.0)

	async with lock.acquire(key):
		val = await redis_client.get(key)
		assert val is not None


@pytest.mark.asyncio
async def test_wait_timeout(redis_url: str, redis_client: Redis):
	pool = RedisPool(RedisPoolSettings(uri=redis_url, db_num=0))
	key = "test:locker:wait_timeout"

	await redis_client.set(key, "other_holder", ex=30)

	lock = DistributedLock(pool).wait(backoff=plain_delay(0.05), timeout=0.3)

	with pytest.raises(ContextLockError) as exc_info:
		async with lock.acquire(key):
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

	await redis_client.set(key, "other_holder", ex=10)

	with pytest.raises(ContextLockError) as exc_info:
		async with lock.acquire(key):
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

	async with lock.acquire(MyKey()):
		val = await redis_client.get("test:locker:strable")
		assert val is not None

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

	modified_retry = original.if_taken(retry=True)
	assert modified_retry is not original
	assert modified_retry._retry_if_acquired is True
	assert original._retry_if_acquired is False


def test_chained_modifications(redis_url: str):
	pool = RedisPool(RedisPoolSettings(uri=redis_url, db_num=0))

	lock = DistributedLock(pool).wait(backoff=plain_delay(0.5), timeout=10.0).if_taken(retry=True)

	assert lock._wait is True
	assert lock._wait_timeout == 10.0
	assert lock._retry_if_acquired is True


# ── acquire timeout (TTL on redis key) ────────────────────────────


@pytest.mark.asyncio
async def test_acquire_timeout_sets_ttl(redis_url: str, redis_client: Redis):
	pool = RedisPool(RedisPoolSettings(uri=redis_url, db_num=0))
	lock = DistributedLock(pool)
	key = "test:locker:ttl"

	async with lock.acquire(key, ttl=10):
		ttl = await redis_client.ttl(key)
		assert 0 < ttl <= 10


# ── sequential contention ─────────────────────────────────────────


@pytest.mark.asyncio
async def test_sequential_contention(redis_url: str):
	pool = RedisPool(RedisPoolSettings(uri=redis_url, db_num=0))
	lock = DistributedLock(pool)
	key = "test:locker:sequential"

	async with lock.acquire(key):
		with pytest.raises(ContextLockError):
			async with lock.acquire(key):
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
			async with lock.acquire(key):
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
	)
	lock = DistributedLock(pool, settings)
	key = "test:locker:custom_settings"

	await redis_client.set(key, "other_holder", ex=10)
	with pytest.raises(ContextLockError) as exc_info:
		async with lock.acquire(key, ttl=10):
			pass
	assert exc_info.value.can_retry is True


# ── owner-safe release (CAS delete) ──────────────────────────────


@pytest.mark.asyncio
async def test_release_only_own_lock(redis_url: str, redis_client: Redis):
	"""Holder A's finally must NOT delete holder B's lock value."""
	pool = RedisPool(RedisPoolSettings(uri=redis_url, db_num=0))
	lock = DistributedLock(pool).extend(enabled=False)
	key = "test:locker:cas_release"

	# holder A acquires
	ctx = lock.acquire(key, ttl=2)
	gen = ctx.__aenter__()
	await gen

	# simulate TTL expiry + holder B acquiring
	await redis_client.set(key, "holder_b_token", ex=30)

	# holder A releases (finally block) — should NOT delete holder B's key
	try:
		await ctx.__aexit__(None, None, None)
	except Exception:
		pass

	val = await redis_client.get(key)
	assert val == "holder_b_token"


@pytest.mark.asyncio
async def test_token_is_unique_per_acquire(redis_url: str, redis_client: Redis):
	pool = RedisPool(RedisPoolSettings(uri=redis_url, db_num=0))
	lock = DistributedLock(pool)
	key = "test:locker:token_unique"

	tokens = []
	for _ in range(3):
		async with lock.acquire(key, ttl=5):
			tokens.append(await redis_client.get(key))

	assert len(set(tokens)) == 3


# ── TTL extension watchdog ────────────────────────────────────────


@pytest.mark.asyncio
async def test_ttl_extended_while_held(redis_url: str, redis_client: Redis):
	pool = RedisPool(RedisPoolSettings(uri=redis_url, db_num=0))
	lock = DistributedLock(pool)  # extend_ttl=True by default
	key = "test:locker:watchdog_extend"

	async with lock.acquire(key, ttl=2):
		# hold longer than TTL — watchdog should keep it alive
		await asyncio.sleep(3)
		val = await redis_client.get(key)
		assert val is not None

	val = await redis_client.get(key)
	assert val is None


@pytest.mark.asyncio
async def test_extend_disabled_ttl_expires(redis_url: str, redis_client: Redis):
	pool = RedisPool(RedisPoolSettings(uri=redis_url, db_num=0))
	lock = DistributedLock(pool).extend(enabled=False)
	key = "test:locker:no_watchdog"

	async with lock.acquire(key, ttl=1):
		await asyncio.sleep(2)
		val = await redis_client.get(key)
		assert val is None  # TTL expired, no watchdog to extend


@pytest.mark.asyncio
async def test_watchdog_stops_on_release(redis_url: str, redis_client: Redis):
	pool = RedisPool(RedisPoolSettings(uri=redis_url, db_num=0))
	lock = DistributedLock(pool)
	key = "test:locker:watchdog_stop"

	async with lock.acquire(key, ttl=5):
		pass  # release immediately

	# after release the key should be gone
	val = await redis_client.get(key)
	assert val is None

	# no lingering watchdog tasks from the locker
	await asyncio.sleep(0.1)
	for task in asyncio.all_tasks():
		coro = task.get_coro()
		if coro is not None and hasattr(coro, "__qualname__"):
			assert "DistributedLock._watchdog" not in coro.__qualname__


# ── extend builder ────────────────────────────────────────────────


def test_extend_builder_returns_copy(redis_url: str):
	pool = RedisPool(RedisPoolSettings(uri=redis_url, db_num=0))
	original = DistributedLock(pool)

	modified = original.extend(enabled=False)
	assert modified is not original
	assert modified._extend_ttl is False
	assert original._extend_ttl is True


def test_extend_builder_chains(redis_url: str):
	pool = RedisPool(RedisPoolSettings(uri=redis_url, db_num=0))
	lock = DistributedLock(pool).wait(timeout=5.0).extend(enabled=False)

	assert lock._wait is True
	assert lock._extend_ttl is False


def test_dl_settings_extend_ttl_default():
	settings = DLSettings()
	assert settings.extend_ttl is True

import pytest
from redis.asyncio import Redis

from sotkalib.redis.lru import LRUSettings, RedisLRU
from sotkalib.redis.pool import RedisPool, RedisPoolSettings
from sotkalib.serializer.impl.pickle import B64Pickle, SecurityWarning
from sotkalib.type.generics import strlike


@pytest.mark.asyncio
async def test_lru_caches_function_result(redis_url: str):
	"""Decorated function result is cached in Redis."""
	settings = RedisPoolSettings(uri=redis_url, db_num=0)
	pool = RedisPool(settings)

	call_count = 0

	def deterministic_keyfunc(version: int, func_name: str, *args, **kwargs) -> str:
		return f"test:{version}:{func_name}:{args}:{sorted(kwargs.items())}"

	lru = RedisLRU(pool).keyfunc(deterministic_keyfunc)

	@lru
	async def expensive_computation(x: int) -> int:
		nonlocal call_count
		call_count += 1
		return x * 2

	with pytest.warns(SecurityWarning):
		result1 = await expensive_computation(5)

	assert result1 == 10
	assert call_count == 1

	result2 = await expensive_computation(5)
	assert result2 == 10
	assert call_count == 1  # Should not increment - result was cached


@pytest.mark.asyncio
async def test_lru_different_args_different_cache(redis_url: str):
	"""Different arguments produce different cache entries."""
	settings = RedisPoolSettings(uri=redis_url, db_num=0)
	pool = RedisPool(settings)

	call_count = 0

	def deterministic_keyfunc(version: int, func_name: str, *args, **kwargs) -> str:
		return f"test:{version}:{func_name}:{args}:{sorted(kwargs.items())}"

	lru = RedisLRU(pool).keyfunc(deterministic_keyfunc)

	@lru
	async def add(a: int, b: int) -> int:
		nonlocal call_count
		call_count += 1
		return a + b

	with pytest.warns(SecurityWarning):
		result1 = await add(1, 2)
	assert result1 == 3
	assert call_count == 1

	with pytest.warns(SecurityWarning):
		result2 = await add(3, 4)
	assert result2 == 7
	assert call_count == 2  # Different args, so function was called again


@pytest.mark.asyncio
async def test_lru_with_ttl(redis_url: str, redis_client: Redis):
	"""Cache entries expire after TTL."""
	settings = RedisPoolSettings(uri=redis_url, db_num=0)
	pool = RedisPool(settings)

	def deterministic_keyfunc(version: int, func_name: str, *args, **kwargs) -> str:
		return f"ttl_test:{version}:{func_name}:{args}"

	lru = RedisLRU(pool).keyfunc(deterministic_keyfunc).ttl(60)

	@lru
	async def get_value() -> str:
		return "cached_value"

	with pytest.warns(SecurityWarning):
		await get_value()

	# Verify TTL was set on the cache key
	key = "ttl_test:1:get_value:()"
	ttl = await redis_client.ttl(key)
	assert ttl > 0
	assert ttl <= 60


@pytest.mark.asyncio
async def test_lru_with_version(redis_url: str):
	"""Different versions produce different cache entries."""
	settings = RedisPoolSettings(uri=redis_url, db_num=0)
	pool = RedisPool(settings)

	call_count = 0

	def deterministic_keyfunc(version: int, func_name: str, *args, **kwargs) -> str:
		return f"version_test:{version}:{func_name}:{args}"

	lru_v1 = RedisLRU(pool).keyfunc(deterministic_keyfunc).version(1)
	lru_v2 = RedisLRU(pool).keyfunc(deterministic_keyfunc).version(2)

	@lru_v1
	async def compute_v1() -> str:
		nonlocal call_count
		call_count += 1
		return "v1_result"

	@lru_v2
	async def compute_v2() -> str:
		nonlocal call_count
		call_count += 1
		return "v2_result"

	with pytest.warns(SecurityWarning):
		result1 = await compute_v1()
	assert result1 == "v1_result"
	assert call_count == 1

	with pytest.warns(SecurityWarning):
		result2 = await compute_v2()
	assert result2 == "v2_result"
	assert call_count == 2  # Different version, different cache


@pytest.mark.asyncio
async def test_lru_serializer_round_trip(redis_url: str):
	"""Complex objects are correctly serialized and deserialized."""
	settings = RedisPoolSettings(uri=redis_url, db_num=0)
	pool = RedisPool(settings)

	def deterministic_keyfunc(version: int, func_name: str, *args, **kwargs) -> str:
		return f"serialize_test:{version}:{func_name}:{args}"

	lru = RedisLRU(pool).keyfunc(deterministic_keyfunc)

	@lru
	async def get_complex_data() -> dict:
		return {"nested": {"key": [1, 2, 3]}, "value": "test"}

	with pytest.warns(SecurityWarning):
		result1 = await get_complex_data()
	assert result1 == {"nested": {"key": [1, 2, 3]}, "value": "test"}

	# Call again to get from cache

	result2 = await get_complex_data()
	assert result2 == {"nested": {"key": [1, 2, 3]}, "value": "test"}


@pytest.mark.asyncio
async def test_lru_with_kwargs(redis_url: str):
	"""Function with keyword arguments caches correctly."""
	settings = RedisPoolSettings(uri=redis_url, db_num=0)
	pool = RedisPool(settings)

	call_count = 0

	def deterministic_keyfunc(version: int, func_name: str, *args, **kwargs) -> str:
		return f"kwargs_test:{version}:{func_name}:{args}:{sorted(kwargs.items())}"

	lru = RedisLRU(pool).keyfunc(deterministic_keyfunc)

	@lru
	async def greet(name: str, greeting: str = "Hello") -> str:
		nonlocal call_count
		call_count += 1
		return f"{greeting}, {name}!"

	with pytest.warns(SecurityWarning):
		result1 = await greet("Alice", greeting="Hi")
	assert result1 == "Hi, Alice!"
	assert call_count == 1

	result2 = await greet("Alice", greeting="Hi")
	assert result2 == "Hi, Alice!"
	assert call_count == 1  # Cached

	with pytest.warns(SecurityWarning):
		result3 = await greet("Alice", greeting="Hey")
	assert result3 == "Hey, Alice!"
	assert call_count == 2  # Different kwargs, not cached


@pytest.mark.asyncio
async def test_lru_preserves_function_metadata(redis_url: str):
	"""Decorated function preserves original function's metadata."""
	settings = RedisPoolSettings(uri=redis_url, db_num=0)
	pool = RedisPool(settings)
	lru = RedisLRU(pool)

	@lru
	async def documented_function(x: int) -> int:
		"""This is the docstring."""
		return x

	assert documented_function.__name__ == "documented_function"
	assert documented_function.__doc__ == "This is the docstring."


@pytest.mark.asyncio
async def test_lru_chain_methods_return_copy(redis_url: str):
	"""with_* methods return a copy, not modifying original."""
	settings = RedisPoolSettings(uri=redis_url, db_num=0)
	pool = RedisPool(settings)

	original = RedisLRU(pool)
	original_ttl = original._ttl

	modified = original.ttl(999)

	assert original._ttl == original_ttl  # Original unchanged
	assert modified._ttl == 999
	assert original is not modified


@pytest.mark.asyncio
async def test_lru_chained_modifications(redis_url: str):
	"""Chained with_* calls work correctly."""
	settings = RedisPoolSettings(uri=redis_url, db_num=0)
	pool = RedisPool(settings)

	def custom_keyfunc(version: int, func_name: str, *args, **kwargs) -> str:
		return f"custom:{version}:{func_name}"

	lru = RedisLRU(pool).ttl(300).version(5).keyfunc(custom_keyfunc)

	assert lru._ttl == 300
	assert lru._version == 5
	assert lru._keyfunc is custom_keyfunc


@pytest.mark.asyncio
async def test_lru_with_custom_serializer(redis_url: str):
	"""Custom serializer is used for marshaling/unmarshaling."""
	settings = RedisPoolSettings(uri=redis_url, db_num=0)
	pool = RedisPool(settings)

	class JsonSerializer:
		marshal_called = False
		unmarshal_called = False

		@staticmethod
		def marshal(data) -> strlike:
			JsonSerializer.marshal_called = True
			import json

			return json.dumps(data).encode()

		@staticmethod
		def unmarshal(raw_data: strlike):
			JsonSerializer.unmarshal_called = True
			import json

			return json.loads(raw_data.decode())

	def deterministic_keyfunc(version: int, func_name: str, *args, **kwargs) -> str:
		return f"serializer_test:{version}:{func_name}:{args}"

	@RedisLRU(pool).serializer(JsonSerializer).keyfunc(deterministic_keyfunc)
	async def get_data() -> dict:
		return {"key": "value"}

	result = await get_data()
	assert result == {"key": "value"}
	assert JsonSerializer.marshal_called
	JsonSerializer.marshal_called = False

	# Second call uses cache, triggering unmarshal
	result2 = await get_data()
	assert result2 == {"key": "value"}
	assert JsonSerializer.unmarshal_called


def test_b64pickle_marshal_unmarshal():
	"""B64Pickle correctly round-trips data."""
	original = {"nested": [1, 2, 3], "key": "value"}
	with pytest.warns(SecurityWarning):
		marshaled = B64Pickle.marshal(original)
	assert isinstance(marshaled, bytes)

	unmarshaled = B64Pickle.unmarshal(marshaled)
	assert unmarshaled == original


def test_b64pickle_handles_various_types():
	"""B64Pickle handles various Python types."""
	test_cases = [
		None,
		42,
		3.14,
		"string",
		[1, 2, 3],
		{"a": 1, "b": 2},
		(1, 2, 3),
		{1, 2, 3},
	]

	for original in test_cases:
		with pytest.warns(SecurityWarning):
			marshaled = B64Pickle.marshal(original)
		unmarshaled = B64Pickle.unmarshal(marshaled)
		assert unmarshaled == original


def test_lru_settings_defaults():
	"""LRUSettings has correct defaults."""
	settings = LRUSettings()
	assert settings.version == 1
	assert settings.ttl == 600
	assert settings.serializer is B64Pickle

import pytest
from redis.asyncio import Redis

from sotkalib.redis.pool import RedisPool, RedisPoolSettings


@pytest.mark.asyncio
async def test_redis_pool_default_settings(redis_url: str):
	settings = RedisPoolSettings(uri=redis_url, db_num=0)
	async with RedisPool(settings) as client:
		assert isinstance(client, Redis)
		await client.set("test_key", "test_value")
		result = await client.get("test_key")
		assert result == "test_value"


@pytest.mark.asyncio
async def test_redis_pool_no_settings():
	pool = RedisPool()
	assert pool._pool is not None


@pytest.mark.asyncio
async def test_redis_pool_custom_settings(redis_url: str):
	settings = RedisPoolSettings(
		uri=redis_url,
		db_num=1,
		max_connections=10,
		socket_timeout=3,
		decode_responses=True,
	)
	async with RedisPool(settings) as client:
		# pyrefly: ignore [not-async]
		await client.ping()


@pytest.mark.asyncio
async def test_redis_pool_multiple_entries(redis_url: str):
	settings = RedisPoolSettings(uri=redis_url, db_num=0)
	pool = RedisPool(settings)

	async with pool as client1:
		await client1.set("k1", "v1")

	async with pool as client2:
		result = await client2.get("k1")
		assert result == "v1"

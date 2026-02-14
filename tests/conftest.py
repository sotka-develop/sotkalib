from collections.abc import AsyncGenerator

import pytest
import pytest_asyncio
from redis.asyncio import Redis
from testcontainers.redis import RedisContainer


@pytest.fixture(scope="session")
def redis_container():
	with RedisContainer("redis:8-alpine") as container:
		yield container


@pytest_asyncio.fixture
async def redis_client(redis_container: RedisContainer) -> AsyncGenerator[Redis]:
	host = redis_container.get_container_host_ip()
	port = redis_container.get_exposed_port(6379)
	client = Redis(host=host, port=int(port), decode_responses=True)
	yield client
	await client.flushdb()
	await client.aclose()


@pytest.fixture
def redis_url(redis_container: RedisContainer) -> str:
	host = redis_container.get_container_host_ip()
	port = redis_container.get_exposed_port(6379)
	return f"redis://{host}:{port}"

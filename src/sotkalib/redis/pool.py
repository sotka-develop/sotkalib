import asyncio
from contextlib import AbstractAsyncContextManager
from typing import Self

from pydantic import BaseModel, Field
from redis.asyncio import ConnectionPool, Redis


class RedisPoolSettings(BaseModel):
	uri: str = Field(default="redis://localhost:6379")
	db_num: int = Field(default=4)
	max_connections: int = Field(default=50)
	socket_timeout: float = Field(default=5)
	socket_connect_timeout: float = Field(default=5)
	retry_on_timeout: bool = Field(default=True)
	health_check_interval: float = Field(default=30)
	decode_responses: bool = Field(default=True)


class RedisPool(AbstractAsyncContextManager):
	def __init__(self, settings: RedisPoolSettings | None = None):
		if not settings:
			settings = RedisPoolSettings()

		self._pool = ConnectionPool.from_url(
			settings.uri + "/" + str(settings.db_num),
			**settings.model_dump(exclude={"uri", "db_num"}),
		)

		self._usage_counter = 0
		self._usage_lock = asyncio.Lock()

	async def __aenter__(self: Self) -> Redis:
		try:
			return Redis(connection_pool=self._pool)
		except Exception:
			raise

	async def __aexit__(self, exc_type, exc_value, traceback): ...

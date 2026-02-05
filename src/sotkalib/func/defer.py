from collections.abc import AsyncGenerator, Awaitable
from contextlib import asynccontextmanager


@asynccontextmanager
async def defer(to_await: Awaitable) -> AsyncGenerator[None]:
	try:
		yield
	finally:
		await to_await


@asynccontextmanager
async def defer_ok(to_await: Awaitable) -> AsyncGenerator[None]:
	try:
		yield
	except Exception:
		raise
	else:
		await to_await

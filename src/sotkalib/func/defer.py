from collections.abc import AsyncGenerator, Awaitable, Sequence
from contextlib import asynccontextmanager


async def _await(to_await: Awaitable | Sequence[Awaitable]):
	if isinstance(to_await, Awaitable):
		await to_await

	else:
		for a in to_await:
			await a


@asynccontextmanager
async def defer(*to_await: Awaitable) -> AsyncGenerator[None]:
	try:
		yield
	finally:
		await _await(to_await)


@asynccontextmanager
async def defer_ok(*to_await: Awaitable) -> AsyncGenerator[None]:
	try:
		yield
	except:
		raise
	else:
		await _await(to_await)


@asynccontextmanager
async def defer_exc(*to_await: Awaitable) -> AsyncGenerator[None]:
	try:
		yield
	except:
		await _await(to_await)
		raise


@asynccontextmanager
async def defer_exc_mute(*to_await: Awaitable) -> AsyncGenerator[None]:
	try:
		yield
	except Exception as e:
		_ = e
		await _await(to_await)

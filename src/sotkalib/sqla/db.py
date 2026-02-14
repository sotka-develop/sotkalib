import functools
import inspect
from collections.abc import AsyncGenerator, Callable, Coroutine, Generator
from contextlib import (
	AbstractAsyncContextManager,
	AbstractContextManager,
	asynccontextmanager,
	contextmanager,
)
from typing import Concatenate, Self, overload

from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy import create_engine
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine
from sqlalchemy.ext.asyncio.session import AsyncSession
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker

from sotkalib.log import get_logger


class ConnectionTimeoutError(Exception):
	pass


class DatabaseSettings(BaseModel):
	model_config = ConfigDict(arbitrary_types_allowed=True)

	uri: str = Field(examples=["postgresql://username:password@localhost:5432/database"])
	async_driver: str | None = "psycopg"
	enable_sync_engine: bool = True
	echo: bool = False
	pool_size: int = 10
	expire_on_commit: bool = False
	decl_base: type[DeclarativeBase] | None = None
	implicit_safe: bool = True

	@property
	def async_uri(self) -> str:
		if self.async_driver is None:
			raise ValueError("tried to get async uri when driver is not passed")
		return self.uri.replace("postgresql://", "postgresql+" + self.async_driver + "://")


type _ASM = AbstractAsyncContextManager[AsyncSession]
type _SSM = AbstractContextManager[Session]
type _Coro[T] = Coroutine[None, None, T]
type _SyncMethod[Self, **Ps, R] = Callable[Concatenate[Self, Ps], R]
type _AsyncMethod[Self, **Ps, R] = Callable[Concatenate[Self, Ps], _Coro[R]]


@overload
def _raise_on_uninitialized[**Ps, R](
	func: _SyncMethod["Database", Ps, R],
) -> _SyncMethod["Database", Ps, R]: ...
@overload
def _raise_on_uninitialized[**Ps, R](
	func: _AsyncMethod["Database", Ps, R],
) -> _AsyncMethod["Database", Ps, R]: ...


def _raise_on_uninitialized[**Ps, R](
	func: _SyncMethod["Database", Ps, R] | _AsyncMethod["Database", Ps, R],
) -> _SyncMethod["Database", Ps, R] | _AsyncMethod["Database", Ps, R]:
	if inspect.iscoroutinefunction(func):

		async def _awrap(self: "Database", *args: Ps.args, **kwargs: Ps.kwargs) -> R:
			if not self._async_enabled:
				raise RuntimeError("async engine is not initialized for this instance")
			return await func(self, *args, **kwargs)  # type:ignore

		return functools.wraps(_awrap)(func)

	def _swrap(self: "Database", *args: Ps.args, **kwargs: Ps.kwargs) -> R:
		if not self._sync_enabled:
			raise RuntimeError("sync engine is not initialized for this instance")
		return func(self, *args, **kwargs)  # type:ignore

	return functools.wraps(_swrap)(func)  # type:ignore


class Database:
	__slots__ = (
		"_decl_base",
		"_implicit_safe",
		"_sync_engine",
		"_sync_session_factory",
		"_async_enabled",
		"_async_engine",
		"_async_session_factory",
		"_sync_enabled",
	)

	def __init__(self, settings: DatabaseSettings):
		self._decl_base = settings.decl_base

		self._implicit_safe = settings.implicit_safe

		self._sync_enabled = settings.enable_sync_engine

		if self._sync_enabled:
			self._sync_engine = create_engine(
				url=settings.uri,
				echo=settings.echo,
				pool_size=settings.pool_size,
			)
			self._sync_session_factory = sessionmaker(
				bind=self._sync_engine,
				expire_on_commit=settings.expire_on_commit,
			)

		self._async_enabled = settings.async_driver is not None

		if self._async_enabled:
			self._async_engine = create_async_engine(
				url=settings.async_uri,
				echo=settings.echo,
				pool_size=settings.pool_size,
			)
			self._async_session_factory = async_sessionmaker(
				bind=self._async_engine,
				expire_on_commit=settings.expire_on_commit,
			)

	@_raise_on_uninitialized
	def __enter__(self) -> Self:
		return self

	def __exit__(self, exc_type, exc_val, exc_tb):
		self.close()

	@_raise_on_uninitialized
	async def __aenter__(self) -> Self:
		return self

	async def __aexit__(self, *args):
		await self.aclose()

	@_raise_on_uninitialized
	def create(self):
		if self._decl_base is None:
			raise ValueError("create called when decl_base is None")

		with self._sync_engine.begin() as conn:
			self._decl_base.metadata.create_all(conn)

	@_raise_on_uninitialized
	async def acreate(self):
		if self._decl_base is None:
			raise ValueError("create called when decl_base is None")

		async with self._async_engine.begin() as aconn:
			await aconn.run_sync(self._decl_base.metadata.create_all)

	@_raise_on_uninitialized
	def drop(self):
		if self._decl_base is None:
			raise ValueError("drop called when decl_base is None")

		with self._sync_engine.begin() as conn:
			self._decl_base.metadata.drop_all(conn)

	@_raise_on_uninitialized
	async def adrop(self):
		if self._decl_base is None:
			raise ValueError("drop called when decl_base is None")

		async with self._async_engine.begin() as aconn:
			await aconn.run_sync(self._decl_base.metadata.drop_all)

	@property
	@_raise_on_uninitialized
	def asession_unsafe(self) -> _ASM:
		return self._async_session_factory()

	@property
	@_raise_on_uninitialized
	def asession_safe(self) -> _ASM:
		return _asafe(self._async_session_factory)

	@property
	def asession(self) -> _ASM:
		if self._implicit_safe:
			return self.asession_safe
		return self.asession_unsafe

	@property
	def async_session(self) -> _ASM:
		return self.asession

	@property
	def session_unsafe(self) -> _SSM:
		return self._sync_session_factory()

	@property
	def session_safe(self) -> _SSM:
		return _safe(self._sync_session_factory)

	@property
	@_raise_on_uninitialized
	def session(self) -> _SSM:
		if self._implicit_safe:
			return self.session_safe
		return self.session_unsafe

	async def aclose(self):
		if self._async_enabled:
			await self._async_engine.dispose()
			get_logger("db").debug("disposed of async engine")

	def close(self):
		if self._sync_enabled:
			self._sync_engine.dispose()
			get_logger("db").debug("disposed of sync engine")


def _safe(sm: sessionmaker[Session]) -> _SSM:
	@contextmanager
	def _() -> Generator[Session]:
		session: Session = None

		try:
			session = sm()
			yield session
			session.commit()
		except:
			if session is not None:
				session.rollback()
			raise
		finally:
			if session is not None:
				session.close()

	return _()


def _asafe(asm: async_sessionmaker[AsyncSession]) -> _ASM:

	@asynccontextmanager
	async def _() -> AsyncGenerator[AsyncSession]:
		session: AsyncSession = None

		try:
			session = asm()
			yield session
			await session.commit()
		except:
			if session is not None:
				await session.rollback()
			raise
		finally:
			if session is not None:
				await session.close()

	return _()

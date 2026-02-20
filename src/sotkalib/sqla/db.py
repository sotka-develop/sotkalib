import functools
import inspect
from collections.abc import AsyncGenerator, Generator
from contextlib import (
	asynccontextmanager,
	contextmanager,
)
from dataclasses import dataclass
from typing import Self, overload

from sqlalchemy import create_engine
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine
from sqlalchemy.ext.asyncio.session import AsyncSession
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker

from sotkalib.log import get_logger
from sotkalib.type.generics import any_method, async_contextmgr, async_method, contextmgr, coro, method


@overload
def _raise_on_uninitialized[**p, r](
	func: method["Database", p, r],
) -> method["Database", p, r]: ...
@overload
def _raise_on_uninitialized[**p, r](
	func: async_method["Database", p, r],
) -> async_method["Database", p, r]: ...


def _raise_on_uninitialized[**p, r](func: any_method["Database", p, r]) -> any_method["Database", p, r]:
	@functools.wraps(func)
	def _wrap(self: "Database", *args: p.args, **kwargs: p.kwargs) -> r | coro[r]:
		if inspect.iscoroutinefunction(func):
			if not self._async_enabled:
				raise RuntimeError("async engine is not initialized for this instance")
		elif not self._sync_enabled:
			raise RuntimeError("sync engine is not initialized for this instance")

		return func(self, *args, **kwargs)

	return _wrap


class ConnectionTimeoutError(Exception):
	pass


@dataclass(slots=True, kw_only=True)
class DatabaseSettings:
	uri: str
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
		self._async_enabled = settings.async_driver is not None

		if not self._sync_enabled and not self._async_enabled:
			raise RuntimeError("either one or both of modes must be specified")

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

	@_raise_on_uninitialized
	def __exit__(self, exc_type, exc_val, exc_tb) -> None:
		self.close()

	@_raise_on_uninitialized
	async def __aenter__(self) -> Self:
		return self

	@_raise_on_uninitialized
	async def __aexit__(self, *args) -> None:
		await self.aclose()

	@_raise_on_uninitialized
	def create(self) -> None:
		if self._decl_base is None:
			raise ValueError("create called when decl_base is None")

		with self._sync_engine.begin() as conn:
			self._decl_base.metadata.create_all(conn)

	@_raise_on_uninitialized
	async def acreate(self) -> None:
		if self._decl_base is None:
			raise ValueError("create called when decl_base is None")

		async with self._async_engine.begin() as aconn:
			await aconn.run_sync(self._decl_base.metadata.create_all)  # type:ignore

	@_raise_on_uninitialized
	def drop(self) -> None:
		if self._decl_base is None:
			raise ValueError("drop called when decl_base is None")

		with self._sync_engine.begin() as conn:
			self._decl_base.metadata.drop_all(conn)

	@_raise_on_uninitialized
	async def adrop(self) -> None:
		if self._decl_base is None:
			raise ValueError("drop called when decl_base is None")

		async with self._async_engine.begin() as aconn:
			await aconn.run_sync(self._decl_base.metadata.drop_all)  # type:ignore

	@property
	@_raise_on_uninitialized
	def asession_unsafe(self) -> async_contextmgr[AsyncSession]:
		return self._async_session_factory()

	@property
	@_raise_on_uninitialized
	def asession_safe(self) -> async_contextmgr[AsyncSession]:
		return _asafe(self._async_session_factory)

	@property
	def asession(self) -> async_contextmgr[AsyncSession]:
		return self.asession_safe if self._implicit_safe else self.asession_unsafe

	@property
	def async_session(self) -> async_contextmgr[AsyncSession]:
		return self.asession

	@property
	def session_unsafe(self) -> contextmgr[Session]:
		return self._sync_session_factory()

	@property
	def session_safe(self) -> contextmgr[Session]:
		return _safe(self._sync_session_factory)

	@property
	@_raise_on_uninitialized
	def session(self) -> contextmgr[Session]:
		return self.session_safe if self._implicit_safe else self.session_unsafe

	async def aclose(self):
		if self._async_enabled:
			await self._async_engine.dispose()
			get_logger("db").debug("disposed of async engine")

	def close(self):
		if self._sync_enabled:
			self._sync_engine.dispose()
			get_logger("db").debug("disposed of sync engine")


@contextmanager
def _safe(sm: sessionmaker[Session]) -> Generator[Session]:
	session = None

	try:
		session: Session = sm()
		yield session
		session.commit()
	except:
		if session is not None:
			session.rollback()
		raise
	finally:
		if session is not None:
			session.close()


@asynccontextmanager
async def _asafe(asm: async_sessionmaker[AsyncSession]) -> AsyncGenerator[AsyncSession]:
	session = None

	try:
		session: AsyncSession = asm()
		yield session
		await session.commit()
	except:
		if session is not None:
			await session.rollback()
		raise
	finally:
		if session is not None:
			await session.close()

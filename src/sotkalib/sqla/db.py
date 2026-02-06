from collections.abc import AsyncGenerator, Generator
from contextlib import (
	AbstractAsyncContextManager,
	AbstractContextManager,
	asynccontextmanager,
	contextmanager,
)

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
	echo: bool = False
	pool_size: int = 10
	expire_on_commit: bool = False
	decl_base: DeclarativeBase | None = None
	explicit_safe: bool = True

	@property
	def async_uri(self) -> str:
		if self.async_driver is None:
			raise ValueError("tried to get async uri when driver is not passed")
		return self.uri.replace("postgresql://", "postgresql+" + self.async_driver + "://")


type AsyncSM = AbstractAsyncContextManager[AsyncSession]
type SyncSM = AbstractContextManager[Session]


class Database:
	__slots__ = (
		"_decl_base",
		"_explicit_safe",
		"_sync_engine",
		"_sync_session_factory",
		"_has_async",
		"_async_engine",
		"_async_session_factory",
	)

	def __init__(self, settings: DatabaseSettings):
		self._decl_base = settings.decl_base

		self._explicit_safe = settings.explicit_safe

		self._sync_engine = create_engine(
			url=settings.uri,
			echo=settings.echo,
			pool_size=settings.pool_size,
		)
		self._sync_session_factory = sessionmaker(
			bind=self._sync_engine,
			expire_on_commit=settings.expire_on_commit,
		)

		self._has_async = settings.async_driver is not None

		if self._has_async:
			self._async_engine = create_async_engine(
				url=settings.async_uri,
				echo=settings.echo,
				pool_size=settings.pool_size,
			)
			self._async_session_factory = async_sessionmaker(
				bind=self._async_engine,
				expire_on_commit=settings.expire_on_commit,
			)

	def __enter__(self):
		return self

	def __exit__(self, exc_type, exc_val, exc_tb):
		self._sync_engine.dispose()
		get_logger("db").info("gracefully closed sync engine")

	async def __aenter__(self):
		if not self._has_async:
			raise ValueError("async engine is not initialized for this instance")
		return self

	async def __aexit__(self, *args):
		await self.aclose()

	def create(self):
		if self._decl_base is None:
			raise ValueError("create called when decl_base is None")

		self._decl_base.metadata.create_all(self._sync_engine)

	@property
	def asession_unsafe(self) -> AsyncSM:
		if not self._has_async:
			raise ValueError("async sf is not initialized for this instance")
		return self._async_session_factory()

	@property
	def asession_safe(self) -> AsyncSM:
		if not self._has_async:
			raise ValueError("async sf is not initialized for this instance")
		return _asafe(self._async_session_factory)

	@property
	def asession(self) -> AsyncSM:
		if self._explicit_safe:
			return self.asession_safe
		return self.asession_unsafe

	@property
	def async_session(self) -> AsyncSM:
		return self.asession

	@property
	def session_unsafe(self) -> SyncSM:
		return self._sync_session_factory()

	@property
	def session_safe(self) -> SyncSM:
		return _safe(self._sync_session_factory)

	@property
	def session(self) -> SyncSM:
		if self._explicit_safe:
			return self.session_safe
		return self.session_unsafe

	async def aclose(self):
		if self._has_async:
			await self._async_engine.dispose()
			get_logger("db").debug("disposed of async engine")

	def close(self):
		self._sync_engine.dispose()
		get_logger("db").debug("disposed of sync engine")


def _safe(sm: sessionmaker[Session]) -> SyncSM:
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


def _asafe(asm: async_sessionmaker[AsyncSession]) -> AsyncSM:

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

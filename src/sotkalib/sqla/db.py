from pydantic import BaseModel, Field
from sqlalchemy import create_engine, Engine
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine, AsyncEngine
from sqlalchemy.ext.asyncio.session import AsyncSession
from sqlalchemy.orm import Session, sessionmaker

from sotkalib.log import get_logger

class ConnectionTimeoutError(Exception): pass

class DatabaseSettings(BaseModel):
    uri: str = Field(examples=[
        "postgresql://username:password@localhost:5432/database"
    ])
    async_driver: str = "asyncpg"
    echo: bool = False
    pool_size: int = 10

    @property
    def async_uri(self) -> str:
        return self.uri.replace("postgresql://", "postgresql" + self.async_driver + "://")

class Database:
    _sync_engine: Engine | None
    _async_engine: AsyncEngine | None
    _sync_session_factory: sessionmaker = None
    _async_session_factory: async_sessionmaker = None

    logger = get_logger("sqldb.instance")

    def __init__(self, settings: DatabaseSettings):
        self.__async_uri = settings.async_uri
        self.__sync_uri = settings.uri
        self.echo = settings.echo
        self.pool_size = settings.pool_size

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        if self._sync_engine:
            self._sync_engine.dispose()
            self.logger.info("closed sync db connection")

    async def __aenter__(self):
        return self

    async def __aexit__(self, *args):
        if self._async_engine:
            await self._async_engine.dispose()
            self.logger.info("closed async db connection")

    def __async_init(self):
        self._async_engine = create_async_engine(
            url=self.__async_uri,
            echo=self.echo,
            pool_size=self.pool_size,
        )
        self._async_session_factory = async_sessionmaker(bind=self._async_engine, expire_on_commit=False)
        self.logger.debug(  # noqa: PLE1205
            "successfully initialized async db connection, engine.status = {} sessionmaker.status = {}",
            self._async_engine.name is not None,
            self._async_session_factory is not None,
            )

    @property
    def async_session(self) -> async_sessionmaker[AsyncSession]:
        if self._async_engine is None or self._async_session_factory is None:
            self.logger.debug("async_sf not found, initializing")
            self.__async_init()
            if self._async_engine is None or self._async_session_factory is None:
                self.logger.error(c := "could not asynchronously connect to pgsql")
                raise ConnectionTimeoutError(c)
        self.logger.debug("success getting (asyncmaker)")
        return self._async_session_factory

    def __sync_init(self):
        self._sync_engine = create_engine(
            url=self.__sync_uri,
            echo=self.echo,
            pool_size=self.pool_size,
        )
        self._sync_session_factory = sessionmaker(bind=self._sync_engine, expire_on_commit=False)
        self.logger.debug(  # noqa
            " -> (__sync_init) successfully initialized sync db connection,\n"
            "\t\t\t\tengine.status = {} sessionmaker.status = {}",
            self._sync_engine.name is not None,
            self._sync_session_factory is not None,
            )

    @property
    def session(self) -> sessionmaker[Session]:
        if self._sync_engine is None or self._sync_session_factory is None:
            self.logger.debug("not found, initializing...")
            self.__sync_init()
            if self._sync_engine is None or self._sync_session_factory is None:
                self.logger.error(c := "could not synchronously connect to pgsql")
                raise ConnectionTimeoutError(c)
        self.logger.debug("success getting (syncmaker)")
        return self._sync_session_factory

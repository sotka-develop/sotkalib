from collections.abc import AsyncGenerator

import pytest
import pytest_asyncio
from sqlalchemy.ext.asyncio import AsyncSession
from testcontainers.postgres import PostgresContainer

from sotkalib.sqla import Database


@pytest.fixture(scope="session")
def pg_container():
	with PostgresContainer("postgres:18-alpine") as pg:
		yield pg


@pytest.fixture(scope="session")
def pg_url(pg_container: PostgresContainer) -> str:
	host = pg_container.get_container_host_ip()
	port = pg_container.get_exposed_port(5432)
	user = pg_container.username
	password = pg_container.password
	dbname = pg_container.dbname
	return f"postgresql://{user}:{password}@{host}:{port}/{dbname}"


@pytest_asyncio.fixture
async def session(_db: Database) -> AsyncGenerator[AsyncSession]:
	async with _db.asession_unsafe as session:
		yield session
		await session.rollback()

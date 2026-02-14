from collections.abc import AsyncGenerator

import pytest
import pytest_asyncio
from sqlalchemy import Column, ForeignKey, Integer, String, Table
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import relationship, selectinload

from sotkalib.sqla import BaseRepository, BasicDBM, Database, DatabaseSettings
from sotkalib.sqla.repo import NotFoundError

pytestmark = pytest.mark.asyncio

author_book = Table(
	"author_book",
	BasicDBM.metadata,
	Column("author_id", Integer, ForeignKey("authors.id"), primary_key=True),
	Column("book_id", Integer, ForeignKey("books.id"), primary_key=True),
)

Base = BasicDBM


@pytest_asyncio.fixture(scope="session")
async def _db(pg_url: str) -> AsyncGenerator[Database]:
	async with Database(settings=DatabaseSettings(uri=pg_url, async_driver="psycopg", decl_base=Base)) as db:
		await db.acreate()
		yield db
		await db.adrop()


class Author(Base):
	__tablename__ = "authors"

	id = Column(Integer, primary_key=True)
	name = Column(String(100), nullable=False)

	books = relationship("Book", secondary=author_book, back_populates="authors", lazy="noload")


class Book(Base):
	__tablename__ = "books"

	id = Column(Integer, primary_key=True)
	title = Column(String(200), nullable=False)

	authors = relationship("Author", secondary=author_book, back_populates="books", lazy="noload")


class AuthorRepo(BaseRepository[Author, int]):
	model = Author


class BookRepo(BaseRepository[Book, int]):
	model = Book


class TestCreate:
	async def test_create_returns_instance(self, author_repo: AuthorRepo):
		author = await author_repo.create(name="Tolkien")
		assert author.id is not None
		assert author.name == "Tolkien"

	async def test_create_rejects_missing_required(self, author_repo: AuthorRepo):
		with pytest.raises(KeyError):
			await author_repo.create()


class TestOne:
	async def test_one_returns_existing(self, author_repo: AuthorRepo):
		author = await author_repo.create(name="Orwell")
		found = await author_repo.one(author.id)
		assert found is not None
		assert found.name == "Orwell"

	async def test_one_returns_none_for_missing(self, author_repo: AuthorRepo):
		assert await author_repo.one(999_999) is None


class TestExists:
	async def test_exists_true(self, author_repo: AuthorRepo):
		author = await author_repo.create(name="Huxley")
		assert await author_repo.exists(author.id) is True

	async def test_exists_false(self, author_repo: AuthorRepo):
		assert await author_repo.exists(999_999) is False


class TestUpdate:
	async def test_update_returns_modified(self, author_repo: AuthorRepo):
		author = await author_repo.create(name="Pratchet")
		updated = await author_repo.update(author.id, name="Pratchett")
		assert updated.name == "Pratchett"
		assert updated.id == author.id

	async def test_update_validates_nonexistent_attrs(self, author_repo: AuthorRepo):
		author = await author_repo.create(name="Pratchet")
		with pytest.raises(AttributeError):
			author.merge(strict=True, hzchoto=True)

	async def test_update_validates_overriding_pk(self, author_repo: AuthorRepo):
		author = await author_repo.create(name="Pratchet")
		with pytest.raises(AttributeError):
			author.merge(strict=True, id=999)

	async def test_update_raises_not_found(self, author_repo: AuthorRepo):
		with pytest.raises(NotFoundError):
			await author_repo.update(999_999, name="Ghost")


class TestDelete:
	async def test_delete_removes_instance(self, author_repo: AuthorRepo):
		author = await author_repo.create(name="Deleteme")
		await author_repo.delete(author.id)
		assert await author_repo.one(author.id) is None

	async def test_delete_raises_not_found(self, author_repo: AuthorRepo):
		with pytest.raises(NotFoundError):
			await author_repo.delete(999_999)


class TestMany:
	async def test_many_returns_all(self, author_repo: AuthorRepo):
		await author_repo.create(name="Many-A")
		await author_repo.create(name="Many-B")
		results = await author_repo.many()
		names = {a.name for a in results}
		assert "Many-A" in names
		assert "Many-B" in names

	async def test_many_pagination(self, author_repo: AuthorRepo):
		for i in range(5):
			await author_repo.create(name=f"Page-{i}")
		page = await author_repo.many(page=1, page_size=2)
		assert len(page) == 2

	async def test_many_with_where(self, author_repo: AuthorRepo):
		await author_repo.create(name="Where-Target")
		results = await author_repo.many(where=[Author.name == "Where-Target"])
		assert all(a.name == "Where-Target" for a in results)


class TestCreateMany:
	async def test_create_many_returns_all(self, author_repo: AuthorRepo):
		authors = await author_repo.create_many(
			[
				{"name": "Bulk-A"},
				{"name": "Bulk-B"},
				{"name": "Bulk-C"},
			]
		)
		assert len(authors) == 3
		assert all(a.id is not None for a in authors)
		assert {a.name for a in authors} == {"Bulk-A", "Bulk-B", "Bulk-C"}

	async def test_create_many_validates_each(self, author_repo: AuthorRepo):
		with pytest.raises(KeyError):
			await author_repo.create_many([{"name": "OK"}, {}])


class TestDeleteMany:
	async def test_delete_many_removes_all(self, author_repo: AuthorRepo):
		authors = await author_repo.create_many(
			[
				{"name": "Del-A"},
				{"name": "Del-B"},
			]
		)
		ids = [a.id for a in authors]
		await author_repo.delete_many(ids)
		for aid in ids:
			assert await author_repo.one(aid) is None

	async def test_delete_many_raises_for_missing(self, author_repo: AuthorRepo):
		author = await author_repo.create(name="Del-C")
		with pytest.raises(NotFoundError):
			await author_repo.delete_many([author.id, 999_999])


class TestEagerLoadOptions:
	async def test_one_with_options_loads_relation(self, author_repo: AuthorRepo, book_repo: BookRepo, session):
		author = await author_repo.create(name="Eco")
		book = await book_repo.create(title="Name of the Rose")
		# link via m2m
		author.books.append(book)
		await session.flush()

		loaded = await author_repo.one(author.id, options=[selectinload(Author.books)])
		assert loaded is not None
		assert len(loaded.books) == 1
		assert loaded.books[0].title == "Name of the Rose"

	async def test_many_with_options(self, author_repo: AuthorRepo, book_repo: BookRepo, session):
		a = await author_repo.create(name="Opts-Many")
		b = await book_repo.create(title="Opts-Book")
		a.books.append(b)
		await session.flush()

		results = await author_repo.many(
			where=[Author.name == "Opts-Many"],
			options=[selectinload(Author.books)],
			unique=True,
		)
		assert len(results) == 1
		assert len(results[0].books) == 1


@pytest.fixture
def author_repo(session: AsyncSession) -> AuthorRepo:
	return AuthorRepo(session)


@pytest.fixture
def book_repo(session: AsyncSession) -> BookRepo:
	return BookRepo(session)

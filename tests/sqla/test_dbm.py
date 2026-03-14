import pytest
from pydantic import BaseModel
from sqlalchemy import Column, Integer, String, Text
from sqlalchemy.orm import defer

from sotkalib.sqla import BasicDBM as BasicDBM_
from sotkalib.sqla import Database
from sotkalib.sqla.db import DatabaseSettings

BasicDBM = BasicDBM_


class User(BasicDBM):
	__tablename__ = "users"

	id = Column(Integer, primary_key=True)
	name = Column(String(50))
	email = Column(String(100))
	bio = Column(Text, nullable=True)

	@property
	def name_upper(self) -> str:
		return self.name.upper() if self.name else ""


class UserOut(BaseModel):
	id: int
	name: str
	email: str


class UserWithProp(BaseModel):
	name: str
	name_upper: str


class UserPartial(BaseModel):
	name: str
	bio: str | None


@pytest.fixture()
def db():
	with Database(
		DatabaseSettings(uri="sqlite:///:memory:", async_driver=None, decl_base=BasicDBM)
	) as db:
		db.create()
		yield db


@pytest.fixture()
def user(db: Database):
	with db.session as session:
		u = User(id=1, name="John", email="john@test.com", bio="developer")
		session.add(u)
		session.commit()
		session.refresh(u)
		yield u


@pytest.fixture()
def user_no_bio(db: Database):
	with db.session as session:
		u = User(id=2, name="Jane", email="jane@test.com", bio=None)
		session.add(u)
		session.commit()
		session.refresh(u)
		yield u


# ── dict() ──────────────────────────────────────────────────────────────


class TestDict:
	def test_returns_all_columns(self, user: User):
		result = user.dict()
		assert result == {
			"id": 1,
			"name": "John",
			"email": "john@test.com",
			"bio": "developer",
		}

	def test_with_none_value(self, user_no_bio: User):
		result = user_no_bio.dict()
		assert result["bio"] is None

	def test_with_extra_kwargs(self, user: User):
		result = user.dict(extra="value", another=42)
		assert result["extra"] == "value"
		assert result["another"] == 42
		assert result["name"] == "John"

	def test_extra_kwargs_override_columns(self, user: User):
		result = user.dict(name="OVERRIDE")
		assert result["name"] == "OVERRIDE"

	def test_pydantic_model_filters_columns(self, user: User):
		result = user.dict(pydantic_model=UserOut)
		assert set(result.keys()) == {"id", "name", "email"}
		assert "bio" not in result

	def test_pydantic_model_partial(self, user: User):
		result = user.dict(pydantic_model=UserPartial)
		assert set(result.keys()) == {"name", "bio"}
		assert result["name"] == "John"
		assert result["bio"] == "developer"

	def test_explicitly_include(self, user: User):
		result = user.dict(explicitly_include=["name", "email"])
		assert set(result.keys()) == {"name", "email"}

	def test_explicitly_include_with_pydantic_intersection(self, user: User):
		# UserOut has {id, name, email}; explicitly_include has {name, bio}
		# intersection should be {name}
		result = user.dict(pydantic_model=UserOut, explicitly_include=["name", "bio"])
		assert "name" in result
		assert "bio" not in result
		assert "id" not in result

	def test_pydantic_model_includes_properties(self, user: User):
		result = user.dict(pydantic_model=UserWithProp)
		assert result["name"] == "John"
		assert result["name_upper"] == "JOHN"

	def test_empty_explicitly_include_dumps_all(self, user: User):
		result = user.dict(explicitly_include=[])
		assert set(result.keys()) == {"id", "name", "email", "bio"}


# ── is_loaded() ─────────────────────────────────────────────────────────


class TestIsLoaded:
	def test_loaded_attr_returns_true(self, user: User):
		assert user.is_loaded(attr="name") is True
		assert user.is_loaded(attr="email") is True

	def test_deferred_attr_returns_false(self, db: Database):
		with db.session as session:
			u = User(id=10, name="Deferred", email="def@test.com", bio="text")
			session.add(u)
			session.commit()
			session.expunge(u)

			loaded = session.query(User).options(defer(User.bio)).filter_by(id=10).one()
			assert loaded.is_loaded(attr="name") is True
			assert loaded.is_loaded(attr="bio") is False

	def test_nonexistent_attr_raises_key_error(self, user: User):
		with pytest.raises(KeyError):
			user.is_loaded(attr="nonexistent_field")


# ── merge() ──────────────────────────────────────────────────────────────


class TestMerge:
	def test_merge_updates_attrs(self, db: Database, user: User):
		user.merge(name="Updated", email="updated@test.com")
		assert user.name == "Updated"
		assert user.email == "updated@test.com"

	def test_merge_skips_unchanged(self, user: User):
		user.merge(name="John")  # same value
		assert user.name == "John"

	def test_merge_skips_unknown_attrs_non_strict(self, user: User):
		# should not raise, just ignore
		user.merge(nonexistent="value")
		assert not hasattr(user, "nonexistent") or user.__dict__.get("nonexistent") is None

	def test_merge_strict_raises_on_unknown(self, user: User):
		with pytest.raises(AttributeError):
			user.merge(strict=True, nonexistent="value")

	def test_merge_strict_raises_on_pk(self, user: User):
		with pytest.raises(AttributeError):
			user.merge(strict=True, id=999)

	def test_merge_partial_update(self, user: User):
		user.merge(bio="new bio")
		assert user.bio == "new bio"
		assert user.name == "John"  # unchanged

	def test_merge_none_value(self, user: User):
		user.merge(bio=None)
		assert user.bio is None

	def test_merge_persists_with_commit(self, db: Database):
		with db.session as session:
			u = User(id=20, name="Before", email="before@test.com")
			session.add(u)
			session.commit()

			u.merge(name="After")
			session.commit()

			refreshed = session.get(User, 20)
			assert refreshed.name == "After"

	def test_merge_multiple_changes_at_once(self, user: User):
		user.merge(name="New", email="new@test.com", bio="new bio")
		assert user.name == "New"
		assert user.email == "new@test.com"
		assert user.bio == "new bio"

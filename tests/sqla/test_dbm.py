from sqlalchemy import Column, Integer, String

from sotkalib.sqla import BasicDBM, Database
from sotkalib.sqla.db import DatabaseSettings


class User(BasicDBM):
	__tablename__ = "users"

	id = Column(Integer, primary_key=True)
	name = Column(String(50))
	email = Column(String(100))


class TestBasicDBM:
	def test_dict_returns_all_columns(self):
		db = Database(DatabaseSettings(uri="sqlite:///:memory:", async_driver=None))
		db.create()

		with db.session() as session:
			user = User(id=1, name="John", email="john@test.com")
			session.add(user)
			session.commit()
			session.refresh(user)

			result = user.dict()
			assert result == {"id": 1, "name": "John", "email": "john@test.com"}

		db.close()

	def test_dict_with_extra_kwargs(self):
		db = Database(DatabaseSettings(uri="sqlite:///:memory:", async_driver=None))
		db.create()

		with db.session() as session:
			user = User(id=1, name="John", email="john@test.com")
			session.add(user)
			session.commit()
			session.refresh(user)

			result = user.dict(extra="value")
			assert result["extra"] == "value"
			assert result["name"] == "John"

		db.close()

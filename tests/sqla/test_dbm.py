from sqlalchemy import Column, Integer, String, create_engine
from sqlalchemy.orm import Session

from sotkalib.sqla.dbm import BasicDBM


class User(BasicDBM):
	__tablename__ = "users"

	id = Column(Integer, primary_key=True)
	name = Column(String(50))
	email = Column(String(100))


class TestBasicDBM:
	def test_dict_returns_all_columns(self):
		engine = create_engine("sqlite:///:memory:")
		BasicDBM.metadata.create_all(engine)

		with Session(engine) as session:
			user = User(id=1, name="John", email="john@test.com")
			session.add(user)
			session.commit()
			session.refresh(user)

			result = user.dict()
			assert result == {"id": 1, "name": "John", "email": "john@test.com"}

	def test_dict_with_extra_kwargs(self):
		engine = create_engine("sqlite:///:memory:")
		BasicDBM.metadata.create_all(engine)

		with Session(engine) as session:
			user = User(id=1, name="John", email="john@test.com")
			session.add(user)
			session.commit()
			session.refresh(user)

			result = user.dict(extra="value")
			assert result["extra"] == "value"
			assert result["name"] == "John"

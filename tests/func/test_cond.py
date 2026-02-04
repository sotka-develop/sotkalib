import pytest

from sotkalib.func.cond import or_raise, suppress, type_or_raise


class TestSuppress:
	def test_suppresses_all_exceptions(self):
		with suppress():
			raise ValueError("error")

	def test_mode_exact_suppresses_matching(self):
		with suppress(mode="exact", excts=[ValueError]):
			raise ValueError("error")

	def test_mode_exact_does_not_suppress_non_matching(self):
		with pytest.raises(TypeError):
			with suppress(mode="exact", excts=[ValueError]):
				raise TypeError("error")

	def test_mode_exact_warns_when_no_excts(self):
		with pytest.warns(UserWarning, match="exact"):
			with suppress(mode="exact", excts=None):
				pass

	def test_mode_all_suppresses_any_exception(self):
		with suppress(mode="all"):
			raise RuntimeError("any error")


class TestOrRaise:
	def test_returns_value_if_not_none(self):
		assert or_raise(42) == 42
		assert or_raise("hello") == "hello"

	def test_raises_if_none(self):
		with pytest.raises(ValueError, match="v is None"):
			or_raise(None)

	def test_raises_with_custom_message(self):
		with pytest.raises(ValueError, match="custom msg"):
			or_raise(None, msg="custom msg")


class TestTypeOrRaise:
	def test_returns_value_if_correct_type(self):
		assert type_or_raise("hello", str) == "hello"
		assert type_or_raise(42, int) == 42

	def test_raises_if_wrong_type(self):
		with pytest.raises(TypeError, match="want.*str.*got.*int"):
			type_or_raise(42, str)

	def test_raises_with_custom_message(self):
		with pytest.raises(TypeError, match="must be string"):
			type_or_raise(42, str, msg="must be string")

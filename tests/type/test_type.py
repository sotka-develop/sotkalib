from sotkalib.type import Unset, unset


class TestUnset:
	def test_repr(self):
		assert repr(Unset) == "Unset"

	def test_bool_is_false(self):
		assert bool(Unset) is False

	def test_identity(self):
		assert Unset is Unset


class TestUnsetFunc:
	def test_unset_returns_true_for_unset(self):
		assert unset(Unset) is True

	def test_unset_returns_false_for_none(self):
		assert unset(None) is False

	def test_unset_returns_false_for_value(self):
		assert unset("value") is False
		assert unset(0) is False
		assert unset([]) is False

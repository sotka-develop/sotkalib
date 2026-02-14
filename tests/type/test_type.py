from sotkalib.type import Unset, is_set


class TestUnset:
	def test_repr(self):
		assert repr(Unset) == "<unset value>"

	def test_bool_is_false(self):
		assert bool(Unset) is False

	def test_identity(self):
		assert Unset is Unset


class TestUnsetFunc:
	def test_unset_returns_false_for_is_set(self):
		assert is_set(Unset) is False

	def test_unset_returns_true_for_none(self):
		assert is_set(None) is True

	def test_unset_returns_true_for_value(self):
		assert is_set("value") is True
		assert is_set(0) is True
		assert is_set([]) is True

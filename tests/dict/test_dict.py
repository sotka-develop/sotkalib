from sotkalib.dict import without_unset
from sotkalib.type import Unset


class TestWithoutUnset:
	def test_removes_unset_values(self):
		d = {"a": 1, "b": Unset, "c": 3}
		result = without_unset(d)
		assert result == {"a": 1, "c": 3}

	def test_preserves_none(self):
		d = {"a": None, "b": Unset}
		result = without_unset(d)
		assert result == {"a": None}

	def test_empty_dict(self):
		assert without_unset({}) == {}

	def test_all_unset(self):
		d = {"a": Unset, "b": Unset}
		assert without_unset(d) == {}

	def test_no_unset(self):
		d = {"a": 1, "b": 2}
		result = without_unset(d)
		assert result == {"a": 1, "b": 2}

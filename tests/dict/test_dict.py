from sotkalib.dict.util import valid
from sotkalib.type import Unset


class TestWithoutUnset:
	def test_removes_unset_values(self):
		assert (valid({"a": 1, "b": Unset, "c": 3})) == {"a": 1, "c": 3}

	def test_preserves_none(self):
		assert valid({"a": None, "b": Unset}) == {"a": None}

	def test_empty_dict(self):
		assert valid({}) == {}

	def test_all_unset(self):
		assert valid({"a": Unset, "b": Unset}) == {}

	def test_no_unset(self):
		assert valid({"a": 1, "b": 2}) == {"a": 1, "b": 2}

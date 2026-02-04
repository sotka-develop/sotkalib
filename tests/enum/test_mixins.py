from enum import auto

import pytest

from sotkalib.enum.mixins import UppercaseMixin, ValidatorMixin, ValuesMixin


class Color(UppercaseMixin):
	red = auto()
	green = auto()
	blue = auto()


class Fruit(ValidatorMixin):
	apple = "apple"
	banana = "banana"
	cherry = "cherry"


class TestUppercaseMixin:
	def test_values_are_uppercased(self):
		assert Color.red == "RED"
		assert Color.green == "GREEN"
		assert Color.blue == "BLUE"

	def test_is_str(self):
		assert isinstance(Color.red, str)


class TestValidatorMixin:
	def test_validate_valid(self):
		assert Fruit.validate(val="apple") is Fruit.apple

	def test_validate_none_not_required(self):
		assert Fruit.validate(val=None) is None

	def test_validate_none_required(self):
		with pytest.raises(ValueError, match="req=True"):
			Fruit.validate(val=None, req=True)

	def test_validate_invalid_value(self):
		with pytest.raises(TypeError, match="not valid"):
			Fruit.validate(val="mango", req=True)

	def test_validate_bytes(self):
		assert Fruit.validate(val=b"apple") is Fruit.apple

	def test_validate_bytearray(self):
		assert Fruit.validate(val=bytearray(b"banana")) is Fruit.banana

	def test_validate_non_str_type(self):
		with pytest.raises(TypeError, match="must be str-like"):
			Fruit.validate(val=123)

	def test_get_valid(self):
		assert Fruit.get("apple") is Fruit.apple

	def test_get_invalid_returns_default(self):
		assert Fruit.get("mango") is None

	def test_get_invalid_with_default(self):
		assert Fruit.get("mango", Fruit.cherry) is Fruit.cherry

	def test_get_none(self):
		assert Fruit.get(None) is None

	def test_in_(self):
		assert Fruit.apple.in_(Fruit.apple, Fruit.banana) is True
		assert Fruit.cherry.in_(Fruit.apple, Fruit.banana) is False

	def test_values(self):
		assert list(Fruit.values()) == [Fruit.apple, Fruit.banana, Fruit.cherry]


class Constants(ValuesMixin):
	FOO = "foo"
	BAR = "bar"
	BAZ = "baz"


class TestValuesMixin:
	def test_values_list(self):
		assert Constants.values_list() == ["foo", "bar", "baz"]

	def test_values_set(self):
		assert Constants.values_set() == {"foo", "bar", "baz"}

	def test_names_list(self):
		assert Constants.names_list() == ["FOO", "BAR", "BAZ"]

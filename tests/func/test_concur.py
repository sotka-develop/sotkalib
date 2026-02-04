import pytest

from sotkalib.func.concur import asyncfn, asyncfn_or_raise


def sync_func():
	pass


async def async_func():
	pass


class TestAsyncfn:
	def test_returns_true_for_async(self):
		assert asyncfn(async_func) is True

	def test_returns_false_for_sync(self):
		assert asyncfn(sync_func) is False

	def test_returns_false_for_lambda(self):
		assert asyncfn(lambda: None) is False


class TestAsyncfnOrRaise:
	def test_raises_for_sync(self):
		with pytest.raises(TypeError, match="is not an async function"):
			asyncfn_or_raise(sync_func)

	def test_does_not_raise_for_async(self):
		asyncfn_or_raise(async_func)

import pytest

from sotkalib.exceptions.handlers.args_incl_error import ArgsIncludedError
from sotkalib.exceptions.handlers.core import aexception_handler, exception_handler


class TestArgsIncludedError:
	def test_basic(self):
		err = ArgsIncludedError("msg", stack_depth=0)
		assert err.args[0] == "msg"

	def test_is_exception(self):
		assert issubclass(ArgsIncludedError, Exception)


class TestExceptionHandler:
	def test_wraps_exception(self):
		@exception_handler
		def failing():
			raise ValueError("boom")

		with pytest.raises(ArgsIncludedError) as exc_info:
			failing()

		assert "boom" in str(exc_info.value.args[0])

	def test_passes_through_on_success(self):
		@exception_handler
		def ok():
			return 42

		assert ok() == 42

	def test_preserves_function_name(self):
		@exception_handler
		def my_func():
			pass

		assert my_func.__name__ == "my_func"


class TestAExceptionHandler:
	@pytest.mark.asyncio
	async def test_wraps_async_exception(self):
		@aexception_handler
		async def failing():
			raise ValueError("async boom")

		with pytest.raises(ArgsIncludedError) as exc_info:
			await failing()

		assert "async boom" in str(exc_info.value.args[0])

	@pytest.mark.asyncio
	async def test_passes_through_on_success(self):
		@aexception_handler
		async def ok():
			return 99

		assert await ok() == 99

	@pytest.mark.asyncio
	async def test_preserves_function_name(self):
		@aexception_handler
		async def my_async_func():
			pass

		assert my_async_func.__name__ == "my_async_func"

from collections.abc import Callable, Coroutine
from functools import wraps
from typing import Any

from sotkalib.log import get_logger

from .args_incl_error import ArgsIncludedError


def exception_handler[**P, R](
	func: Callable[P, R],
	stack_depth: int = 3,
) -> Callable[P, R]:
	@wraps(func)
	def wrapper(*args: P.args, **kwargs: P.kwargs) -> R:
		try:
			return func(*args, **kwargs)
		except Exception as e:
			get_logger().exception("")
			raise ArgsIncludedError(*e.args, stack_depth=stack_depth) from e

	return wrapper


def aexception_handler[**P, R](
	func: Callable[P, Coroutine[Any, Any, R]],
	stack_depth: int = 7,
) -> Callable[P, Coroutine[Any, Any, R]]:
	@wraps(func)
	async def wrapper(*args: P.args, **kwargs: P.kwargs) -> R:
		try:
			return await func(*args, **kwargs)
		except Exception as e:
			get_logger().exception("")
			raise ArgsIncludedError(*e.args, stack_depth=stack_depth) from e

	return wrapper

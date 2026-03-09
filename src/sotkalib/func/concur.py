import inspect
from collections.abc import Callable
from typing import Any, TypeIs

from sotkalib.type.generics import any_function, async_function


def asyncfn[**P, R](fn: any_function[P, R]) -> TypeIs[async_function[P, R]]:
	return inspect.iscoroutinefunction(fn)


def asyncfn_or_raise(fn: Callable[..., Any]) -> None:
	if not inspect.iscoroutinefunction(fn):
		raise TypeError(f"{fn} is not an async function")

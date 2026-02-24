import inspect
from collections.abc import Callable, Coroutine
from typing import Any, TypeIs


def asyncfn(fn: Callable[..., Any]) -> TypeIs[Callable[..., Coroutine[Any, Any, Any]]]:
	return inspect.iscoroutinefunction(fn)


def asyncfn_or_raise(fn: Callable[..., Any]) -> None:
	if not inspect.iscoroutinefunction(fn):
		raise TypeError(f"{fn} is not an async function")

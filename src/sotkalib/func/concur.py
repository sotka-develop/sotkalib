import inspect
from collections.abc import Callable
from typing import Any


def asyncfn(fn: Callable[..., Any]) -> bool:
	return inspect.iscoroutinefunction(fn)


def asyncfn_or_raise(fn: Callable[..., Any]) -> None:
	if not inspect.iscoroutinefunction(fn):
		raise TypeError(f"{fn} is not an async function")

from collections.abc import Mapping, Sequence
from typing import Any

from sotkalib.type.generics import any_function

from ..type.generics import async_function
from .context import RequestContext

type Next[T] = async_function[[RequestContext], T]
type Middleware[T, R] = async_function[[RequestContext, Next[T]], R]
type ArgumentFunc = any_function[[RequestContext], ArgsKwargs]
type ArgsKwargs = tuple[Sequence[Any], Mapping[str, Any]]


class RanOutOfAttemptsError(Exception):
	pass


class CriticalStatusError(Exception):
	pass


class StatusRetryError(Exception):
	status: int
	context: str

	def __init__(self, status: int, context: str) -> None:
		super().__init__(f"{status}: {context}")
		self.status = status
		self.context = context

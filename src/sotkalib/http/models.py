import time
from collections.abc import Callable, Coroutine, Mapping, Sequence
from copy import deepcopy
from dataclasses import dataclass, field
from http import HTTPStatus
from typing import Any, Literal, Self
from warnings import warn

import aiohttp
from aiohttp import client_exceptions
from pydantic import BaseModel, ConfigDict, Field

type Next[T] = Callable[[RequestContext], Coroutine[None, None, T]]
type Middleware[T, R] = Callable[[RequestContext, Next[T]], Coroutine[None, None, R]]
type ArgumentFunc = Callable[[RequestContext], tuple[Sequence[Any], Mapping[str, Any] | None]]


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


@dataclass
class RequestContext:
	method: str
	url: str
	params: dict[str, Any] | None = None
	headers: dict[str, Any] | None = None
	data: Any = None
	json: Any = None
	kwargs: dict[str, Any] = field(default_factory=dict)

	attempt: int = 0
	max_attempts: int = 1

	response: aiohttp.ClientResponse | None = None
	response_body: Any = None
	response_text: str | None = None
	response_json: Any = None

	started_at: float | None = None
	finished_at: float | None = None
	attempt_started_at: float | None = None

	errors: list[Exception] = field(default_factory=list)
	last_error: Exception | None = None

	state: dict[str, Any] = field(default_factory=dict)

	@property
	def elapsed(self) -> float | None:
		if self.started_at is None:
			return None
		end = self.finished_at if self.finished_at else time.monotonic()
		return end - self.started_at

	@property
	def attempt_elapsed(self) -> float | None:
		if self.attempt_started_at is None:
			return None
		return time.monotonic() - self.attempt_started_at

	@property
	def is_retry(self) -> bool:
		return self.attempt > 0

	@property
	def status(self) -> int | None:
		return self.response.status if self.response else None

	def merge_headers(self, headers: dict[str, str]) -> None:
		if self.headers is None:
			self.headers = {}
		self.headers.update(headers)

	def to_request_kwargs(self) -> dict[str, Any]:
		kw = dict(self.kwargs)
		if self.params is not None:
			kw["params"] = self.params
		if self.headers is not None:
			kw["headers"] = self.headers
		if self.data is not None:
			kw["data"] = self.data
		if self.json is not None:
			kw["json"] = self.json
		return kw


async def default_stat_arg_func(ctx: RequestContext) -> tuple[Sequence[Any], None]:
	resp = ctx.response
	if resp is None:
		return (), None
	return (f"[{resp.status}]; {await resp.text()=}",), None


def default_exc_arg_func(ctx: RequestContext) -> tuple[Sequence[Any], None]:
	return (
		f"exception {type(ctx.last_error)}: ({ctx.last_error=}) attempt={ctx.attempt}; url={ctx.url} method={ctx.method}"
	), None


class _MergeableSettings(BaseModel):
	def _merge_from(self, other: "_MergeableSettings") -> Self:
		merged = self.model_copy(deep=True)
		for field_name in other.model_fields_set:
			value = getattr(other, field_name)
			base_value = getattr(merged, field_name)
			if isinstance(base_value, _MergeableSettings) and isinstance(value, _MergeableSettings):
				value = base_value._merge_from(value)
			object.__setattr__(merged, field_name, value)
		return merged

	def __or__(self, other: "_MergeableSettings") -> Self:
		if isinstance(other, type(self)):
			return self._merge_from(other)
		return NotImplemented


class StatusSettings(_MergeableSettings):
	model_config = ConfigDict(arbitrary_types_allowed=True)

	to_raise: set[HTTPStatus] = Field(default={HTTPStatus.FORBIDDEN})
	to_retry: set[HTTPStatus] = Field(default={HTTPStatus.TOO_MANY_REQUESTS, HTTPStatus.FORBIDDEN})
	exc_to_raise: type[Exception] = Field(default=CriticalStatusError)
	not_found_as_none: bool = Field(default=True)
	args_for_exc_func: ArgumentFunc = Field(default=default_stat_arg_func)
	unspecified: Literal["retry", "raise"] = Field(default="retry")


class ExceptionSettings(_MergeableSettings):
	model_config = ConfigDict(arbitrary_types_allowed=True)

	to_raise: tuple[type[Exception], ...] = Field(
		default=(
			client_exceptions.ConnectionTimeoutError,
			client_exceptions.ClientProxyConnectionError,
			client_exceptions.ContentTypeError,
		),
	)

	to_retry: tuple[type[Exception], ...] = Field(
		default=(
			TimeoutError,
			client_exceptions.ServerDisconnectedError,
			client_exceptions.ClientConnectionResetError,
			client_exceptions.ClientOSError,
			client_exceptions.ClientHttpProxyError,
		),
	)

	exc_to_raise: type[Exception] | None = Field(default=None)
	args_for_exc_func: ArgumentFunc = Field(default=default_exc_arg_func)
	unspecified: Literal["retry", "raise"] = Field(default="retry")


class ClientSettings(_MergeableSettings):
	timeout: float = Field(default=5.0, gt=0)
	base: float = Field(default=1.0, gt=0)
	backoff: float = Field(default=2.0, gt=0)
	maximum_retries: int = Field(default=3, ge=1)

	useragent_factory: Callable[[], str] | None = Field(default=None)

	status_settings: StatusSettings = Field(default_factory=StatusSettings)
	exception_settings: ExceptionSettings = Field(default_factory=ExceptionSettings)

	session_kwargs: dict[str, Any] = Field(default_factory=dict)
	use_cookies_from_response: bool = Field(default=False)

	_nested_map: dict[type, str] = {
		StatusSettings: "status_settings",
		ExceptionSettings: "exception_settings",
	}

	def __or__(self, other: _MergeableSettings) -> Self:
		if isinstance(other, ClientSettings):
			return self._merge_from(other)

		field_name = self._nested_map.get(type(other))
		if field_name is not None:
			merged = self.model_copy(deep=True)
			setattr(merged, field_name, getattr(merged, field_name)._merge_from(other))
			return merged

		return NotImplemented

	def with_(self, **kws) -> Self:
		warn(
			"ClientSettings.with_() is deprecated, use the | operator instead",
			DeprecationWarning,
			stacklevel=2,
		)
		ns = deepcopy(self)
		for k, v in kws.items():
			if "." in k:
				pk, ck = k.split(".")
				setattr(getattr(ns, pk), ck, v)
			else:
				setattr(ns, k, v)
		return ns

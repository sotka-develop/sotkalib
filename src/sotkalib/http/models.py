from collections.abc import Callable
from copy import deepcopy
from http import HTTPStatus
from typing import Any, Literal, Self
from warnings import deprecated

from aiohttp import client_exceptions
from pydantic import BaseModel, ConfigDict, Field

from .context import RequestContext
from .types import ArgsKwargs, ArgumentFunc, CriticalStatusError


async def default_stat_arg_func(ctx: RequestContext) -> ArgsKwargs:
	resp = ctx.response
	if resp is None:
		return (), {}
	return (f"[{resp.status}]; {await resp.text()=}",), {}


async def default_exc_arg_func(ctx: RequestContext) -> ArgsKwargs:
	return (
		f"exception {type(ctx.last_error)}: ({ctx.last_error=}) attempt={ctx.attempt}; url={ctx.url}"
		f" method={ctx.method}"
	), {}


class _MergeableSettings(BaseModel):
	def _merge_from(self, other: "_MergeableSettings") -> Self:
		merged = self.model_copy(deep=True)
		for field_name in other.model_fields_set:
			value = getattr(other, field_name)
			base_value = getattr(merged, field_name)
			if isinstance(base_value, _MergeableSettings) and isinstance(
				value, _MergeableSettings
			):
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
	to_retry: set[HTTPStatus] = Field(
		default={HTTPStatus.TOO_MANY_REQUESTS, HTTPStatus.FORBIDDEN}
	)
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
	exception_settings: ExceptionSettings = Field(
		default_factory=ExceptionSettings
	)

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
			setattr(
				merged,
				field_name,
				getattr(merged, field_name)._merge_from(other),
			)
			return merged

		return NotImplemented

	@deprecated(
		"ClientSettings.with_() is deprecated, use the | operator instead"
	)
	def with_(self, **kws) -> Self:
		ns = deepcopy(self)
		for k, v in kws.items():
			if "." in k:
				pk, ck = k.split(".")
				setattr(getattr(ns, pk), ck, v)
			else:
				setattr(ns, k, v)
		return ns

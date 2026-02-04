import asyncio
import ssl
import time
from collections.abc import Awaitable, Callable, Mapping, Sequence
from dataclasses import dataclass, field
from http import HTTPStatus
from typing import Any, Literal, Self

import aiohttp
from aiohttp import client_exceptions
from pydantic import BaseModel, ConfigDict, Field

from sotkalib.log import get_logger

MAXIMUM_BACKOFF: float = 120

try:
	import certifi
except ImportError:
	certifi = None


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


type Next[T] = Callable[[RequestContext], Awaitable[T]]
type Middleware[T, R] = Callable[[RequestContext, Next[T]], Awaitable[R]]

type ExcArgFunc = Callable[..., tuple[Sequence[Any], Mapping[str, Any] | None]]
type StatArgFunc = Callable[..., Any]


async def default_stat_arg_func(resp: aiohttp.ClientResponse) -> tuple[Sequence[Any], None]:
	return (f"[{resp.status}]; {await resp.text()=}",), None


def default_exc_arg_func(exc: Exception, attempt: int, url: str, method: str, **kw) -> tuple[Sequence[Any], None]:
	return (f"exception {type(exc)}: ({exc=}) {attempt=}; {url=} {method=} {kw=}",), None


class StatusSettings(BaseModel):
	model_config = ConfigDict(arbitrary_types_allowed=True)

	to_raise: set[HTTPStatus] = Field(default={HTTPStatus.FORBIDDEN})
	to_retry: set[HTTPStatus] = Field(default={HTTPStatus.TOO_MANY_REQUESTS, HTTPStatus.FORBIDDEN})
	exc_to_raise: type[Exception] = Field(default=CriticalStatusError)
	not_found_as_none: bool = Field(default=True)
	args_for_exc_func: StatArgFunc = Field(default=default_stat_arg_func)
	unspecified: Literal["retry", "raise"] = Field(default="retry")


class ExceptionSettings(BaseModel):
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
	args_for_exc_func: ExcArgFunc = Field(default=default_exc_arg_func)
	unspecified: Literal["retry", "raise"] = Field(default="retry")


class ClientSettings(BaseModel):
	timeout: float = Field(default=5.0, gt=0)
	base: float = Field(default=1.0, gt=0)
	backoff: float = Field(default=2.0, gt=0)
	maximum_retries: int = Field(default=3, ge=1)

	useragent_factory: Callable[[], str] | None = Field(default=None)

	status_settings: StatusSettings = Field(default_factory=StatusSettings)
	exception_settings: ExceptionSettings = Field(default_factory=ExceptionSettings)

	session_kwargs: dict[str, Any] = Field(default_factory=dict)
	use_cookies_from_response: bool = Field(default=False)


# ============================================================================
# SSL Context
# ============================================================================


def _make_ssl_context(disable_tls13: bool = False) -> ssl.SSLContext:
	ctx = ssl.SSLContext(ssl.PROTOCOL_TLS_CLIENT)
	ctx.load_default_certs()

	if certifi:
		ctx.load_verify_locations(certifi.where())

	ctx.minimum_version = ssl.TLSVersion.TLSv1_2
	ctx.maximum_version = ssl.TLSVersion.TLSv1_2 if disable_tls13 else ssl.TLSVersion.TLSv1_3

	ctx.set_ciphers(
		"TLS_AES_256_GCM_SHA384:TLS_AES_128_GCM_SHA256:"
		"TLS_CHACHA20_POLY1305_SHA256:"
		"ECDHE-ECDSA-AES256-GCM-SHA384:ECDHE-RSA-AES256-GCM-SHA384:"
		"ECDHE-ECDSA-AES128-GCM-SHA256:ECDHE-RSA-AES128-GCM-SHA256"
	)

	ctx.check_hostname = True
	ctx.verify_mode = ssl.CERT_REQUIRED

	return ctx


# ============================================================================
# HTTP Session
# ============================================================================


class HTTPSession[R = aiohttp.ClientResponse | None]:
	config: ClientSettings
	_session: aiohttp.ClientSession | None
	_middlewares: list[Middleware[Any, Any]]
	_logger: Any

	def __init__(
		self,
		config: ClientSettings | None = None,
		_middlewares: list[Middleware[Any, Any]] | None = None,
	) -> None:
		self.config = config if config is not None else ClientSettings()
		self._session = None
		self._middlewares = _middlewares or []
		self._logger = get_logger("http.client_session")

	def use[NewR](self, middleware: Middleware[R, NewR]) -> HTTPSession[NewR]:
		return HTTPSession[NewR](
			config=self.config,
			_middlewares=[*self._middlewares, middleware],
		)

	async def __aenter__(self) -> Self:
		ctx = _make_ssl_context(disable_tls13=False)

		session_kwargs = dict(self.config.session_kwargs)
		if session_kwargs.get("connector") is None:
			session_kwargs["connector"] = aiohttp.TCPConnector(ssl=ctx)
		if session_kwargs.get("trust_env") is None:
			session_kwargs["trust_env"] = False

		self._session = aiohttp.ClientSession(
			timeout=aiohttp.ClientTimeout(total=self.config.timeout),
			**session_kwargs,
		)

		self._logger.debug(f"HTTPSession initialized with timeout: {self.config.timeout}")
		return self

	async def __aexit__(
		self,
		exc_type: type[BaseException] | None,
		exc_val: BaseException | None,
		exc_tb: Any,
	) -> None:
		if self._session:
			await self._session.close()

	def _build_pipeline(self) -> Next[R]:
		"""Build the middleware pipeline with the core request at the end."""

		async def core_request(ctx: RequestContext) -> aiohttp.ClientResponse | None:
			"""The innermost handler that actually makes the HTTP request."""
			return await self._execute_request(ctx)

		pipeline: Next[Any] = core_request
		for middleware in reversed(self._middlewares):
			pipeline = (lambda mw, nxt: lambda c: mw(c, nxt))(middleware, pipeline)

		return pipeline

	async def _execute_request(self, ctx: RequestContext) -> aiohttp.ClientResponse | None:
		"""Execute the actual HTTP request and handle status codes."""
		if self._session is None:
			raise RuntimeError("HTTPSession must be used as async context manager")

		response = await self._session.request(ctx.method, ctx.url, **ctx.to_request_kwargs())
		ctx.response = response

		return await self._handle_status(ctx, response)

	async def _handle_status(
		self,
		ctx: RequestContext,
		response: aiohttp.ClientResponse,
	) -> aiohttp.ClientResponse | None:
		"""Handle HTTP status codes according to settings."""
		status = response.status
		settings = self.config.status_settings

		if self.config.use_cookies_from_response and self._session:
			self._session.cookie_jar.update_cookies(response.cookies)

		if HTTPStatus(status) in settings.to_retry:
			text = await response.text()
			ctx.response_text = text
			raise StatusRetryError(status=status, context=text)

		if HTTPStatus(status) in settings.to_raise:
			exc_cls = settings.exc_to_raise
			args, kwargs = await settings.args_for_exc_func(response)
			if kwargs is None:
				raise exc_cls(*args)
			raise exc_cls(*args, **kwargs)

		if settings.not_found_as_none and status == HTTPStatus.NOT_FOUND:
			return None

		return response


	async def _request_with_retry(self, ctx: RequestContext) -> R:
		"""Execute request with retry logic."""
		ctx.started_at = time.monotonic()
		ctx.max_attempts = self.config.maximum_retries + 1

		pipeline = self._build_pipeline()

		for attempt in range(ctx.max_attempts):
			ctx.attempt = attempt
			ctx.attempt_started_at = time.monotonic()
			ctx.response = None

			try:
				result = await pipeline(ctx)
				ctx.finished_at = time.monotonic()
				return result

			except merge_tuples(self.config.exception_settings.to_retry, (StatusRetryError,)) as e:
				ctx.errors.append(e)
				ctx.last_error = e
				await self._handle_retry(ctx, e)

			except self.config.exception_settings.to_raise as e:
				ctx.errors.append(e)
				ctx.last_error = e
				ctx.finished_at = time.monotonic()
				await self._handle_to_raise(ctx, e)

			except Exception as e:
				ctx.errors.append(e)
				ctx.last_error = e
				await self._handle_exception(ctx, e)

		ctx.finished_at = time.monotonic()
		raise RanOutOfAttemptsError(
			f"failed after {self.config.maximum_retries} retries: {type(ctx.last_error).__name__}: {ctx.last_error}"
		)

	async def _handle_retry(self, ctx: RequestContext, e: Exception) -> None:
		if ctx.attempt >= self.config.maximum_retries:
			raise RanOutOfAttemptsError(
				f"failed after {self.config.maximum_retries} retries: {type(e).__name__}: {e}"
			) from e

		delay = self.config.base * min(MAXIMUM_BACKOFF, self.config.backoff**ctx.attempt)
		self._logger.debug(
			f"Retry {ctx.attempt + 1}/{ctx.max_attempts} for {ctx.method} {ctx.url} "
			f"after {delay:.2f}s (error: {type(e).__name__})"
		)
		await asyncio.sleep(delay)

	async def _handle_to_raise(self, ctx: RequestContext, e: Exception) -> None:
		"""Handle exceptions that should be re-raised (possibly wrapped)."""
		exc_cls = self.config.exception_settings.exc_to_raise
		if exc_cls is None:
			raise e

		args, kwargs = self.config.exception_settings.args_for_exc_func(
			e, ctx.attempt, ctx.url, ctx.method, **ctx.to_request_kwargs()
		)
		if kwargs is None:
			raise exc_cls(*args) from e
		raise exc_cls(*args, **kwargs) from e

	async def _handle_exception(self, ctx: RequestContext, e: Exception) -> None:
		"""Handle unspecified exceptions according to settings."""
		if self.config.exception_settings.unspecified == "raise":
			raise e
		await self._handle_retry(ctx, e)

	def _create_context(
		self,
		method: str,
		url: str,
		params: dict[str, Any] | None = None,
		headers: dict[str, Any] | None = None,
		data: Any = None,
		json: Any = None,
		**kwargs: Any,
	) -> RequestContext:
		"""Create a RequestContext for the given request parameters."""
		# Apply user agent if configured
		if self.config.useragent_factory is not None:
			if headers is None:
				headers = {}
			headers["User-Agent"] = self.config.useragent_factory()

		return RequestContext(
			method=method,
			url=url,
			params=params,
			headers=headers,
			data=data,
			json=json,
			kwargs=kwargs,
		)

	async def request(
		self,
		method: str,
		url: str,
		*,
		params: dict[str, Any] | None = None,
		headers: dict[str, Any] | None = None,
		data: Any = None,
		json: Any = None,
		**kwargs: Any,
	) -> R:
		ctx = self._create_context(method, url, params, headers, data, json, **kwargs)
		return await self._request_with_retry(ctx)

	async def get(self, url: str, **kwargs: Any) -> R:
		"""Make a GET request."""
		return await self.request("GET", url, **kwargs)

	async def post(self, url: str, **kwargs: Any) -> R:
		"""Make a POST request."""
		return await self.request("POST", url, **kwargs)

	async def put(self, url: str, **kwargs: Any) -> R:
		"""Make a PUT request."""
		return await self.request("PUT", url, **kwargs)

	async def delete(self, url: str, **kwargs: Any) -> R:
		"""Make a DELETE request."""
		return await self.request("DELETE", url, **kwargs)

	async def patch(self, url: str, **kwargs: Any) -> R:
		"""Make a PATCH request."""
		return await self.request("PATCH", url, **kwargs)


def merge_tuples[T](t1: tuple[T, ...], t2: tuple[T, ...]) -> tuple[T, ...]:
	return t1 + t2
# ============================================================================
# Legacy compatibility aliases
# ============================================================================

# Old Handler protocol - kept for backwards compatibility but deprecated
from typing import Protocol


class Handler[**P, T](Protocol):
	"""
	DEPRECATED: Use Middleware type instead.

	Old handler protocol for backwards compatibility.
	"""

	async def __call__(self, *args: P.args, **kwargs: P.kwargs) -> T: ...

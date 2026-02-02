import asyncio
import ssl
from collections.abc import Callable, Mapping, Sequence
from functools import reduce
from http import HTTPStatus
from typing import Any, Literal, Protocol, Self

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

type ExcArgFunc = Callable[..., tuple[Sequence[Any], Mapping[str, Any] | None]]
type StatArgFunc = Callable[..., Any]

async def default_stat_arg_func(resp: aiohttp.ClientResponse) -> tuple[Sequence[Any], None]:
	return (f"[{resp.status}]; {await resp.text()=}",), None

class StatusSettings(BaseModel):
	model_config = ConfigDict(arbitrary_types_allowed=True)

	to_raise: set[HTTPStatus] = Field(default={HTTPStatus.FORBIDDEN})
	to_retry: set[HTTPStatus] = Field(default={HTTPStatus.TOO_MANY_REQUESTS, HTTPStatus.FORBIDDEN})
	exc_to_raise: type[Exception] = Field(default=CriticalStatusError)
	not_found_as_none: bool = Field(default=True)
	args_for_exc_func: StatArgFunc = Field(default=default_stat_arg_func)
	unspecified: Literal["retry", "raise"] = Field(default="retry")

def default_exc_arg_func(exc: Exception, attempt: int, url: str, method: str, **kw) -> tuple[Sequence[Any], None]:
	return (f"exception {type(exc)}: ({exc=}) {attempt=}; {url=} {method=} {kw=}",), None

class ExceptionSettings(BaseModel):
	model_config = ConfigDict(arbitrary_types_allowed=True)

	to_raise: tuple[type[Exception]] = Field(
		default=(
			client_exceptions.ConnectionTimeoutError,
			client_exceptions.ClientProxyConnectionError,
			client_exceptions.ContentTypeError,
		),
	)

	to_retry: tuple[type[Exception]] = Field(
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


class Handler[**P, T](Protocol):
	async def __call__(self, *args: P.args, **kwargs: P.kwargs) -> T: ...


type Middleware[**P, T, R] = Callable[[Handler[P, T]], Handler[P, R]]


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



class HTTPSession[R = aiohttp.ClientResponse | None]:
	config: ClientSettings
	_session: aiohttp.ClientSession
	_middlewares: list[Middleware]

	def __init__(
		self,
		config: ClientSettings | None = None,
		_middlewares: list[Middleware] | None = None,
	) -> None:
		self.config = config if config is not None else ClientSettings()
		self._session = None
		self._middlewares = _middlewares or []

	def use[**P, NewR](self, mw: Middleware[P, R, NewR]) -> HTTPSession[NewR]:
		new_session: HTTPSession[NewR] = HTTPSession(
			config=self.config,
			_middlewares=[*self._middlewares, mw],
		)
		return new_session

	async def __aenter__(self) -> Self:
		ctx = _make_ssl_context(disable_tls13=False)

		if self.config.session_kwargs.get("connector") is None:
			self.config.session_kwargs["connector"] = aiohttp.TCPConnector(ssl=ctx)
		if self.config.session_kwargs.get("trust_env") is None:
			self.config.session_kwargs["trust_env"] = False

		self._session = aiohttp.ClientSession(
			timeout=aiohttp.ClientTimeout(total=self.config.timeout),
			**self.config.session_kwargs,
		)

		get_logger("http.client_session").debug(
			f"RetryableClientSession initialized with timeout: {self.config.timeout}"
		)

		return self

	async def __aexit__(self, exc_type: type[BaseException] | None, exc_val: BaseException | None, exc_tb: Any) -> None:
		if self._session:
			await self._session.close()

	async def _handle_statuses(self, response: aiohttp.ClientResponse) -> aiohttp.ClientResponse | None:
		sc = response.status
		exc, argfunc = self.config.status_settings.exc_to_raise, self.config.status_settings.args_for_exc_func
		if self.config.use_cookies_from_response:
			self._session.cookie_jar.update_cookies(response.cookies)
		if sc in self.config.status_settings.to_retry:
			raise StatusRetryError(status=sc, context=(await response.text()))
		elif sc in self.config.status_settings.to_raise:
			a, kw = await argfunc(response)
			if kw is None:
				raise exc(*a)
			raise exc(*a, **kw)
		elif self.config.status_settings.not_found_as_none and sc == HTTPStatus.NOT_FOUND:
			return None

		return response

	def _get_make_request_func(self) -> Callable[..., Any]:
		async def _make_request(*args: Any, **kwargs: Any) -> aiohttp.ClientResponse | None:
			return await self._handle_statuses(await self._session.request(*args, **kwargs))

		return reduce(lambda t, s: s(t), reversed(self._middlewares), _make_request)

	async def _handle_request(
		self,
		method: str,
		url: str,
		make_request_func: Callable[..., Any],
		**kw: Any,
	) -> R:
		if self.config.useragent_factory is not None:
			user_agent_header = {"User-Agent": self.config.useragent_factory()}
			kw["headers"] = kw.get("headers", {}) | user_agent_header

		return await make_request_func(method, url, **kw)

	async def _handle_retry(self, e: Exception, attempt: int, url: str, method: str, **kws: Any) -> None:
		if attempt == self.config.maximum_retries:
			raise RanOutOfAttemptsError(f"failed after {self.config.maximum_retries} retries: {type(e)} {e}") from e

		await asyncio.sleep(self.config.base * min(MAXIMUM_BACKOFF, self.config.backoff**attempt))

	async def _handle_to_raise(self, e: Exception, attempt: int, url: str, method: str, **kw: Any) -> None:
		if self.config.exception_settings.exc_to_raise is None:
			raise e

		exc, argfunc = self.config.exception_settings.exc_to_raise, self.config.exception_settings.args_for_exc_func

		a, exckw = argfunc(e, attempt, url, method, **kw)
		if exckw is None:
			raise exc(*a) from e

		raise exc(*a, **exckw) from e

	async def _handle_exception(self, e: Exception, attempt: int, url: str, method: str, **kw: Any) -> None:
		if self.config.exception_settings.unspecified == "raise":
			raise e

		await self._handle_retry(e, attempt, url, method, **kw)

	async def _request_with_retry(self, method: str, url: str, **kw: Any) -> R:
		_make_request = self._get_make_request_func()
		for attempt in range(self.config.maximum_retries + 1):
			try:
				return await self._handle_request(method, url, _make_request, **kw)
			except self.config.exception_settings.to_retry + (StatusRetryError,) as e:
				await self._handle_retry(e, attempt, url, method, **kw)
			except self.config.exception_settings.to_raise as e:
				await self._handle_to_raise(e, attempt, url, method, **kw)
			except Exception as e:
				await self._handle_exception(e, attempt, url, method, **kw)

		return await _make_request()

	async def get(self, url: str, **kwargs: Any) -> R:
		return await self._request_with_retry("GET", url, **kwargs)

	async def post(self, url: str, **kwargs: Any) -> R:
		return await self._request_with_retry("POST", url, **kwargs)

	async def put(self, url: str, **kwargs: Any) -> R:
		return await self._request_with_retry("PUT", url, **kwargs)

	async def delete(self, url: str, **kwargs: Any) -> R:
		return await self._request_with_retry("DELETE", url, **kwargs)

	async def patch(self, url: str, **kwargs: Any) -> R:
		return await self._request_with_retry("PATCH", url, **kwargs)

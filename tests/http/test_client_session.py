import ssl

import aiohttp
import pytest
import pytest_asyncio
from aiohttp import web
from aiohttp.test_utils import TestServer

from sotkalib.http.client_session import (
	ClientSettings,
	ExceptionSettings,
	HTTPSession,
	RanOutOfAttemptsError,
	RequestContext,
	StatusRetryError,
	StatusSettings,
	_make_ssl_context,
)


@pytest.fixture
def app():
	application = web.Application()

	async def ok_handler(_):
		return web.json_response({"status": "ok"})

	async def error_handler(_):
		return web.Response(status=500, text="Internal Server Error")

	async def not_found_handler(_):
		return web.Response(status=404, text="Not Found")

	async def forbidden_handler(_):
		return web.Response(status=403, text="Forbidden")

	async def rate_limit_handler(_):
		return web.Response(status=429, text="Too Many Requests")

	async def echo_headers_handler(request):
		return web.json_response(dict(request.headers))

	async def echo_body_handler(request):
		data = await request.json()
		return web.json_response({"received": data})

	application.router.add_get("/ok", ok_handler)
	application.router.add_post("/ok", ok_handler)
	application.router.add_put("/ok", ok_handler)
	application.router.add_delete("/ok", ok_handler)
	application.router.add_patch("/ok", ok_handler)
	application.router.add_get("/error", error_handler)
	application.router.add_get("/not-found", not_found_handler)
	application.router.add_get("/forbidden", forbidden_handler)
	application.router.add_get("/rate-limit", rate_limit_handler)
	application.router.add_get("/headers", echo_headers_handler)
	application.router.add_post("/echo", echo_body_handler)

	return application


@pytest_asyncio.fixture
async def server(app):
	srv = TestServer(app)
	await srv.start_server()
	yield srv
	await srv.close()


@pytest_asyncio.fixture
async def base_url(server):
	return f"http://localhost:{server.port}"


class TestMakeSslContext:
	def test_creates_context(self):
		ctx = _make_ssl_context()
		assert isinstance(ctx, ssl.SSLContext)
		assert ctx.check_hostname is True
		assert ctx.minimum_version == ssl.TLSVersion.TLSv1_2

	def test_disable_tls13(self):
		ctx = _make_ssl_context(disable_tls13=True)
		assert ctx.maximum_version == ssl.TLSVersion.TLSv1_2


class TestClientSettings:
	def test_defaults(self):
		s = ClientSettings()
		assert s.timeout == 5.0
		assert s.maximum_retries == 3
		assert s.backoff == 2.0

	def test_status_settings_defaults(self):
		s = StatusSettings()
		assert s.not_found_as_none is True

	def test_exception_settings_defaults(self):
		s = ExceptionSettings()
		assert s.unspecified == "retry"


class TestRequestContext:
	def test_basic_creation(self):
		ctx = RequestContext(method="GET", url="https://example.com")
		assert ctx.method == "GET"
		assert ctx.url == "https://example.com"
		assert ctx.attempt == 0
		assert ctx.errors == []

	def test_is_retry(self):
		ctx = RequestContext(method="GET", url="https://example.com")
		assert ctx.is_retry is False
		ctx.attempt = 1
		assert ctx.is_retry is True

	def test_status_property(self):
		ctx = RequestContext(method="GET", url="https://example.com")
		assert ctx.status is None

	def test_merge_headers(self):
		ctx = RequestContext(method="GET", url="https://example.com")
		ctx.merge_headers({"Authorization": "Bearer token"})
		assert ctx.headers == {"Authorization": "Bearer token"}

		ctx.merge_headers({"X-Custom": "value"})
		assert ctx.headers == {"Authorization": "Bearer token", "X-Custom": "value"}

	def test_to_request_kwargs(self):
		ctx = RequestContext(
			method="POST",
			url="https://example.com",
			params={"q": "search"},
			headers={"Auth": "token"},
			json={"data": "value"},
		)
		kw = ctx.to_request_kwargs()
		assert kw["params"] == {"q": "search"}
		assert kw["headers"] == {"Auth": "token"}
		assert kw["json"] == {"data": "value"}

	def test_state_dict(self):
		ctx = RequestContext(method="GET", url="https://example.com")
		ctx.state["request_id"] = "abc123"
		assert ctx.state["request_id"] == "abc123"


class TestClientSession:
	@pytest.mark.asyncio
	async def test_get(self, base_url):
		config = ClientSettings(session_kwargs={"connector": aiohttp.TCPConnector(ssl=False)})
		async with HTTPSession(config) as session:
			resp = await session.get(f"{base_url}/ok")
			data = await resp.json()
			assert data == {"status": "ok"}

	@pytest.mark.asyncio
	async def test_post(self, base_url):
		config = ClientSettings(session_kwargs={"connector": aiohttp.TCPConnector(ssl=False)})
		async with HTTPSession(config) as session:
			resp = await session.post(f"{base_url}/ok")
			data = await resp.json()
			assert data == {"status": "ok"}

	@pytest.mark.asyncio
	async def test_put(self, base_url):
		config = ClientSettings(session_kwargs={"connector": aiohttp.TCPConnector(ssl=False)})
		async with HTTPSession(config) as session:
			resp = await session.put(f"{base_url}/ok")
			data = await resp.json()
			assert data == {"status": "ok"}

	@pytest.mark.asyncio
	async def test_delete(self, base_url):
		config = ClientSettings(session_kwargs={"connector": aiohttp.TCPConnector(ssl=False)})
		async with HTTPSession(config) as session:
			resp = await session.delete(f"{base_url}/ok")
			data = await resp.json()
			assert data == {"status": "ok"}

	@pytest.mark.asyncio
	async def test_patch(self, base_url):
		config = ClientSettings(session_kwargs={"connector": aiohttp.TCPConnector(ssl=False)})
		async with HTTPSession(config) as session:
			resp = await session.patch(f"{base_url}/ok")
			data = await resp.json()
			assert data == {"status": "ok"}

	@pytest.mark.asyncio
	async def test_not_found_returns_none(self, base_url):
		config = ClientSettings(session_kwargs={"connector": aiohttp.TCPConnector(ssl=False)})
		async with HTTPSession(config) as session:
			resp = await session.get(f"{base_url}/not-found")
			assert resp is None

	@pytest.mark.asyncio
	async def test_retry_on_429_exhausts(self, base_url):
		config = ClientSettings(
			maximum_retries=1,
			base=0.01,
			session_kwargs={"connector": aiohttp.TCPConnector(ssl=False)},
		)
		async with HTTPSession(config) as session:
			with pytest.raises(RanOutOfAttemptsError):
				await session.get(f"{base_url}/rate-limit")

	@pytest.mark.asyncio
	async def test_useragent_factory(self, base_url):
		config = ClientSettings(
			useragent_factory=lambda: "TestBot/1.0",
			session_kwargs={"connector": aiohttp.TCPConnector(ssl=False)},
		)
		async with HTTPSession(config) as session:
			resp = await session.get(f"{base_url}/headers")
			data = await resp.json()
			assert data["User-Agent"] == "TestBot/1.0"


class TestMiddleware:
	@pytest.mark.asyncio
	async def test_passthrough_middleware(self, base_url):
		"""Test middleware that passes through without modifying response type."""
		call_log = []

		async def logging_mw(ctx: RequestContext, next):
			call_log.append(f"before: {ctx.method} {ctx.url}")
			result = await next(ctx)
			call_log.append(f"after: {ctx.status}")
			return result

		config = ClientSettings(session_kwargs={"connector": aiohttp.TCPConnector(ssl=False)})
		session = HTTPSession(config).use(logging_mw)
		async with session as s:
			resp = await s.get(f"{base_url}/ok")
			assert resp is not None
			data = await resp.json()
			assert data == {"status": "ok"}

		assert len(call_log) == 2
		assert "before: GET" in call_log[0]
		assert "after: 200" in call_log[1]

	@pytest.mark.asyncio
	async def test_header_modifying_middleware(self, base_url):
		"""Test middleware that modifies request headers via context."""

		async def auth_mw(ctx: RequestContext, next):
			ctx.merge_headers({"X-Test-Header": "middleware-value"})
			return await next(ctx)

		config = ClientSettings(session_kwargs={"connector": aiohttp.TCPConnector(ssl=False)})
		session = HTTPSession(config).use(auth_mw)
		async with session as s:
			resp = await s.get(f"{base_url}/headers")
			data = await resp.json()
			assert data["X-Test-Header"] == "middleware-value"

	@pytest.mark.asyncio
	async def test_type_transforming_middleware(self, base_url):
		"""Test middleware that transforms response type from ClientResponse to dict."""

		async def json_mw(ctx: RequestContext, next) -> dict:
			resp = await next(ctx)
			if resp is None:
				return {}
			return await resp.json()

		config = ClientSettings(session_kwargs={"connector": aiohttp.TCPConnector(ssl=False)})
		session: HTTPSession[dict] = HTTPSession(config).use(json_mw)
		async with session as s:
			data = await s.get(f"{base_url}/ok")
			assert isinstance(data, dict)
			assert data == {"status": "ok"}

	@pytest.mark.asyncio
	async def test_middleware_chain(self, base_url):
		"""Test chaining multiple middlewares."""
		order = []

		async def mw1(ctx: RequestContext, next):
			order.append("mw1-before")
			result = await next(ctx)
			order.append("mw1-after")
			return result

		async def mw2(ctx: RequestContext, next):
			order.append("mw2-before")
			result = await next(ctx)
			order.append("mw2-after")
			return result

		async with (
			HTTPSession(ClientSettings(session_kwargs={"connector": aiohttp.TCPConnector(ssl=False)}))
			.use(mw1)
			.use(mw2) as s
		):
			await s.get(f"{base_url}/ok")

		assert order == ["mw1-before", "mw2-before", "mw2-after", "mw1-after"]

	@pytest.mark.asyncio
	async def test_middleware_can_use_state(self, base_url):
		"""Test that middleware can share data via context.state."""
		captured_request_id = None

		async def id_mw(ctx: RequestContext, next):
			ctx.state["request_id"] = "test-123"
			return await next(ctx)

		async def capture_mw(ctx: RequestContext, next):
			nonlocal captured_request_id
			captured_request_id = ctx.state.get("request_id")
			return await next(ctx)

		config = ClientSettings(session_kwargs={"connector": aiohttp.TCPConnector(ssl=False)})
		session = HTTPSession(config).use(id_mw).use(capture_mw)
		async with session as s:
			await s.get(f"{base_url}/ok")

		assert captured_request_id == "test-123"

	@pytest.mark.asyncio
	async def test_middleware_sees_attempt_on_retry(self, base_url):
		"""Test that middleware can see attempt count during retries."""
		attempts_seen = []

		async def tracking_mw(ctx: RequestContext, next):
			attempts_seen.append(ctx.attempt)
			return await next(ctx)

		config = ClientSettings(
			maximum_retries=2,
			base=0.01,
			session_kwargs={"connector": aiohttp.TCPConnector(ssl=False)},
		)
		session = HTTPSession(config).use(tracking_mw)
		async with session as s:
			with pytest.raises(RanOutOfAttemptsError):
				await s.get(f"{base_url}/rate-limit")

		assert attempts_seen == [0, 1, 2]


class TestStatusRetryError:
	def test_attributes(self):
		err = StatusRetryError(status=429, context="rate limited")
		assert err.status == 429
		assert err.context == "rate limited"
		assert "429" in str(err)

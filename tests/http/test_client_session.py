import ssl

import aiohttp
import pytest
import pytest_asyncio
from aiohttp import web
from aiohttp.test_utils import TestServer

from sotkalib.http.client_session import (
	ClientSession,
	ClientSettings,
	ExceptionSettings,
	RunOutOfAttemptsError,
	StatusRetryError,
	StatusSettings,
	_make_ssl_context,
)


@pytest.fixture
def app():
	application = web.Application()

	async def ok_handler(request):
		return web.json_response({"status": "ok"})

	async def error_handler(request):
		return web.Response(status=500, text="Internal Server Error")

	async def not_found_handler(request):
		return web.Response(status=404, text="Not Found")

	async def forbidden_handler(request):
		return web.Response(status=403, text="Forbidden")

	async def rate_limit_handler(request):
		return web.Response(status=429, text="Too Many Requests")

	async def echo_headers_handler(request):
		return web.json_response(dict(request.headers))

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


class TestClientSession:
	@pytest.mark.asyncio
	async def test_get(self, base_url):
		config = ClientSettings(session_kwargs={"connector": aiohttp.TCPConnector(ssl=False)})
		async with ClientSession(config) as session:
			resp = await session.get(f"{base_url}/ok")
			data = await resp.json()
			assert data == {"status": "ok"}

	@pytest.mark.asyncio
	async def test_post(self, base_url):
		config = ClientSettings(session_kwargs={"connector": aiohttp.TCPConnector(ssl=False)})
		async with ClientSession(config) as session:
			resp = await session.post(f"{base_url}/ok")
			data = await resp.json()
			assert data == {"status": "ok"}

	@pytest.mark.asyncio
	async def test_put(self, base_url):
		config = ClientSettings(session_kwargs={"connector": aiohttp.TCPConnector(ssl=False)})
		async with ClientSession(config) as session:
			resp = await session.put(f"{base_url}/ok")
			data = await resp.json()
			assert data == {"status": "ok"}

	@pytest.mark.asyncio
	async def test_delete(self, base_url):
		config = ClientSettings(session_kwargs={"connector": aiohttp.TCPConnector(ssl=False)})
		async with ClientSession(config) as session:
			resp = await session.delete(f"{base_url}/ok")
			data = await resp.json()
			assert data == {"status": "ok"}

	@pytest.mark.asyncio
	async def test_patch(self, base_url):
		config = ClientSettings(session_kwargs={"connector": aiohttp.TCPConnector(ssl=False)})
		async with ClientSession(config) as session:
			resp = await session.patch(f"{base_url}/ok")
			data = await resp.json()
			assert data == {"status": "ok"}

	@pytest.mark.asyncio
	async def test_not_found_returns_none(self, base_url):
		config = ClientSettings(session_kwargs={"connector": aiohttp.TCPConnector(ssl=False)})
		async with ClientSession(config) as session:
			resp = await session.get(f"{base_url}/not-found")
			assert resp is None

	@pytest.mark.asyncio
	async def test_retry_on_429_exhausts(self, base_url):
		config = ClientSettings(
			maximum_retries=1,
			base=0.01,
			session_kwargs={"connector": aiohttp.TCPConnector(ssl=False)},
		)
		async with ClientSession(config) as session:
			with pytest.raises(RunOutOfAttemptsError):
				await session.get(f"{base_url}/rate-limit")

	@pytest.mark.asyncio
	async def test_useragent_factory(self, base_url):
		config = ClientSettings(
			useragent_factory=lambda: "TestBot/1.0",
			session_kwargs={"connector": aiohttp.TCPConnector(ssl=False)},
		)
		async with ClientSession(config) as session:
			resp = await session.get(f"{base_url}/headers")
			data = await resp.json()
			assert data["User-Agent"] == "TestBot/1.0"

	@pytest.mark.asyncio
	async def test_middleware(self, base_url):
		call_log = []

		def logging_mw(handler):
			async def wrapper(*args, **kwargs):
				call_log.append("before")
				result = await handler(*args, **kwargs)
				call_log.append("after")
				return result

			return wrapper

		config = ClientSettings(session_kwargs={"connector": aiohttp.TCPConnector(ssl=False)})
		session = ClientSession(config).use(logging_mw)
		async with session as s:
			await s.get(f"{base_url}/ok")

		assert call_log == ["before", "after"]


class TestStatusRetryError:
	def test_attributes(self):
		err = StatusRetryError(status=429, context="rate limited")
		assert err.status == 429
		assert err.context == "rate limited"
		assert "429" in str(err)

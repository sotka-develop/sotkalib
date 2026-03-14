import http

from sotkalib.exceptions.api import APIError, BaseHTTPError, ErrorSchema


class TestErrorSchema:
	def test_defaults(self):
		schema = ErrorSchema()
		assert schema.code is None
		assert schema.desc is None
		assert schema.ctx is None

	def test_with_values(self):
		schema = ErrorSchema(code="ERR_01", desc="invalid input", ctx={"field": "name"})
		assert schema.code == "ERR_01"
		assert schema.ctx == {"field": "name"}


class TestBaseHTTPError:
	def test_with_detail(self):
		err = BaseHTTPError(400, detail="bad input")
		assert err.status_code == 400
		assert err.detail == "bad input"
		assert str(err) == "400: bad input"

	def test_default_detail(self):
		err = BaseHTTPError(404)
		assert err.detail == "Not Found"

	def test_repr(self):
		err = BaseHTTPError(500, detail="boom")
		assert "BaseHTTPError" in repr(err)
		assert "500" in repr(err)

	def test_headers(self):
		err = BaseHTTPError(401, headers={"WWW-Authenticate": "Bearer"})
		assert err.headers == {"WWW-Authenticate": "Bearer"}


class TestAPIError:
	def test_default(self):
		err = APIError()
		assert err.status == http.HTTPStatus.BAD_REQUEST

	def test_with_int_status(self):
		err = APIError(status=404)
		assert err.status == http.HTTPStatus.NOT_FOUND

	def test_with_http_status(self):
		err = APIError(status=http.HTTPStatus.FORBIDDEN, code="FORBIDDEN", desc="no access")
		assert err.code == "FORBIDDEN"
		assert err.desc == "no access"

	def test_with_ctx_list(self):
		err = APIError(ctx=["field1", "field2"])
		assert err.ctx == ["field1", "field2"]
		assert err.schema.ctx == ["field1", "field2"]

	def test_inherits_base_http_error(self):
		err = APIError(status=422, code="VALIDATION")
		assert isinstance(err, BaseHTTPError)
		assert err.status_code == 422

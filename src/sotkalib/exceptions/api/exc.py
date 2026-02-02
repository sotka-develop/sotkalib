import http
from collections.abc import Mapping
from typing import Any

from pydantic import BaseModel


class ErrorSchema(BaseModel):
	code: str | None = None
	phrase: str | None = None
	desc: str | None = None
	ctx: Mapping[str, Any] | str | list[Any] | None = None


class BaseHTTPError(Exception):
	def __init__(self, status_code: int, detail: str | None = None, headers: Mapping[str, str] | None = None) -> None:
		if detail is None:
			detail = http.HTTPStatus(status_code).phrase
		self.status_code = status_code
		self.detail = detail
		self.headers = headers

	def __str__(self) -> str:
		return f"{self.status_code}: {self.detail}"

	def __repr__(self) -> str:
		class_name = self.__class__.__name__
		return f"{class_name}(status_code={self.status_code!r}, detail={self.detail!r})"


class APIError(BaseHTTPError):
	def __init__(
		self,
		*,
		status: http.HTTPStatus | int = http.HTTPStatus.BAD_REQUEST,
		code: str | None = None,
		desc: str | None = None,
		ctx: Mapping[str, Any] | list[Any] | str | None = None,
	):
		if isinstance(status, int):
			status = http.HTTPStatus(status)

		self.status = status
		self.phrase = status.phrase
		self.code = code
		self.desc = desc
		self.ctx = ctx

		self.schema = ErrorSchema(
			code=self.code,
			phrase=self.phrase,
			desc=self.desc,
			ctx=self.ctx,
		)

		super().__init__(status_code=self.status.value, detail=self.schema.model_dump_json())

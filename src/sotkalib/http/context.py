import time
from dataclasses import dataclass, field
from typing import Any

import aiohttp


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

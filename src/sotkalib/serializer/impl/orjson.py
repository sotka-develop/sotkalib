from typing import Any

import orjson


class ORJSONSerializer:
	@staticmethod
	def marshal(data: Any) -> bytes:
		return orjson.dumps(data)

	@staticmethod
	def unmarshal(raw_data: bytes) -> Any:
		return orjson.loads(raw_data)

from typing import Any

import orjson


class OrJsonSerializer:
	def marshal(self, data: Any) -> bytes:
		return orjson.dumps(data)

	def unmarshal(self, raw_data: bytes) -> Any:
		return orjson.loads(raw_data)

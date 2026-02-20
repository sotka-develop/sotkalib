import json
from typing import Any


class StdJSONSerializer:
	@staticmethod
	def marshal(data: Any) -> bytes:
		return json.dumps(data).encode()

	@staticmethod
	def unmarshal(raw_data: bytes) -> Any:
		return json.loads(raw_data)

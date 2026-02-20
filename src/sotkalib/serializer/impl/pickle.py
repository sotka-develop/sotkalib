import os
from base64 import b64decode, b64encode
from pickle import HIGHEST_PROTOCOL, dumps, loads
from typing import Any
from warnings import warn

_pickle_allowed = (os.getenv("SOTKALIB_ALLOW_PICKLE", "").lower() == "yes") or False


class SecurityWarning(Warning): ...


class B64Pickle:
	@staticmethod
	def marshal(data: Any) -> bytes:
		if not _pickle_allowed:
			warn(
				"sotkalib.redis.lru is using pickle serializer."
				" This is not recommended for production,"
				" as deserialization with pickle may execute arbitrary code.\n\n"
				"You may silence this warning by using a different serializer or set"
				"ting the environment variable SOTKALIB_ALLOW_PICKLE=yes",
				stacklevel=2,
				category=SecurityWarning,
			)

		dumped = dumps(data, protocol=HIGHEST_PROTOCOL)
		dumped_b64 = b64encode(dumped)
		return dumped_b64

	@staticmethod
	def unmarshal(raw_data: bytes) -> Any:
		return loads(b64decode(raw_data))  # noqa

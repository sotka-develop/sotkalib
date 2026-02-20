from typing import Any

import msgspec.json as msgspec_json
import msgspec.msgpack as msgspec_msgpack
from msgspec import Struct

from . import _typed_serializer_generic_mixin


class MSJSONSerializer:
	@staticmethod
	def marshal(data: Any) -> bytes:
		return msgspec_json.encode(data)

	@staticmethod
	def unmarshal(raw_data: bytes) -> Any:
		return msgspec_json.decode(raw_data)


class MsgpackSerializer:
	@staticmethod
	def marshal(data: Any) -> bytes:
		return msgspec_msgpack.encode(data)

	@staticmethod
	def unmarshal(raw_data: bytes) -> Any:
		return msgspec_msgpack.decode(raw_data)


class TypedMSJSONSerializer[T: Struct](_typed_serializer_generic_mixin):
	def marshal(self, data: T) -> bytes:
		return msgspec_json.encode(data)

	def unmarshal(self, raw_data: bytes) -> T:
		return msgspec_json.decode(raw_data, type=self.type_)


class TypedMsgpackSerializer[T: Struct](_typed_serializer_generic_mixin):
	def marshal(self, data: T) -> bytes:
		return msgspec_msgpack.encode(data)

	def unmarshal(self, raw_data: bytes) -> T:
		return msgspec_msgpack.decode(raw_data, type=self.type_)

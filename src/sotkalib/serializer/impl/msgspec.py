"""requires sotkalib[msgspec] extra to be installed"""

from typing import Any, Self

import msgspec.json as msgspec_json
import msgspec.msgpack as msgspec_msgpack

from sotkalib.type.generics import func

from .mixin import TypedSerializerGenericMixin


class _msgspec_mixin:  # noqa: N801
	_enc_hook: func[[Any], Any] | None
	_dec_hook: func[[type, Any], Any] | None

	@classmethod
	def with_hooks(
		cls,
		enc_hook: func[[Any], Any] | None = None,
		dec_hook: func[[type, Any], Any] | None = None,
	) -> Self:
		inst = cls()
		inst._dec_hook = dec_hook
		inst._enc_hook = enc_hook
		return inst


class MsgspecJsonSerializer(_msgspec_mixin):
	def marshal(self, data: Any) -> bytes:
		return msgspec_json.encode(data, enc_hook=self._enc_hook)

	def unmarshal(self, raw_data: bytes) -> Any:
		return msgspec_json.decode(raw_data, dec_hook=self._dec_hook)


class MsgspecMsgpackSerializer(_msgspec_mixin):
	def marshal(self, data: Any) -> bytes:
		return msgspec_msgpack.encode(data, enc_hook=self._enc_hook)

	def unmarshal(self, raw_data: bytes) -> Any:
		return msgspec_msgpack.decode(raw_data, dec_hook=self._dec_hook)


class TypedMsgspecJsonSerializer[T](TypedSerializerGenericMixin, _msgspec_mixin):
	def marshal(self, data: T) -> bytes:
		return msgspec_json.encode(data, enc_hook=self._enc_hook)

	def unmarshal(self, raw_data: bytes) -> T:
		return msgspec_json.decode(raw_data, type=self.type_, dec_hook=self._dec_hook)


class TypedMsgspecMsgpackSerializer[T](TypedSerializerGenericMixin, _msgspec_mixin):
	def marshal(self, data: T) -> bytes:
		return msgspec_msgpack.encode(data, enc_hook=self._enc_hook)

	def unmarshal(self, raw_data: bytes) -> T:
		return msgspec_msgpack.decode(raw_data, type=self.type_, dec_hook=self._dec_hook)

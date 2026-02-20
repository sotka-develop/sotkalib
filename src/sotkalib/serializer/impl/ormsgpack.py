"""requires sotkalib[ormsgpack] extra to be installed"""

from typing import Any, Self

import ormsgpack


class _ormsgpack_mixin:  # noqa: N801
	_option: int = ormsgpack.OPT_SERIALIZE_PYDANTIC

	@classmethod
	def with_opt(
		cls,
		option: int = _option,
	) -> Self:
		inst = cls()
		inst._option = option
		return inst


class OrMsgpackSerializer(_ormsgpack_mixin):
	def marshal(self, data: Any) -> bytes:
		return ormsgpack.packb(data, option=self._option)

	def unmarshal(self, raw_data: bytes) -> Any:
		return ormsgpack.unpackb(raw_data, option=self._option)

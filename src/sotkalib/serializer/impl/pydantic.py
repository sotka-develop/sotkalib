from pydantic import BaseModel

from .mixin import TypedSerializerGenericMixin


class PydanticSerializer[T: BaseModel](TypedSerializerGenericMixin):
	def marshal(self, data: T) -> bytes:  # noqa
		return data.model_dump_json(
			exclude_unset=True,
			exclude_defaults=True,
			exclude_computed_fields=True,
		).encode()

	def unmarshal(self, raw_data: bytes) -> T:
		return self.type_.model_validate_strings(raw_data)

from pydantic import BaseModel

from . import _typed_serializer_generic_mixin


class PydanticSerializer[T: BaseModel](_typed_serializer_generic_mixin):
	def marshal(self, data: T) -> bytes:  # noqa
		return data.model_dump_json(
			exclude_unset=True,
			exclude_defaults=True,
			exclude_computed_fields=True,
		).encode()

	def unmarshal(self, raw_data: bytes) -> T:
		return self.type_.model_validate_strings(raw_data)

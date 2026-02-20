from typing import Any, Protocol

from ...type.generics import strlike


class Serializer(Protocol):
	def marshal(self, data: Any) -> strlike: ...
	def unmarshal(self, raw_data: strlike) -> Any: ...


class TypedSerializer[T](Protocol):
	type_: type[T]

	def marshal(self, data: T) -> strlike: ...
	def unmarshal(self, raw_data: strlike) -> T: ...

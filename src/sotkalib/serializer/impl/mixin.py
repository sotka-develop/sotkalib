from typing import Self


class TypedSerializerGenericMixin[T]:
	type_: type[T]

	@classmethod
	def __class_getitem__(cls, typ: type[T]) -> type[Self]:
		return type(f"{cls.__name__}[{typ.__name__}]", (cls,), {"type_": typ})

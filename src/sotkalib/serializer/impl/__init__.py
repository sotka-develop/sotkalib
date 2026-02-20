from typing import Self


class _typed_serializer_generic_mixin[T]:  # noqa
	type_: type[T]

	def __class_getitem__(cls, typ: type[T]) -> type[Self]:
		return type(f"{cls.__name__}[{typ.__name__}]", (cls,), {"type_": typ})  # type: ignore[return-value,attr-defined]

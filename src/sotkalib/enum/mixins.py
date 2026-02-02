from collections.abc import Sequence
from enum import Enum
from typing import Any, Literal, Self, overload


class UppercaseStrEnumMixin(str, Enum):
    @staticmethod
    def _generate_next_value_(name: str, start: int, count: int, last_values: Sequence) -> str:  # noqa
        return name.upper()


class ValidatorStrEnumMixin(str, Enum):
    @classmethod
    def _normalize_value(cls, val: Any) -> str:
        if isinstance(val, (str, bytes, bytearray)):
            return val.decode("utf-8") if isinstance(val, (bytes, bytearray)) else val
        raise TypeError("value must be str-like")

    @overload
    @classmethod
    def validate(cls, *, val: Any, req: Literal[False] = False) -> Self | None: ...

    @overload
    @classmethod
    def validate(cls, *, val: Any, req: Literal[True]) -> Self: ...

    @classmethod
    def validate(cls, *, val: Any, req: bool = False) -> Self | None:
        if val is None:
            if req:
                raise ValueError("value is None and req=True")
            return None
        normalized = cls._normalize_value(val)
        try:
            return cls(normalized)
        except ValueError as e:
            raise TypeError(f"{normalized=} not valid: {e}") from e

    @overload
    @classmethod
    def get(cls, val: Any, default: Literal[None] = None) -> Self | None: ...

    @overload
    @classmethod
    def get(cls, val: Any, default: Self) -> Self: ...

    @classmethod
    def get(cls, val: Any, default: Self | None = None) -> Self | None:
        try:
            return cls.validate(val=val, req=False) or default
        except (ValueError, TypeError):
            return default

    def in_(self, *enum_values: Self) -> bool:
        return self in enum_values

    @classmethod
    def values(cls) -> Sequence[Self]:
        return list(cls)

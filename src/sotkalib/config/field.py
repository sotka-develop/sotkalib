from collections.abc import Callable
from dataclasses import dataclass

type AllowedTypes = int | float | complex | str | bool | None


@dataclass(init=True, slots=True, frozen=True)
class SettingsField[T: AllowedTypes]:
    default: T | None = None
    factory: Callable[[], T] | str | None = None
    nullable: bool = False

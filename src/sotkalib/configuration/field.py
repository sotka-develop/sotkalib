from collections.abc import Callable
from dataclasses import dataclass


type _allowedTypes = int | float | complex | str | bool | None


@dataclass(init=True, slots=True, frozen=True)
class SettingsField[T: _allowedTypes]:
    """

    Typed field declaration for AppSettings.

    **Parameters:**

    - `T`: Python type of the value (int | float | complex | str | bool | None).

    **Attributes:**

    - `default`: Optional fallback value when the variable is missing.
    - `factory`: A callable returning a value, or a name of a @property on the class that will be evaluated after initialization.
    - `nullable`: Whether None is allowed when no value is provided and no default/factory is set.

    """

    default: T = None
    factory: Callable[[], T] | str = None
    nullable: bool = True

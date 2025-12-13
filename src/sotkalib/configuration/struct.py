from __future__ import annotations

import re
from _warnings import warn
from dataclasses import dataclass
from os import PathLike, getenv
from types import NoneType, UnionType
from typing import TYPE_CHECKING, Any, get_args

from dotenv import load_dotenv

from sotkalib.logging import get_logger

from .field import SettingsField

type _allowedTypes = int | float | complex | str | bool | None


if TYPE_CHECKING:
    from logging import (
        Logger as StdLogger,
    )

    from loguru import Logger as LoguruLogger

    type _loggers = StdLogger | LoguruLogger


@dataclass
class AppSettings:
    """

    Base class for reading typed settings from environment variables.

        Declare attributes with type annotations and assign SettingsField(...) to each.
        On initialization, values are resolved from the environment (loading .env if provided),
        then from default/factory, or set to None if nullable.

        **Notes:**

        Only immutable primitive types are allowed: int, float, complex, str, bool, None.

        If explicit_format is True, attribute names must be UPPER_SNAKE_CASE.

        **Example:**

        >>> import secrets
        >>> class MySettings(AppSettings):
        ...     BOT_TOKEN: str = SettingsField(nullable=False)
        ...     POSTGRES_USER: str = SettingsField(default="pg_user")
        ...     POSTGRES_PASSWORD: str = SettingsField(nullable=False, factory=secrets.token_urlsafe(8))
        ...     SECRET_ALIAS: str = SettingsField(factory="secret")
        ...
        ...     @property
        ...     def secret(self) -> str:
        ...         return "computed"


        >>> settings = MySettings()

    """

    def __init__(
        self,
        dotenv_path: str | PathLike[str] | None = None,
        logger: _loggers | None = None,
        explicit_format: bool = True,
        strict: bool = False,
    ) -> None:
        """

        Initialize AppSettings and resolve annotated fields.

        **Parameters:**

        - `dotenv_path`: Optional path to a .env file. If None, python-dotenv searches recursively.
        - `logger`: Optional logging or loguru logger.
        - `explicit_format`: If True, attribute names must be uppercase with underscores.
        - `strict`: If True, any mutable types will raise an exception rather than being set to
        None.

        **Raises:**

        - `AttributeError`: If an attribute name violates explicit_format constraint or a declared property is missing.
        - `TypeError`: If an annotation uses a disallowed (mutable) type or a factory reference is not a property.
        - `ValueError`: If a required field (nullable=False, no default/factory) is missing in the environment.

        """

        def evaluate_var(_type: type, _var: str) -> Any:
            if _type is NoneType:
                return None
            if _type is bool:
                return _var.lower() in ("yes", "true", "1", "y")
            return _type(_var)

        load_dotenv(dotenv_path=dotenv_path)

        _log = get_logger("utilities.appsettings") if logger is None else logger
        self.__log = _log

        self.__strict = strict

        cls_annotations = self.__class__.__annotations__
        cls_dict = self.__class__.__dict__

        settings_fields: dict[str, SettingsField] = {
            attr: val for attr, val in cls_dict.items() if not attr.startswith("__")
        }

        self.__deferred = []

        for attr, settings_field in settings_fields.items():
            if explicit_format and not re.match(r"[A-Z_]", attr):
                raise AttributeError("AppSettings attributes should contain only capital letters and underscores")

            annotated = cls_annotations.get(attr, NoneType)
            string_value = getenv(attr, None)

            if string_value is None:
                self.__validate_empty_string_value(attr, settings_field)
                continue

            typed_value = evaluate_var(annotated, string_value)

            setattr(self, attr, self.__validate(typed_value, strict=self.__strict))
            _log.info(f"successfully evaluated {attr}={getattr(self, attr)!r}")

        self.__post_init__()

    def __validate_empty_string_value(self, attr: str, settings_field: SettingsField) -> None:
        if settings_field.default is not None:
            setattr(self, attr, self.__validate(settings_field.default, strict=self.__strict))
            self.__log.info(f"successfully evaluated {attr}={settings_field.default} by default")
            return

        if settings_field.factory is not None and isinstance(settings_field.factory, str):
            self.__deferred.append((attr, settings_field.factory))
            self.__log.info(f"defer {attr} init as factory is a str; => property")
            return

        if hasattr(settings_field.factory, "__call__"):
            setattr(self, attr, self.__validate(settings_field.factory(), strict=self.__strict))
            self.__log.info(f"successfully evaluated {attr} from factory")
            return

        if settings_field.nullable:
            setattr(self, attr, None)  # None is immutable by invariant
            self.__log.info(f"Nulled {attr}")
            return

        raise ValueError(f"reqd field {attr} was not found in .env")

    def __post_init__(self):
        for attr, factory in self.__deferred:
            if factory not in self.__class__.__dict__:
                raise AttributeError(f"property {factory} was not found in {self.__class__.__name__}")
            if not isinstance(getattr(self.__class__, factory), property):
                raise TypeError(f"method {factory} is not a property")
            self.__log.info(f"successfully evaluated {attr} from property {factory}")
            setattr(self, attr, self.__validate(getattr(self, factory), strict=self.__strict))

    @staticmethod
    def __validate[T: Any](val: T, strict: bool) -> T | None:
        typeval = type(val)
        allowed = get_args(_allowedTypes.__value__)

        if typeval not in allowed or (isinstance(val, UnionType) and not all(t in allowed for t in get_args(val))):
            if strict:
                raise TypeError(
                    f"{val} ({typeval}) is not allowed for annotations as it, or one of its' members is mutable"
                )
            else:
                warn(f"{val} ({typeval}) is mutable, set value to None")
                return None

        return val

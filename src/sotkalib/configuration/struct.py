from __future__ import annotations

from dataclasses import dataclass
from logging import (
    Logger as StdLogger,
)
from os import getenv, PathLike
import re
from types import NoneType, UnionType
from typing import Any, get_args

from dotenv import load_dotenv
from loguru._logger import Logger

from sotkalib.logging import get_logger

from .field import SettingsField


type _allowedTypes = int | float | complex | str | bool | None
type _loggers = StdLogger | Logger


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

        _log: _loggers = get_logger("utilities.appsettings") if logger is None else logger
        self.__log: _loggers = _log

        self.__strict = strict

        cls_annotations: dict[str, Any] = self.__class__.__annotations__
        cls_dict: dict[str, Any] = self.__class__.__dict__

        setting_fields: dict[str, SettingsField] = {
            attr: val for attr, val in cls_dict.items() if not attr.startswith("__")
        }

        deferred: list[tuple[str, str]] = []

        for attr, settings_field in setting_fields.items():
            if explicit_format and not re.match(r"[A-Z_]", attr):
                raise AttributeError("AppSettings attributes should contain only capital letters and underscores")

            annotated: type = cls_annotations.get(attr, NoneType)

            self.__mutability_chk(annotated, strict)

            string_value: str | None = getenv(attr, None)

            if string_value is None:
                self.__validate_empty_string_value(attr, deferred, settings_field)
                continue

            typed_value: _allowedTypes = evaluate_var(annotated, string_value)

            self.__set_if_immutable(attr, typed_value)
            _log.info(f"successfully evaluated {attr}={typed_value!r}")

        self.__init_factory_defined(deferred=deferred)

    def __validate_empty_string_value(
        self, attr: str, deferred: list[tuple[str, str]], settings_field: SettingsField
    ) -> None:
        if settings_field.default is not None:
            self.__set_if_immutable(attr, settings_field.default)
            self.__log.info(f"Successfully evaluated {attr}={settings_field.default} by default")
            return

        if settings_field.factory is not None and isinstance(settings_field.factory, str):
            deferred.append((attr, settings_field.factory))
            self.__log.info(f"Postponed {attr} initialization as factory is a property")
            return

        if hasattr(settings_field.factory, "__call__"):
            self.__set_if_immutable(attr, settings_field.factory())
            self.__log.info(f"Successfully evaluated {attr} from factory")
            return

        if settings_field.nullable:
            setattr(self, attr, None)  # None is immutable by invariant
            self.__log.info(f"Nulled {attr}")
            return

        raise ValueError(f"Required field {attr} was not found in .env")

    def __set_if_immutable[T: _allowedTypes](self, key: str, value: T) -> None:
        value = self.__mutability_chk(type(value), strict=self.__strict)
        setattr(self, key, value)

    def __init_factory_defined(self, deferred: list[tuple[str, str]]):
        for attr, factory in deferred:
            if factory not in self.__class__.__dict__:
                raise AttributeError(f"Property {factory} was not found in {self.__class__.__name__}")
            if not isinstance(getattr(self.__class__, factory), property):
                raise TypeError(f"Method {factory} is not a property")
            self.__log.info(f"Successfully evaluated {attr} from property {factory}")
            self.__set_if_immutable(attr, getattr(self, factory))

    @staticmethod
    def __mutability_chk[T: Any](annotated: T, strict: bool) -> T | None:
        if isinstance(annotated, get_args(_allowedTypes.__value__)):
            annotated = annotated.__value__
        # ??? TODO
        if annotated not in get_args(_allowedTypes.__value__) or (
            isinstance(annotated, UnionType)
            and not all(isinstance(annotated, _allowedTypes) for _type in get_args(annotated))
        ):
            if strict:
                raise TypeError(f"{annotated} is not allowed for annotations as it is mutable")
            else:
                return None

        return annotated

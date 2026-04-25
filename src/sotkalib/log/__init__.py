from __future__ import annotations

import sys
import threading
from collections.abc import Generator, Mapping, Sequence
from contextlib import contextmanager
from dataclasses import dataclass
from enum import Enum, auto
from logging import CRITICAL, DEBUG, INFO, WARNING, Handler, StreamHandler, getLogger
from sys import stdout
from typing import Any, NamedTuple, TextIO, TypedDict

import orjson
import structlog
from rich import traceback
from structlog.contextvars import (
	bind_contextvars,
	bound_contextvars,
	clear_contextvars,
	merge_contextvars,
)
from structlog.dev import RichTracebackFormatter
from structlog.stdlib import BoundLogger, LoggerFactory, ProcessorFormatter
from structlog.types import Processor

from ..type.unset import Unset, UnsetT, is_unset


class Environment(Enum):
	dev = auto()
	staging = auto()
	prod = auto()


_once = threading.Event()


@dataclass(frozen=True)
class Sink:
	renderer: Processor
	stream: TextIO = stdout
	level: int | str | None = None

	def build(self, shared: Sequence[Processor]) -> Handler:
		handler = StreamHandler(self.stream)
		handler.setFormatter(
			structlog.stdlib.ProcessorFormatter(
				foreign_pre_chain=shared,
				processors=[
					structlog.stdlib.ProcessorFormatter.remove_processors_meta,
					self.renderer,
				],
			)
		)
		if self.level is not None:
			handler.setLevel(self.level)
		return handler


def configure_logging(
	env: Environment = Environment.dev, override: LoggerSettingsOverride | None = None
) -> None:
	if _once.is_set():
		return
	_once.set()

	settings = _settings_for(env, override)
	_setup_std_logging(settings)

	structlog.configure(
		processors=[*settings["shared"], ProcessorFormatter.wrap_for_formatter],
		wrapper_class=BoundLogger,
		logger_factory=LoggerFactory(),
		cache_logger_on_first_use=True,
	)

	traceback.install()


def _setup_std_logging(
	settings: LoggerSettings,
) -> None:
	root = getLogger()
	root.handlers = [sink.build(settings["shared"]) for sink in settings["sinks"]]
	root.setLevel(settings["level"])

	for name, level in settings["named_loggers"].items():
		lg = getLogger(name)
		lg.handlers = []
		lg.propagate = True
		lg.setLevel(SHUT_THE_FUCK_UP_PLEASE_ONG if level is None else level)

	access = getLogger("uvicorn.access")
	access.propagate = settings["propagate_uvicorn_access"]


SHUT_THE_FUCK_UP_PLEASE_ONG = CRITICAL + 1


def get_logger(name: str | None = None) -> structlog.stdlib.BoundLogger:
	return structlog.get_logger(name)


def bind_context(**context: Any) -> None:
	bind_contextvars(**context)


def clear_context() -> None:
	clear_contextvars()


@contextmanager
def bound_context(**context: Any) -> Generator[None]:
	with bound_contextvars(**context):
		yield


def _sinks_for(env: Environment) -> list[Sink]:
	def json_serializer(value: Any, default: type = str, **kws) -> str:
		return orjson.dumps(value, default=default, **kws).decode()

	if env == Environment.dev:
		return [
			Sink(
				renderer=structlog.dev.ConsoleRenderer(
					exception_formatter=RichTracebackFormatter(),
				)
			)
		]
	if env == Environment.staging:
		return [
			Sink(renderer=structlog.processors.JSONRenderer(serializer=json_serializer)),
			Sink(renderer=structlog.dev.ConsoleRenderer(), stream=sys.stderr, level=WARNING),
		]
	return [Sink(renderer=structlog.processors.JSONRenderer(serializer=json_serializer))]


class LoggerSettings(TypedDict):
	level: int | str
	propagate_uvicorn_access: bool
	log_callsite: bool
	sinks: Sequence[Sink]
	shared: Sequence[Processor]
	named_loggers: Mapping[str, int | str | None]


_BASE_NAMED_LOGGERS: Mapping[str, int | str | None] = {
	"uvicorn": INFO,
	"uvicorn.error": WARNING,
	"uvicorn.access": WARNING,
	"sqlalchemy.engine": WARNING,
	"fsevents": None,
	"taskiq": WARNING,
	"taskiq.process-manager": WARNING,
	"taskiq.worker": WARNING,
}


def _named_loggers(
	default_level: int | str,
	prefix_level: Mapping[str, int | str | None] | None = None,
) -> dict[str, int | str | None]:
	"""
	Merge builtin silencing defaults with caller overrides, resolving each
	entry to its longest-matching prefix from the combined map. Entries
	without any matching prefix fall back to ``default_level``.

	Biggest prefix wins: ``{"taskiq": None, "taskiq.worker": "INFO"}`` keeps
	``taskiq.*`` silenced except the ``taskiq.worker`` subtree.
	"""

	if prefix_level is None:
		prefix_level = {}

	combined: dict[str, int | str | None] = {**_BASE_NAMED_LOGGERS, **prefix_level}
	prefixes = sorted(combined, key=len, reverse=True)
	resolved: dict[str, int | str | None] = {}
	for name in combined:
		match = next((p for p in prefixes if name == p or name.startswith(f"{p}.")), None)
		resolved[name] = combined[match] if match is not None else default_level
	return resolved


class LoggerSettingsOverride(NamedTuple):
	base_level: int | str | UnsetT = Unset
	include_callsite: bool | UnsetT = Unset
	additional_named_loggers: dict[str, int | str] = {}


def _settings_for(
	env: Environment,
	override: LoggerSettingsOverride | None = None,
) -> LoggerSettings:
	level: int | str
	match env:
		case Environment.dev:
			_scope_named = {
				"uvicorn": DEBUG,
				"uvicorn.access": DEBUG,
				"sqlalchemy.engine": DEBUG,
			}
			level = "DEBUG"
			setts: LoggerSettings = {
				"level": level,
				"propagate_uvicorn_access": True,
				"log_callsite": True,
				"sinks": _sinks_for(env),
				"shared": _shared_processors(include_callsite=True),
				"named_loggers": _named_loggers(
					level,
					_scope_named,
				),
			}
		case Environment.staging:
			level = "DEBUG"
			_scope_named = {}
			setts = {
				"level": level,
				"propagate_uvicorn_access": False,
				"log_callsite": True,
				"sinks": _sinks_for(env),
				"shared": _shared_processors(include_callsite=True),
				"named_loggers": _named_loggers(
					level,
				),
			}
		case Environment.prod:
			level = "INFO"
			_scope_named = {}
			setts = {
				"level": level,
				"propagate_uvicorn_access": False,
				"log_callsite": False,
				"sinks": _sinks_for(env),
				"shared": _shared_processors(include_callsite=False),
				"named_loggers": _named_loggers(
					level,
				),
			}
		case _:
			raise type("InvalidEnvironment", (BaseException,), {})(env)

	if override is not None:
		level, callsite, named = override

		if not is_unset(level):
			setts["level"] = level

		if not is_unset(callsite):
			setts["log_callsite"] = callsite
			setts["shared"] = _shared_processors(include_callsite=callsite)

		setts["named_loggers"] = _named_loggers(setts["level"], _scope_named | named)

	return setts


def _shared_processors(*, include_callsite: bool) -> list[Processor]:
	processors: list[Processor] = [
		merge_contextvars,
		structlog.stdlib.add_logger_name,
		structlog.stdlib.add_log_level,
		structlog.processors.TimeStamper(fmt="iso", utc=True),
		structlog.processors.StackInfoRenderer(),
		structlog.processors.format_exc_info,
		structlog.processors.UnicodeDecoder(),
	]
	if include_callsite:
		processors.append(
			structlog.processors.CallsiteParameterAdder(
				{
					structlog.processors.CallsiteParameter.FILENAME,
					structlog.processors.CallsiteParameter.FUNC_NAME,
					structlog.processors.CallsiteParameter.LINENO,
				}
			)
		)
	return processors


def _json_dumps(value: Any) -> str:
	return orjson.dumps(value, default=str).decode()


def _normalize_level(level: str | int) -> str | int:
	return level.upper() if isinstance(level, str) else level

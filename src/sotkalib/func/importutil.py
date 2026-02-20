from __future__ import annotations

import sys
from collections.abc import Generator
from contextlib import contextmanager
from importlib import import_module
from pathlib import Path
from typing import Any

from loguru import logger


@contextmanager
def add_cwd_in_path() -> Generator[None]:
	"""
	adds current directory in python path

	this context manager adds current directory in sys.path,
	so all python files are discoverable now, without installing
	current project

	:yield none
	"""
	cwd = Path.cwd()
	if str(cwd) in sys.path:
		yield
	else:
		logger.debug(f"inserting {cwd} in sys.path")
		sys.path.insert(0, str(cwd))
		try:
			yield
		finally:
			try:
				sys.path.remove(str(cwd))
			except ValueError:
				logger.warning(f"cannot remove '{cwd}' from sys.path")


def import_object(object_spec: str, app_dir: str | None = None) -> Any:
	"""
	parses python object spec and imports it

	Args:
		object_spec: string in format like `package.module:variable`
		app_dir: directory to add in sys.path for importing

	Raises:
		ValueError: if spec has unknown format

	Returns:
		imported object
	"""
	import_spec = object_spec.split(":")
	if len(import_spec) != 2:
		raise ValueError("you should provide object path in `module:variable` format.")
	with add_cwd_in_path():
		if app_dir:
			sys.path.insert(0, app_dir)
		module = import_module(import_spec[0])
	return getattr(module, import_spec[1])


def import_from_modules(modules: list[str]) -> None:
	"""
	import all modules from modules variable.

	:param modules: list of modules.
	"""
	for module in modules:
		try:
			logger.info(f"importing tasks from module {module}")
			with add_cwd_in_path():
				import_module(module)
		except ImportError as err:
			logger.warning(f"cannot import {module}. Cause:")
			logger.exception(err)


def object_fqn(obj: object) -> str:
	if hasattr(obj, "__name__"):
		return f"{obj.__module__}.{obj.__name__}"
	return f"{obj.__module__}.{obj.__class__.__name__}"


def get_type_fqn(arg: Any) -> str | None:
	_resolved_module = ""
	try:
		_resolved_module = arg.__module__
	except AttributeError:
		if arg.__class__.__name__ in __builtins__:
			_resolved_module = "builtins"

	if _resolved_module == "":
		return None

	return _resolved_module + ":" + arg.__class__.__name__


def get_type_from_fqn(_result: str | bytes | None) -> Any:
	_imported_type = None
	if _result is None:
		return _imported_type

	_decoded_result = _result.decode() if isinstance(_result, bytes) else _result
	try:
		_imported_type = import_object(_decoded_result)
	except Exception as exc:
		logger.warning("{}", exc)

	return _imported_type

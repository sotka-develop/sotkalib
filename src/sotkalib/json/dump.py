from datetime import date, datetime
from decimal import Decimal
from enum import Enum
from typing import Any
from uuid import UUID

import orjson

from sotkalib.log import get_logger


def safe_serialize_value(obj: Any) -> Any:
	val: Any

	match obj:
		case None:
			val = None
		case str() | int() | float() | bool():
			val = obj
		case datetime() | date():
			val = obj.isoformat()
		case Decimal():
			val = float(obj)
		case UUID():
			val = str(obj)
		case Enum():
			val = obj.value
		case bytes():
			val = obj.decode("utf-8", errors="replace")
		case dict():
			val = {k: safe_serialize_value(v) for k, v in obj.items()}
		case list() | tuple() | set() | frozenset():
			val = [safe_serialize_value(item) for item in obj]
		case _ if hasattr(obj, "model_dump"):
			try:
				val = {k: safe_serialize_value(v) for k, v in obj.model_dump().items()}
			except Exception:
				val = None
		case _ if hasattr(obj, "__dict__"):
			try:
				val = {k: safe_serialize_value(v) for k, v in obj.__dict__.items()}
			except Exception:
				val = None
		case _:
			try:
				orjson.dumps(obj)
				val = obj
			except TypeError, ValueError:
				val = None

	return val


def safe_serialize(data: Any) -> bytes:
	try:
		return orjson.dumps(safe_serialize_value(data))
	except BaseException:
		get_logger().exception("{}", data)
		raise

from datetime import date, datetime
from decimal import Decimal
from enum import Enum
from typing import Any
from uuid import UUID

import orjson

from sotkalib.func import suppress
from sotkalib.log import get_logger


def safe_serialize_value(obj: Any, _depth: int = 0, _depth_limit: int = 10) -> Any:
	if _depth > _depth_limit:
		return str(obj)

	if obj is None or isinstance(obj, (str, int, float, bool)):
		return obj

	if isinstance(obj, (datetime, date)):
		return obj.isoformat()
	if isinstance(obj, Decimal):
		return float(obj)
	if isinstance(obj, UUID):
		return str(obj)
	if isinstance(obj, Enum):
		return obj.value
	if isinstance(obj, bytes):
		return obj.decode("utf-8", errors="replace")

	if isinstance(obj, dict):
		return {k: safe_serialize_value(v, _depth + 1, _depth_limit) for k, v in obj.items()}
	if isinstance(obj, (list, tuple, set, frozenset)):
		return [safe_serialize_value(item, _depth + 1, _depth_limit) for item in obj]

	if hasattr(obj, "model_dump"):
		with suppress("exact", (TypeError, ValueError)):
			return {k: safe_serialize_value(v, _depth + 1, _depth_limit) for k, v in obj.model_dump().items()}

	if hasattr(obj, "__dict__"):
		with suppress("exact", (TypeError, ValueError)):
			return {k: safe_serialize_value(v, _depth + 1, _depth_limit) for k, v in obj.__dict__.items()}

	try:
		orjson.dumps(obj)
		return obj
	except (TypeError, ValueError):
		pass

	with suppress():
		return str(obj)
	return None


def safe_serialize(data: Any) -> bytes:
	try:
		return orjson.dumps(safe_serialize_value(data))
	except BaseException:
		get_logger().exception("{}", data)
		raise

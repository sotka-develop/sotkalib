from dataclasses import dataclass
from datetime import datetime
from typing import Any

from ...serializer.abc import Serializer
from ...serializer.impl.pickle import B64Pickle
from .abcs import keyfunc


def base_keyfunc(version: int, func_name: str, *args: tuple, **kwargs: dict[str, Any]) -> str:
	return f"{version}_{datetime.now().isoformat()}_{func_name}_{B64Pickle.marshal((args, kwargs))}"


@dataclass(slots=True, kw_only=True)
class LRUSettings:
	version: int = 1
	ttl: int = 600
	serializer: Serializer = B64Pickle
	keyfunc: keyfunc = base_keyfunc

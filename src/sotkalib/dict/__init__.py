from sotkalib.type import Unset
from typing import Any


def without_unset(d: dict[str, Any]) -> dict[str, Any]:
	newd = {}
	for k, v in d.items():
		if v == Unset:
			continue
		newd[k] = v
	return newd


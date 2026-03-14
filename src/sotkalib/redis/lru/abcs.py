from typing import Protocol


class keyfunc[**p](Protocol):  # noqa: N801
	def __call__(self, version: int, func_name: str, *args: p.args, **kwargs: p.kwargs) -> str: ...

from functools import lru_cache

from loguru import logger
from loguru._logger import Logger


@lru_cache
def get_logger(logger_name: str | None = None) -> Logger:
	return (
		logger  # type:ignore
		if logger_name is None
		else logger.bind(name=logger_name.replace(".", " -> "))
	)

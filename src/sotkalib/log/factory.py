from functools import lru_cache

from loguru import logger


@lru_cache
def get_logger(logger_name: str | None = None):
	return logger if logger_name is None else logger.bind(name=logger_name.replace(".", " -> "))

from functools import lru_cache

from loguru import Logger, logger


@lru_cache
def get_logger(logger_name: str | None = None) -> Logger:
	return logger if logger_name is None else logger.bind(name=logger_name.replace(".", " -> "))

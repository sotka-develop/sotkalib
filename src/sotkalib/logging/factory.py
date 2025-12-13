from functools import lru_cache

import loguru
from loguru import logger


@lru_cache
def get_logger(logger_name: str | None = None) -> loguru.Logger:
    """

    Return a cached loguru Logger optionally bound with a humanized name.

    If a name is provided, the returned logger is bound with extra["logger_name"]
    in a " src -> sub -> leaf " format so it can be referenced in loguru sinks.

    **Parameters:**

    - `logger_name`: Dotted logger name (e.g., "src.database.service"). If None, return the global logger.

    **Returns:**

    A cached loguru Logger with the extra context bound when name is provided.

    """

    return logger if logger_name is None else logger.bind(logger_name=f" {logger_name.replace('.', ' -> ')} ")

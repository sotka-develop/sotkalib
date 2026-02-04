import traceback


def traceback_from(exc: BaseException) -> str:
	return "".join(traceback.format_exception(exc))

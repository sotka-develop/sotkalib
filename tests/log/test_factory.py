from sotkalib.log.factory import get_logger


class TestGetLogger:
	def test_returns_logger(self):
		log = get_logger()
		assert log is not None

	def test_named_logger(self):
		log = get_logger("test.module")
		assert log is not None

	def test_cached(self):
		a = get_logger("cache.test")
		b = get_logger("cache.test")
		assert a is b

	def test_different_names_different_loggers(self):
		a = get_logger("one")
		b = get_logger("two")
		assert a is not b

	def test_name_formatting(self):
		log = get_logger("src.database.service")
		assert " src -> database -> service " in str(log._core.extra) or hasattr(log, "_log")

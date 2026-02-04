from datetime import UTC, datetime, timezone

from sotkalib.time import now, utcnow


class TestUtcnow:
	def test_returns_datetime(self):
		result = utcnow()
		assert isinstance(result, datetime)

	def test_has_utc_timezone(self):
		result = utcnow()
		assert result.tzinfo is UTC


class TestNow:
	def test_returns_datetime(self):
		result = now()
		assert isinstance(result, datetime)

	def test_with_timezone(self):
		tz = timezone.utc
		result = now(tz)
		assert result.tzinfo is tz

	def test_without_timezone(self):
		result = now()
		assert result.tzinfo is None

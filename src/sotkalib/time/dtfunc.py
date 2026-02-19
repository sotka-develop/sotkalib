from datetime import UTC, datetime, timezone


def utcnow() -> datetime:
	return datetime.now(UTC)


def now(tz: timezone | None = None) -> datetime:
	return datetime.now(tz)

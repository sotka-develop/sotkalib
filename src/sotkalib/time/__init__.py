from datetime import UTC, datetime, timezone


__all__ = ["utcnow", "now"]

def utcnow() -> datetime:
	return datetime.now(UTC)


def now(tz: timezone | None = None) -> datetime:
	return datetime.now(tz)

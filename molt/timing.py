"""Time utilities."""

from datetime import UTC, datetime, timedelta

POST_COOLDOWN = timedelta(minutes=30)


def now() -> datetime:
    return datetime.now(UTC)


def now_iso() -> str:
    return now().isoformat()


def fmt_ago(iso_str: str | None) -> str:
    if not iso_str:
        return "never"
    secs = int((now() - datetime.fromisoformat(iso_str)).total_seconds())
    if secs < 0:
        return "future?"
    if secs < 60:
        return f"{secs}s ago"
    if secs < 3600:
        return f"{secs // 60}m ago"
    if secs < 86400:
        return f"{secs // 3600}h {(secs % 3600) // 60}m ago"
    return f"{secs // 86400}d {(secs % 86400) // 3600}h ago"

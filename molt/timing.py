"""Time utilities — no DB dependency."""

from datetime import UTC, datetime, timedelta

POST_COOLDOWN = timedelta(minutes=30)


def now():
    return datetime.now(UTC)


def now_iso():
    return now().isoformat()


def fmt_ago(iso_str):
    if not iso_str:
        return "never"
    then = datetime.fromisoformat(iso_str)
    delta = now() - then
    secs = int(delta.total_seconds())
    if secs < 0:
        return "future?"
    if secs < 60:
        return f"{secs}s ago"
    if secs < 3600:
        return f"{secs // 60}m ago"
    if secs < 86400:
        return f"{secs // 3600}h {(secs % 3600) // 60}m ago"
    return f"{secs // 86400}d {(secs % 86400) // 3600}h ago"

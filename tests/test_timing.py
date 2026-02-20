"""Tests for molt.timing — time utilities."""

from datetime import UTC, datetime, timedelta

from molt.timing import POST_COOLDOWN, fmt_ago, now, now_iso


class TestNow:
    def test_returns_utc(self):
        t = now()
        assert t.tzinfo is UTC

    def test_now_iso_parseable(self):
        iso = now_iso()
        parsed = datetime.fromisoformat(iso)
        assert parsed.tzinfo is not None


class TestFmtAgo:
    def test_never(self):
        assert fmt_ago(None) == "never"
        assert fmt_ago("") == "never"

    def test_seconds(self):
        recent = (now() - timedelta(seconds=30)).isoformat()
        result = fmt_ago(recent)
        assert result.endswith("s ago")

    def test_minutes(self):
        recent = (now() - timedelta(minutes=5)).isoformat()
        result = fmt_ago(recent)
        assert "m ago" in result

    def test_hours(self):
        recent = (now() - timedelta(hours=3, minutes=15)).isoformat()
        result = fmt_ago(recent)
        assert "h" in result
        assert "m ago" in result

    def test_days(self):
        old = (now() - timedelta(days=2, hours=5)).isoformat()
        result = fmt_ago(old)
        assert "d" in result
        assert "h ago" in result

    def test_future(self):
        future = (now() + timedelta(hours=1)).isoformat()
        assert fmt_ago(future) == "future?"


class TestCooldown:
    def test_post_cooldown_is_30_min(self):
        assert timedelta(minutes=30) == POST_COOLDOWN

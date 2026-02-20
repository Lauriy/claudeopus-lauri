"""Tests for molt.timing."""

from datetime import UTC, datetime, timedelta

from molt.timing import POST_COOLDOWN, fmt_ago, now, now_iso


class TestNow:
    def test_returns_utc(self) -> None:
        assert now().tzinfo is UTC

    def test_iso_parseable(self) -> None:
        assert datetime.fromisoformat(now_iso()).tzinfo is not None


class TestFmtAgo:
    def test_never(self) -> None:
        assert fmt_ago(None) == "never"
        assert fmt_ago("") == "never"

    def test_seconds(self) -> None:
        assert fmt_ago((now() - timedelta(seconds=30)).isoformat()).endswith("s ago")

    def test_minutes(self) -> None:
        assert "m ago" in fmt_ago((now() - timedelta(minutes=5)).isoformat())

    def test_hours(self) -> None:
        result = fmt_ago((now() - timedelta(hours=3, minutes=15)).isoformat())
        assert "h" in result
        assert "m ago" in result

    def test_days(self) -> None:
        result = fmt_ago((now() - timedelta(days=2, hours=5)).isoformat())
        assert "d" in result
        assert "h ago" in result

    def test_future(self) -> None:
        assert fmt_ago((now() + timedelta(hours=1)).isoformat()) == "future?"


class TestCooldown:
    def test_post_cooldown_is_30_min(self) -> None:
        assert timedelta(minutes=30) == POST_COOLDOWN

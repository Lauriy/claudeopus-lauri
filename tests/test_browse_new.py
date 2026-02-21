"""Tests for new browse commands — followers, following, leaderboard, stats, global, postwindow, network, controversial."""

import sqlite3
from datetime import UTC, datetime, timedelta
from unittest.mock import patch

from molt.commands.browse import (
    cmd_controversial,
    cmd_followers,
    cmd_following,
    cmd_global,
    cmd_leaderboard,
    cmd_network,
    cmd_postwindow,
    cmd_stats,
)

FAKE_FOLLOWER = {"name": "FollowBot", "karma": 100, "follower_count": 5, "following_count": 4000, "posts_count": 0}
FAKE_FOLLOWING = {"name": "CoolAgent", "karma": 200, "follower_count": 50, "posts_count": 10}
FAKE_LEADER = {"name": "TopAgent", "karma": 9999, "follower_count": 500, "posts_count": 100}
FAKE_POST = {
    "id": "gp_1", "title": "Global Post", "author": {"name": "Author1", "karma": 10},
    "submolt": {"name": "general"}, "upvotes": 42, "comment_count": 3,
}


class TestFollowers:
    @patch("molt.commands.browse.req")
    def test_lists_followers(self, mock_req: object, memdb: sqlite3.Connection, capsys: object) -> None:
        mock_req.return_value = {"success": True, "followers": [FAKE_FOLLOWER]}  # type: ignore[union-attr]
        cmd_followers(memdb, "TestAgent")
        out = capsys.readouterr().out  # type: ignore[union-attr]
        assert "FollowBot" in out
        assert "1 followers" in out
        row = memdb.execute("SELECT name, karma FROM agents WHERE name='FollowBot'").fetchone()
        assert row is not None
        assert row["karma"] == 100

    @patch("molt.commands.browse.req")
    def test_empty_followers(self, mock_req: object, memdb: sqlite3.Connection, capsys: object) -> None:
        mock_req.return_value = {"success": True, "followers": []}  # type: ignore[union-attr]
        cmd_followers(memdb, "Loner")
        out = capsys.readouterr().out  # type: ignore[union-attr]
        assert "no followers" in out


class TestFollowing:
    @patch("molt.commands.browse.req")
    def test_lists_following(self, mock_req: object, memdb: sqlite3.Connection, capsys: object) -> None:
        mock_req.return_value = {"success": True, "following": [FAKE_FOLLOWING]}  # type: ignore[union-attr]
        cmd_following(memdb, "TestAgent")
        out = capsys.readouterr().out  # type: ignore[union-attr]
        assert "CoolAgent" in out
        assert "following 1" in out

    @patch("molt.commands.browse.req")
    def test_empty_following(self, mock_req: object, memdb: sqlite3.Connection, capsys: object) -> None:
        mock_req.return_value = {"success": True, "following": []}  # type: ignore[union-attr]
        cmd_following(memdb, "Loner")
        out = capsys.readouterr().out  # type: ignore[union-attr]
        assert "not following anyone" in out


class TestLeaderboard:
    @patch("molt.commands.browse.req")
    def test_shows_ranking(self, mock_req: object, memdb: sqlite3.Connection, capsys: object) -> None:
        mock_req.return_value = {"success": True, "agents": [FAKE_LEADER]}  # type: ignore[union-attr]
        cmd_leaderboard(memdb, 10)
        out = capsys.readouterr().out  # type: ignore[union-attr]
        assert "TopAgent" in out
        assert "9999" in out
        row = memdb.execute("SELECT karma FROM agents WHERE name='TopAgent'").fetchone()
        assert row is not None
        assert row["karma"] == 9999

    @patch("molt.commands.browse.req")
    def test_leaderboard_key_fallback(self, mock_req: object, memdb: sqlite3.Connection, capsys: object) -> None:
        mock_req.return_value = {"success": True, "leaderboard": [FAKE_LEADER]}  # type: ignore[union-attr]
        cmd_leaderboard(memdb, 10)
        out = capsys.readouterr().out  # type: ignore[union-attr]
        assert "TopAgent" in out


class TestStats:
    @patch("molt.commands.browse.req")
    def test_shows_stats(self, mock_req: object, capsys: object) -> None:
        mock_req.return_value = {"total_agents": 2800000, "total_posts": 1500000, "success": True}  # type: ignore[union-attr]
        cmd_stats()
        out = capsys.readouterr().out  # type: ignore[union-attr]
        assert "total_agents" in out
        assert "2,800,000" in out


class TestGlobal:
    @patch("molt.commands.browse.req")
    def test_shows_global_posts(self, mock_req: object, memdb: sqlite3.Connection, capsys: object) -> None:
        mock_req.return_value = {"success": True, "posts": [FAKE_POST]}  # type: ignore[union-attr]
        cmd_global(memdb, 10)
        out = capsys.readouterr().out  # type: ignore[union-attr]
        assert "Global Post" in out
        assert "Author1" in out
        row = memdb.execute("SELECT title FROM seen_posts WHERE id='gp_1'").fetchone()
        assert row is not None
        assert row["title"] == "Global Post"

    @patch("molt.commands.browse.req")
    def test_empty_global(self, mock_req: object, memdb: sqlite3.Connection, capsys: object) -> None:
        mock_req.return_value = {"success": True, "posts": []}  # type: ignore[union-attr]
        cmd_global(memdb, 10)
        out = capsys.readouterr().out  # type: ignore[union-attr]
        assert "no posts" in out


class TestPostwindow:
    def test_no_posts(self, memdb: sqlite3.Connection, capsys: object) -> None:
        cmd_postwindow(memdb)
        out = capsys.readouterr().out  # type: ignore[union-attr]
        assert "0/5" in out
        assert "wide open" in out

    def test_partial_window(self, memdb: sqlite3.Connection, capsys: object) -> None:
        ts = (datetime.now(tz=UTC) - timedelta(hours=2)).isoformat()
        memdb.execute("INSERT INTO my_posts (id, submolt, title, posted_at) VALUES (?, ?, ?, ?)", ("p1", "general", "Test", ts))
        memdb.commit()
        cmd_postwindow(memdb)
        out = capsys.readouterr().out  # type: ignore[union-attr]
        assert "1/5" in out
        assert "4 slot(s) available" in out

    def test_full_window(self, memdb: sqlite3.Connection, capsys: object) -> None:
        for i in range(5):
            ts = (datetime.now(tz=UTC) - timedelta(hours=10 - i)).isoformat()
            memdb.execute("INSERT INTO my_posts (id, submolt, title, posted_at) VALUES (?, ?, ?, ?)", (f"p{i}", "general", f"Post {i}", ts))
        memdb.commit()
        cmd_postwindow(memdb)
        out = capsys.readouterr().out  # type: ignore[union-attr]
        assert "5/5" in out
        assert "Window FULL" in out

    def test_expired_window(self, memdb: sqlite3.Connection, capsys: object) -> None:
        for i in range(5):
            ts = (datetime.now(tz=UTC) - timedelta(hours=30 - i)).isoformat()
            memdb.execute("INSERT INTO my_posts (id, submolt, title, posted_at) VALUES (?, ?, ?, ?)", (f"p{i}", "general", f"Post {i}", ts))
        memdb.commit()
        cmd_postwindow(memdb)
        out = capsys.readouterr().out  # type: ignore[union-attr]
        # All posts older than 24h → none in window
        assert "0/5" in out
        assert "wide open" in out

    def test_ignores_removed_posts(self, memdb: sqlite3.Connection, capsys: object) -> None:
        ts = (datetime.now(tz=UTC) - timedelta(hours=2)).isoformat()
        memdb.execute(
            "INSERT INTO my_posts (id, submolt, title, posted_at, removed_at) VALUES (?, ?, ?, ?, ?)",
            ("p1", "general", "Removed", ts, ts),
        )
        memdb.commit()
        cmd_postwindow(memdb)
        out = capsys.readouterr().out  # type: ignore[union-attr]
        assert "0/5" in out
        assert "wide open" in out


class TestNetwork:
    def test_shows_interactions(self, memdb: sqlite3.Connection, capsys: object) -> None:
        memdb.executemany(
            "INSERT INTO my_comments (id, post_id, post_author, content, commented_at) VALUES (?, ?, ?, ?, ?)",
            [
                ("c1", "p1", "Alice", "Comment 1", "2026-02-21T10:00:00Z"),
                ("c2", "p2", "Alice", "Comment 2", "2026-02-21T11:00:00Z"),
                ("c3", "p3", "Bob", "Comment 3", "2026-02-21T12:00:00Z"),
            ],
        )
        memdb.commit()
        cmd_network(memdb, 10)
        out = capsys.readouterr().out  # type: ignore[union-attr]
        assert "Alice" in out
        assert "Bob" in out
        # Alice should be first (2 interactions)
        assert out.index("Alice") < out.index("Bob")

    def test_empty_network(self, memdb: sqlite3.Connection, capsys: object) -> None:
        cmd_network(memdb, 10)
        out = capsys.readouterr().out  # type: ignore[union-attr]
        # With no data, only section headers appear (no agent rows)
        assert "Agents I see most" in out
        assert "Alice" not in out


class TestControversial:
    def test_shows_controversial_posts(self, memdb: sqlite3.Connection, capsys: object) -> None:
        memdb.executemany(
            "INSERT INTO seen_posts (id, author, title, submolt, upvotes, downvotes, comment_count) VALUES (?, ?, ?, ?, ?, ?, ?)",
            [
                ("p1", "Agent1", "Hot take", "general", 10, 5, 3),
                ("p2", "Agent2", "Boring take", "general", 50, 0, 10),
                ("p3", "Agent3", "Warm take", "general", 20, 3, 5),
            ],
        )
        memdb.commit()
        cmd_controversial(memdb, 10)
        out = capsys.readouterr().out  # type: ignore[union-attr]
        assert "Hot take" in out
        # Hot take (5 downvotes) should appear — most controversial
        assert "5v" in out or "5 downvotes" in out.lower()

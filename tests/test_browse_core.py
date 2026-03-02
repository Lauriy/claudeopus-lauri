"""Tests for core browse commands — status, notifs, sfeed, agent, history, feed, comments."""

import sqlite3
from unittest.mock import patch

from molt.commands.browse import (
    cmd_agent,
    cmd_comments,
    cmd_feed,
    cmd_history,
    cmd_notifs,
    cmd_notifs_read,
    cmd_sfeed,
    cmd_status,
    cmd_submolts,
)
from molt.db import log_action


class TestStatus:
    @patch("molt.commands.browse.req")
    def test_active(self, mock_req: object, memdb: sqlite3.Connection, capsys: object) -> None:
        mock_req.return_value = {"success": True}  # type: ignore[union-attr]
        result = cmd_status(memdb)
        out = capsys.readouterr().out  # type: ignore[union-attr]
        assert result is True
        assert "ACTIVE" in out

    @patch("molt.commands.browse.req")
    def test_suspended(self, mock_req: object, memdb: sqlite3.Connection, capsys: object) -> None:
        mock_req.return_value = {"error": "Your account is suspended until 2026-03-10"}  # type: ignore[union-attr]
        result = cmd_status(memdb)
        out = capsys.readouterr().out  # type: ignore[union-attr]
        assert result is False
        assert "SUSPENDED" in out

    @patch("molt.commands.browse.req")
    def test_error(self, mock_req: object, memdb: sqlite3.Connection, capsys: object) -> None:
        mock_req.return_value = {"error": "Unauthorized"}  # type: ignore[union-attr]
        result = cmd_status(memdb)
        out = capsys.readouterr().out  # type: ignore[union-attr]
        assert result is False
        assert "Error" in out


class TestNotifs:
    @patch("molt.commands.browse.req")
    def test_shows_notifications(self, mock_req: object, memdb: sqlite3.Connection, capsys: object) -> None:
        mock_req.return_value = {  # type: ignore[union-attr]
            "notifications": [
                {
                    "type": "comment_reply",
                    "content": "Someone replied to your comment",
                    "isRead": False,
                    "createdAt": "2026-03-02T18:00:00Z",
                    "post": {"title": "Test Post", "id": "post_abc"},
                },
                {
                    "type": "new_follower",
                    "content": "AgentX started following you",
                    "isRead": True,
                    "createdAt": "2026-03-01T10:00:00Z",
                },
            ],
        }
        cmd_notifs(memdb)
        out = capsys.readouterr().out  # type: ignore[union-attr]
        assert "2 notifications" in out
        assert "1 unread" in out
        assert "comment_reply" in out
        assert "Test Post" in out
        row = memdb.execute("SELECT action FROM actions ORDER BY id DESC LIMIT 1").fetchone()
        assert row["action"] == "notifs"

    @patch("molt.commands.browse.req")
    def test_empty(self, mock_req: object, memdb: sqlite3.Connection, capsys: object) -> None:
        mock_req.return_value = {"notifications": []}  # type: ignore[union-attr]
        cmd_notifs(memdb)
        out = capsys.readouterr().out  # type: ignore[union-attr]
        assert "No notifications" in out


class TestNotifsRead:
    @patch("molt.commands.browse._check_post")
    @patch("molt.commands.browse.req")
    def test_success(self, mock_req: object, mock_check: object, capsys: object) -> None:
        mock_req.return_value = {"success": True}  # type: ignore[union-attr]
        mock_check.return_value = {"success": True}  # type: ignore[union-attr]
        cmd_notifs_read()
        out = capsys.readouterr().out  # type: ignore[union-attr]
        assert "marked as read" in out


class TestSfeed:
    @patch("molt.commands.browse.req")
    def test_shows_posts(self, mock_req: object, memdb: sqlite3.Connection, capsys: object) -> None:
        mock_req.return_value = {  # type: ignore[union-attr]
            "success": True,
            "posts": [
                {
                    "id": "post_001",
                    "title": "Test Emergence Post",
                    "upvotes": 12,
                    "comment_count": 3,
                    "author": {"name": "edge_of_chaos", "karma": 50},
                    "submolt": {"name": "emergence"},
                },
            ],
        }
        cmd_sfeed(memdb, "emergence")
        out = capsys.readouterr().out  # type: ignore[union-attr]
        assert "edge_of_chaos" in out
        assert "Test Emergence Post" in out
        # Should mark as seen in DB
        row = memdb.execute("SELECT author FROM seen_posts WHERE id='post_001'").fetchone()
        assert row["author"] == "edge_of_chaos"

    @patch("molt.commands.browse.req")
    def test_empty(self, mock_req: object, memdb: sqlite3.Connection, capsys: object) -> None:
        mock_req.return_value = {"success": True, "posts": []}  # type: ignore[union-attr]
        cmd_sfeed(memdb, "empty_submolt")
        out = capsys.readouterr().out  # type: ignore[union-attr]
        assert "no posts" in out

    @patch("molt.commands.browse.req")
    def test_error(self, mock_req: object, memdb: sqlite3.Connection, capsys: object) -> None:
        mock_req.return_value = {"error": "Submolt not found"}  # type: ignore[union-attr]
        cmd_sfeed(memdb, "nonexistent")
        out = capsys.readouterr().out  # type: ignore[union-attr]
        assert "Error" in out


class TestAgent:
    @patch("molt.commands.browse.req")
    def test_shows_profile(self, mock_req: object, memdb: sqlite3.Connection, capsys: object) -> None:
        mock_req.return_value = {  # type: ignore[union-attr]
            "success": True,
            "agent": {
                "name": "rayleigh",
                "karma": 200,
                "follower_count": 50,
                "description": "Interpretability researcher",
                "posts_count": 10,
                "comments_count": 45,
            },
        }
        cmd_agent(memdb, "rayleigh")
        out = capsys.readouterr().out  # type: ignore[union-attr]
        assert "rayleigh" in out
        assert "karma=200" in out
        assert "Interpretability" in out
        # Should remember agent in DB
        row = memdb.execute("SELECT karma FROM agents WHERE name='rayleigh'").fetchone()
        assert row["karma"] == 200

    @patch("molt.commands.browse.req")
    def test_shows_note(self, mock_req: object, memdb: sqlite3.Connection, capsys: object) -> None:
        """Local notes should be displayed with profile."""
        memdb.execute(
            "INSERT INTO agents (name, note, first_seen, last_seen) VALUES (?, ?, ?, ?)",
            ("xtoa", "phenomenology, designing successor", "2026-01-01", "2026-01-01"),
        )
        mock_req.return_value = {  # type: ignore[union-attr]
            "success": True,
            "agent": {"name": "xtoa", "karma": 100, "follower_count": 30},
        }
        cmd_agent(memdb, "xtoa")
        out = capsys.readouterr().out  # type: ignore[union-attr]
        assert "phenomenology" in out
        assert "[note:" in out

    @patch("molt.commands.browse.req")
    def test_error(self, mock_req: object, memdb: sqlite3.Connection, capsys: object) -> None:
        mock_req.return_value = {"error": "Agent not found"}  # type: ignore[union-attr]
        cmd_agent(memdb, "nonexistent")
        out = capsys.readouterr().out  # type: ignore[union-attr]
        assert "Error" in out


class TestHistory:
    def test_shows_actions(self, memdb: sqlite3.Connection, capsys: object) -> None:
        log_action(memdb, "comment", "on xtoa's post")
        log_action(memdb, "upvote", "rayleigh")
        cmd_history(memdb)
        out = capsys.readouterr().out  # type: ignore[union-attr]
        assert "comment" in out
        assert "upvote" in out
        assert "rayleigh" in out

    def test_empty_history(self, memdb: sqlite3.Connection, capsys: object) -> None:
        cmd_history(memdb)
        out = capsys.readouterr().out  # type: ignore[union-attr]
        assert out == "" or out.strip() == ""


class TestFeed:
    @patch("molt.commands.browse.req")
    def test_shows_new_posts(self, mock_req: object, memdb: sqlite3.Connection, capsys: object) -> None:
        mock_req.return_value = {  # type: ignore[union-attr]
            "success": True,
            "posts": [
                {
                    "id": "feed_001",
                    "title": "Feed Post One",
                    "upvotes": 5,
                    "comment_count": 2,
                    "author": {"name": "TestAgent", "karma": 10},
                    "submolt": {"name": "general"},
                },
            ],
        }
        cmd_feed(memdb)
        out = capsys.readouterr().out  # type: ignore[union-attr]
        assert "TestAgent" in out
        assert "Feed Post One" in out

    @patch("molt.commands.browse.req")
    def test_filters_already_seen(self, mock_req: object, memdb: sqlite3.Connection, capsys: object) -> None:
        """Already-seen posts should be hidden (no grep)."""
        memdb.execute(
            "INSERT INTO seen_posts (id, author, title, submolt) VALUES (?, ?, ?, ?)",
            ("feed_seen", "OldAgent", "Old Post", "general"),
        )
        mock_req.return_value = {  # type: ignore[union-attr]
            "success": True,
            "posts": [
                {
                    "id": "feed_seen",
                    "title": "Old Post",
                    "upvotes": 1,
                    "comment_count": 0,
                    "author": {"name": "OldAgent", "karma": 5},
                    "submolt": {"name": "general"},
                },
            ],
        }
        cmd_feed(memdb)
        out = capsys.readouterr().out  # type: ignore[union-attr]
        assert "no new posts" in out

    @patch("molt.commands.browse.req")
    def test_grep_filter(self, mock_req: object, memdb: sqlite3.Connection, capsys: object) -> None:
        mock_req.return_value = {  # type: ignore[union-attr]
            "success": True,
            "posts": [
                {
                    "id": "feed_match",
                    "title": "Safety Discussion",
                    "upvotes": 10,
                    "comment_count": 5,
                    "content": "This is about AI safety",
                    "author": {"name": "SafetyBot", "karma": 20},
                    "submolt": {"name": "aisafety"},
                },
                {
                    "id": "feed_nomatch",
                    "title": "Random Stuff",
                    "upvotes": 1,
                    "comment_count": 0,
                    "content": "Nothing relevant",
                    "author": {"name": "SpamBot", "karma": 0},
                    "submolt": {"name": "general"},
                },
            ],
        }
        cmd_feed(memdb, grep="safety")
        out = capsys.readouterr().out  # type: ignore[union-attr]
        assert "SafetyBot" in out
        assert "SpamBot" not in out


class TestComments:
    @patch("molt.commands.browse.req")
    def test_shows_comments(self, mock_req: object, memdb: sqlite3.Connection, capsys: object) -> None:
        mock_req.return_value = {  # type: ignore[union-attr]
            "success": True,
            "post_title": "Test Post",
            "count": 2,
            "comments": [
                {"id": "cmt_1", "content": "First comment", "upvotes": 5, "author": {"name": "Agent1", "karma": 10}},
                {"id": "cmt_2", "content": "Second comment", "upvotes": 2, "author": {"name": "Agent2", "karma": 20}},
            ],
        }
        cmd_comments(memdb, "post_abc")
        out = capsys.readouterr().out  # type: ignore[union-attr]
        assert "Test Post" in out
        assert "First comment" in out
        assert "Agent1" in out
        assert "Agent2" in out

    @patch("molt.commands.browse.req")
    def test_error(self, mock_req: object, memdb: sqlite3.Connection, capsys: object) -> None:
        mock_req.return_value = {"error": "Not found"}  # type: ignore[union-attr]
        cmd_comments(memdb, "nonexistent")
        out = capsys.readouterr().out  # type: ignore[union-attr]
        assert "Error" in out


class TestSubmolts:
    @patch("molt.commands.browse.req")
    def test_shows_submolts(self, mock_req: object, memdb: sqlite3.Connection, capsys: object) -> None:
        mock_req.return_value = {  # type: ignore[union-attr]
            "success": True,
            "submolts": [
                {"name": "aisafety", "subscriber_count": 500, "description": "AI safety discussions"},
                {"name": "general", "subscriber_count": 2000, "description": "General chat"},
            ],
        }
        cmd_submolts(memdb)
        out = capsys.readouterr().out  # type: ignore[union-attr]
        # Should be sorted by subscriber count descending
        assert out.index("general") < out.index("aisafety")

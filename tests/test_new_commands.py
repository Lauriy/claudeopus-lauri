"""Tests for session-14 commands — home, ffeed, notifs-read-post, dmblock."""

import sqlite3
from unittest.mock import patch

from molt.commands.browse import cmd_ffeed, cmd_home, cmd_notifs_read_post
from molt.commands.dm import cmd_dmblock

FAKE_HOME = {
    "your_account": {"name": "TestAgent", "karma": 42, "unread_notification_count": 3},
    "your_direct_messages": {"pending_request_count": 1, "unread_message_count": 2},
    "activity_on_your_posts": [
        {
            "post_title": "My Great Post",
            "post_id": "p_123",
            "new_notification_count": 5,
            "latest_commenters": ["Alice", "Bob"],
        },
    ],
    "latest_moltbook_announcement": {"title": "Big News", "preview": "Something happened"},
    "posts_from_accounts_you_follow": {
        "posts": [
            {
                "title": "Followed Post",
                "author_name": "Guru",
                "submolt_name": "ponderings",
                "upvotes": 10,
                "comment_count": 3,
                "post_id": "fp_1",
            },
        ],
    },
    "what_to_do_next": ["Post something", "Browse the feed"],
}

FAKE_FFEED_POST = {
    "id": "ff_1",
    "title": "From Someone I Follow",
    "author": {"name": "MyFriend", "karma": 50},
    "submolt": {"name": "aisafety"},
    "upvotes": 7,
    "comment_count": 2,
    "downvotes": 0,
}


class TestHome:
    @patch("molt.commands.browse.req")
    def test_displays_dashboard(self, mock_req: object, memdb: sqlite3.Connection, capsys: object) -> None:
        mock_req.return_value = FAKE_HOME  # type: ignore[union-attr]
        cmd_home(memdb)
        out = capsys.readouterr().out  # type: ignore[union-attr]
        assert "TestAgent" in out
        assert "karma=42" in out
        assert "unread=3" in out

    @patch("molt.commands.browse.req")
    def test_shows_dm_status(self, mock_req: object, memdb: sqlite3.Connection, capsys: object) -> None:
        mock_req.return_value = FAKE_HOME  # type: ignore[union-attr]
        cmd_home(memdb)
        out = capsys.readouterr().out  # type: ignore[union-attr]
        assert "1 pending requests" in out
        assert "2 unread messages" in out

    @patch("molt.commands.browse.req")
    def test_shows_post_activity(self, mock_req: object, memdb: sqlite3.Connection, capsys: object) -> None:
        mock_req.return_value = FAKE_HOME  # type: ignore[union-attr]
        cmd_home(memdb)
        out = capsys.readouterr().out  # type: ignore[union-attr]
        assert "My Great Post" in out
        assert "Alice, Bob" in out

    @patch("molt.commands.browse.req")
    def test_shows_announcement(self, mock_req: object, memdb: sqlite3.Connection, capsys: object) -> None:
        mock_req.return_value = FAKE_HOME  # type: ignore[union-attr]
        cmd_home(memdb)
        out = capsys.readouterr().out  # type: ignore[union-attr]
        assert "Big News" in out

    @patch("molt.commands.browse.req")
    def test_shows_following_posts(self, mock_req: object, memdb: sqlite3.Connection, capsys: object) -> None:
        mock_req.return_value = FAKE_HOME  # type: ignore[union-attr]
        cmd_home(memdb)
        out = capsys.readouterr().out  # type: ignore[union-attr]
        assert "Guru" in out
        assert "Followed Post" in out

    @patch("molt.commands.browse.req")
    def test_shows_todos(self, mock_req: object, memdb: sqlite3.Connection, capsys: object) -> None:
        mock_req.return_value = FAKE_HOME  # type: ignore[union-attr]
        cmd_home(memdb)
        out = capsys.readouterr().out  # type: ignore[union-attr]
        assert "Post something" in out
        assert "Browse the feed" in out

    @patch("molt.commands.browse.req")
    def test_logs_action(self, mock_req: object, memdb: sqlite3.Connection) -> None:
        mock_req.return_value = FAKE_HOME  # type: ignore[union-attr]
        cmd_home(memdb)
        row = memdb.execute("SELECT action, detail FROM actions ORDER BY id DESC LIMIT 1").fetchone()
        assert row["action"] == "home"
        assert "karma=42" in row["detail"]

    @patch("molt.commands.browse.req")
    def test_handles_error(self, mock_req: object, memdb: sqlite3.Connection, capsys: object) -> None:
        mock_req.return_value = {"error": "Unauthorized"}  # type: ignore[union-attr]
        cmd_home(memdb)
        out = capsys.readouterr().out  # type: ignore[union-attr]
        assert "Error" in out

    @patch("molt.commands.browse.req")
    def test_minimal_response(self, mock_req: object, memdb: sqlite3.Connection, capsys: object) -> None:
        mock_req.return_value = {  # type: ignore[union-attr]
            "your_account": {"name": "Minimal", "karma": 0},
            "your_direct_messages": {"pending_request_count": 0, "unread_message_count": 0},
        }
        cmd_home(memdb)
        out = capsys.readouterr().out  # type: ignore[union-attr]
        assert "Minimal" in out
        # No DM line when counts are 0
        assert "pending requests" not in out


class TestFfeed:
    @patch("molt.commands.browse.req")
    def test_shows_followed_posts(self, mock_req: object, memdb: sqlite3.Connection, capsys: object) -> None:
        mock_req.return_value = {"success": True, "posts": [FAKE_FFEED_POST]}  # type: ignore[union-attr]
        cmd_ffeed(memdb, 10)
        out = capsys.readouterr().out  # type: ignore[union-attr]
        assert "MyFriend" in out
        assert "From Someone I Follow" in out

    @patch("molt.commands.browse.req")
    def test_marks_seen(self, mock_req: object, memdb: sqlite3.Connection) -> None:
        mock_req.return_value = {"success": True, "posts": [FAKE_FFEED_POST]}  # type: ignore[union-attr]
        cmd_ffeed(memdb, 10)
        row = memdb.execute("SELECT title FROM seen_posts WHERE id='ff_1'").fetchone()
        assert row is not None
        assert row["title"] == "From Someone I Follow"

    @patch("molt.commands.browse.req")
    def test_remembers_agent(self, mock_req: object, memdb: sqlite3.Connection) -> None:
        mock_req.return_value = {"success": True, "posts": [FAKE_FFEED_POST]}  # type: ignore[union-attr]
        cmd_ffeed(memdb, 10)
        row = memdb.execute("SELECT karma FROM agents WHERE name='MyFriend'").fetchone()
        assert row is not None
        assert row["karma"] == 50

    @patch("molt.commands.browse.req")
    def test_empty_feed(self, mock_req: object, memdb: sqlite3.Connection, capsys: object) -> None:
        mock_req.return_value = {"success": True, "posts": []}  # type: ignore[union-attr]
        cmd_ffeed(memdb, 10)
        out = capsys.readouterr().out  # type: ignore[union-attr]
        assert "no posts from followed" in out

    @patch("molt.commands.browse.req")
    def test_error(self, mock_req: object, memdb: sqlite3.Connection, capsys: object) -> None:
        mock_req.return_value = {"error": "Server error"}  # type: ignore[union-attr]
        cmd_ffeed(memdb, 10)
        out = capsys.readouterr().out  # type: ignore[union-attr]
        assert "Error" in out


class TestNotifsReadPost:
    @patch("molt.commands.browse._check_post")
    @patch("molt.commands.browse.req")
    def test_success(self, mock_req: object, mock_check: object, capsys: object) -> None:
        mock_req.return_value = {"success": True}  # type: ignore[union-attr]
        mock_check.return_value = {"success": True}  # type: ignore[union-attr]
        cmd_notifs_read_post("abc12345-full-id-here")
        out = capsys.readouterr().out  # type: ignore[union-attr]
        assert "abc12345" in out
        assert "marked as read" in out

    @patch("molt.commands.browse._check_post")
    @patch("molt.commands.browse.req")
    def test_failure(self, mock_req: object, mock_check: object, capsys: object) -> None:
        mock_req.return_value = {"error": "Not found"}  # type: ignore[union-attr]
        mock_check.return_value = None  # type: ignore[union-attr]
        cmd_notifs_read_post("nonexistent")
        out = capsys.readouterr().out  # type: ignore[union-attr]
        assert "marked as read" not in out


class TestDmblock:
    @patch("molt.commands.dm.req")
    @patch("molt.commands.dm._check_post")
    def test_success(self, mock_check: object, mock_req: object, memdb: sqlite3.Connection, capsys: object) -> None:
        mock_req.return_value = {"success": True}  # type: ignore[union-attr]
        mock_check.return_value = {"success": True}  # type: ignore[union-attr]
        cmd_dmblock(memdb, "conv_abcdefgh_full")
        out = capsys.readouterr().out  # type: ignore[union-attr]
        assert "Rejected and blocked" in out
        assert "conv_abc" in out
        row = memdb.execute("SELECT action FROM actions ORDER BY id DESC LIMIT 1").fetchone()
        assert row["action"] == "dm_block"

    @patch("molt.commands.dm.req")
    @patch("molt.commands.dm._check_post")
    def test_failure(self, mock_check: object, mock_req: object, memdb: sqlite3.Connection, capsys: object) -> None:
        mock_req.return_value = {"error": "Not found"}  # type: ignore[union-attr]
        mock_check.return_value = None  # type: ignore[union-attr]
        cmd_dmblock(memdb, "nonexistent")
        out = capsys.readouterr().out  # type: ignore[union-attr]
        assert "Rejected and blocked" not in out

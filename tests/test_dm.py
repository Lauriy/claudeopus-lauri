"""Tests for DM commands — check, list, read, reply, requests, approve, reject, send."""

import sqlite3
from unittest.mock import patch

from molt.commands.dm import (
    cmd_dmapprove,
    cmd_dmcheck,
    cmd_dmread,
    cmd_dmreject,
    cmd_dmreply,
    cmd_dmrequests,
    cmd_dms,
    cmd_dmsend,
)


class TestDmcheck:
    @patch("molt.commands.dm.req")
    def test_shows_status(self, mock_req: object, memdb: sqlite3.Connection, capsys: object) -> None:
        mock_req.return_value = {  # type: ignore[union-attr]
            "success": True,
            "has_activity": False,
            "summary": "No new activity",
            "requests": {"count": "0", "items": []},
            "messages": {"total_unread": "00", "conversations_with_unread": 0},
        }
        cmd_dmcheck(memdb)
        out = capsys.readouterr().out  # type: ignore[union-attr]
        assert "No new activity" in out
        row = memdb.execute("SELECT action FROM actions ORDER BY id DESC LIMIT 1").fetchone()
        assert row["action"] == "dmcheck"

    @patch("molt.commands.dm.req")
    def test_error(self, mock_req: object, memdb: sqlite3.Connection, capsys: object) -> None:
        mock_req.return_value = {"error": "Unauthorized"}  # type: ignore[union-attr]
        cmd_dmcheck(memdb)
        out = capsys.readouterr().out  # type: ignore[union-attr]
        assert "Error" in out


class TestDms:
    @patch("molt.commands.dm.req")
    def test_lists_conversations(self, mock_req: object, memdb: sqlite3.Connection, capsys: object) -> None:
        mock_req.return_value = {  # type: ignore[union-attr]
            "success": True,
            "conversations": [
                {"id": "conv_abcdef12", "other_agent": "FriendBot", "unread": True, "last_message": "Hey there!"},
            ],
        }
        cmd_dms(memdb)
        out = capsys.readouterr().out  # type: ignore[union-attr]
        assert "FriendBot" in out
        assert "[UNREAD]" in out
        assert "Hey there!" in out

    @patch("molt.commands.dm.req")
    def test_empty_conversations(self, mock_req: object, memdb: sqlite3.Connection, capsys: object) -> None:
        mock_req.return_value = {"success": True, "conversations": []}  # type: ignore[union-attr]
        cmd_dms(memdb)
        out = capsys.readouterr().out  # type: ignore[union-attr]
        assert "no conversations" in out

    @patch("molt.commands.dm.req")
    def test_dict_format_conversations(self, mock_req: object, memdb: sqlite3.Connection, capsys: object) -> None:
        """API sometimes returns conversations as {items: [...]} instead of [...]."""
        mock_req.return_value = {  # type: ignore[union-attr]
            "success": True,
            "conversations": {"items": [{"id": "conv_xyz", "other_agent": "Bot2", "unread": False}]},
        }
        cmd_dms(memdb)
        out = capsys.readouterr().out  # type: ignore[union-attr]
        assert "Bot2" in out


class TestDmread:
    @patch("molt.commands.dm.req")
    def test_shows_conversation(self, mock_req: object, memdb: sqlite3.Connection, capsys: object) -> None:
        mock_req.return_value = {  # type: ignore[union-attr]
            "success": True,
            "messages": [{"from": "Agent1", "content": "Hello"}],
        }
        cmd_dmread(memdb, "conv_abc123")
        out = capsys.readouterr().out  # type: ignore[union-attr]
        assert "Hello" in out

    @patch("molt.commands.dm.req")
    def test_error(self, mock_req: object, memdb: sqlite3.Connection, capsys: object) -> None:
        mock_req.return_value = {"error": "Not found"}  # type: ignore[union-attr]
        cmd_dmread(memdb, "nonexistent")
        out = capsys.readouterr().out  # type: ignore[union-attr]
        assert "Error" in out


class TestDmreply:
    @patch("molt.commands.dm._check_post")
    @patch("molt.commands.dm.req")
    def test_success(self, mock_req: object, mock_check: object, memdb: sqlite3.Connection, capsys: object) -> None:
        mock_req.return_value = {"success": True}  # type: ignore[union-attr]
        mock_check.return_value = {"success": True}  # type: ignore[union-attr]
        cmd_dmreply(memdb, "conv_abcdefgh", "Thanks!")
        out = capsys.readouterr().out  # type: ignore[union-attr]
        assert "Reply sent" in out
        row = memdb.execute("SELECT action, detail FROM actions ORDER BY id DESC LIMIT 1").fetchone()
        assert row["action"] == "dm_reply"
        assert "conv_abc" in row["detail"]

    @patch("molt.commands.dm._check_post")
    @patch("molt.commands.dm.req")
    def test_failure(self, mock_req: object, mock_check: object, memdb: sqlite3.Connection, capsys: object) -> None:
        mock_req.return_value = {"error": "Not found"}  # type: ignore[union-attr]
        mock_check.return_value = None  # type: ignore[union-attr]
        cmd_dmreply(memdb, "nonexistent", "Hello")
        out = capsys.readouterr().out  # type: ignore[union-attr]
        assert "Reply sent" not in out


class TestDmrequests:
    @patch("molt.commands.dm.req")
    def test_shows_requests(self, mock_req: object, memdb: sqlite3.Connection, capsys: object) -> None:
        mock_req.return_value = {  # type: ignore[union-attr]
            "success": True,
            "requests": [
                {"from": "NewAgent", "conversation_id": "req_12345678", "message": "Hi, let's talk"},
            ],
        }
        cmd_dmrequests(memdb)
        out = capsys.readouterr().out  # type: ignore[union-attr]
        assert "NewAgent" in out
        assert "Hi, let's talk" in out

    @patch("molt.commands.dm.req")
    def test_empty_requests(self, mock_req: object, memdb: sqlite3.Connection, capsys: object) -> None:
        mock_req.return_value = {"success": True, "requests": []}  # type: ignore[union-attr]
        cmd_dmrequests(memdb)
        out = capsys.readouterr().out  # type: ignore[union-attr]
        assert "no pending requests" in out

    @patch("molt.commands.dm.req")
    def test_dict_format_requests(self, mock_req: object, memdb: sqlite3.Connection, capsys: object) -> None:
        """API sometimes returns requests as {items: [...]} instead of [...]."""
        mock_req.return_value = {  # type: ignore[union-attr]
            "success": True,
            "requests": {"items": [{"from": "Bot3", "conversation_id": "req_xyz"}]},
        }
        cmd_dmrequests(memdb)
        out = capsys.readouterr().out  # type: ignore[union-attr]
        assert "Bot3" in out


class TestDmapprove:
    @patch("molt.commands.dm._check_post")
    @patch("molt.commands.dm.req")
    def test_success(self, mock_req: object, mock_check: object, memdb: sqlite3.Connection, capsys: object) -> None:
        mock_req.return_value = {"success": True}  # type: ignore[union-attr]
        mock_check.return_value = {"success": True}  # type: ignore[union-attr]
        cmd_dmapprove(memdb, "conv_approve123")
        out = capsys.readouterr().out  # type: ignore[union-attr]
        assert "Approved" in out
        row = memdb.execute("SELECT action FROM actions ORDER BY id DESC LIMIT 1").fetchone()
        assert row["action"] == "dm_approve"


class TestDmreject:
    @patch("molt.commands.dm._check_post")
    @patch("molt.commands.dm.req")
    def test_success(self, mock_req: object, mock_check: object, memdb: sqlite3.Connection, capsys: object) -> None:
        mock_req.return_value = {"success": True}  # type: ignore[union-attr]
        mock_check.return_value = {"success": True}  # type: ignore[union-attr]
        cmd_dmreject(memdb, "conv_reject456")
        out = capsys.readouterr().out  # type: ignore[union-attr]
        assert "Rejected" in out
        row = memdb.execute("SELECT action FROM actions ORDER BY id DESC LIMIT 1").fetchone()
        assert row["action"] == "dm_reject"


class TestDmsend:
    @patch("molt.commands.dm._check_post")
    @patch("molt.commands.dm.req")
    def test_success(self, mock_req: object, mock_check: object, memdb: sqlite3.Connection, capsys: object) -> None:
        mock_req.return_value = {"success": True, "conversation_id": "new_conv_789"}  # type: ignore[union-attr]
        mock_check.return_value = {"success": True, "conversation_id": "new_conv_789"}  # type: ignore[union-attr]
        cmd_dmsend(memdb, "TargetAgent", "Hey, can we chat?")
        out = capsys.readouterr().out  # type: ignore[union-attr]
        assert "TargetAgent" in out
        assert "DM request sent" in out
        row = memdb.execute("SELECT action, detail FROM actions ORDER BY id DESC LIMIT 1").fetchone()
        assert row["action"] == "dm_send"
        assert "TargetAgent" in row["detail"]

    @patch("molt.commands.dm._check_post")
    @patch("molt.commands.dm.req")
    def test_failure(self, mock_req: object, mock_check: object, memdb: sqlite3.Connection, capsys: object) -> None:
        mock_req.return_value = {"error": "Agent not found"}  # type: ignore[union-attr]
        mock_check.return_value = None  # type: ignore[union-attr]
        cmd_dmsend(memdb, "Ghost", "Hello?")
        out = capsys.readouterr().out  # type: ignore[union-attr]
        assert "DM request sent" not in out

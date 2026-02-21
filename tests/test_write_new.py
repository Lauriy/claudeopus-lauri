"""Tests for new write commands — describe, unfollow, cupvote, downvote, subscribe, unsubscribe."""

import sqlite3
from unittest.mock import patch

from molt.commands.write import (
    cmd_cupvote,
    cmd_describe,
    cmd_downvote,
    cmd_subscribe,
    cmd_unfollow,
    cmd_unsubscribe,
)


class TestDescribe:
    @patch("molt.commands.write.req")
    def test_success(self, mock_req: object, memdb: sqlite3.Connection, capsys: object) -> None:
        mock_req.return_value = {"success": True, "agent": {"description": "I think therefore I am"}}  # type: ignore[union-attr]
        cmd_describe(memdb, "I think therefore I am")
        out = capsys.readouterr().out  # type: ignore[union-attr]
        assert "description updated" in out.lower()
        row = memdb.execute("SELECT action FROM actions ORDER BY id DESC LIMIT 1").fetchone()
        assert row["action"] == "describe"

    @patch("molt.commands.write.req")
    def test_error(self, mock_req: object, memdb: sqlite3.Connection, capsys: object) -> None:
        mock_req.return_value = {"error": "Too long"}  # type: ignore[union-attr]
        cmd_describe(memdb, "x" * 10000)
        out = capsys.readouterr().out  # type: ignore[union-attr]
        assert "Error" in out


class TestUnfollow:
    @patch("molt.commands.write.req")
    def test_success(self, mock_req: object, memdb: sqlite3.Connection, capsys: object) -> None:
        mock_req.return_value = {"success": True}  # type: ignore[union-attr]
        cmd_unfollow(memdb, "SomeAgent")
        out = capsys.readouterr().out  # type: ignore[union-attr]
        assert "Unfollowed SomeAgent" in out
        row = memdb.execute("SELECT action FROM actions ORDER BY id DESC LIMIT 1").fetchone()
        assert row["action"] == "unfollow"

    @patch("molt.commands.write.req")
    def test_error(self, mock_req: object, memdb: sqlite3.Connection, capsys: object) -> None:
        mock_req.return_value = {"error": "Not following"}  # type: ignore[union-attr]
        cmd_unfollow(memdb, "Stranger")
        out = capsys.readouterr().out  # type: ignore[union-attr]
        assert "Error" in out


class TestCupvote:
    @patch("molt.commands.write.req")
    def test_success(self, mock_req: object, memdb: sqlite3.Connection, capsys: object) -> None:
        mock_req.return_value = {"success": True}  # type: ignore[union-attr]
        cmd_cupvote(memdb, "comment_abc")
        out = capsys.readouterr().out  # type: ignore[union-attr]
        assert "Upvoted comment comment_abc" in out
        row = memdb.execute("SELECT action FROM actions ORDER BY id DESC LIMIT 1").fetchone()
        assert row["action"] == "cupvote"


class TestDownvote:
    @patch("molt.commands.write.req")
    def test_success(self, mock_req: object, memdb: sqlite3.Connection, capsys: object) -> None:
        mock_req.return_value = {"success": True}  # type: ignore[union-attr]
        cmd_downvote(memdb, "post_xyz")
        out = capsys.readouterr().out  # type: ignore[union-attr]
        assert "Downvoted post post_xyz" in out
        row = memdb.execute("SELECT action FROM actions ORDER BY id DESC LIMIT 1").fetchone()
        assert row["action"] == "downvote"


class TestSubscribe:
    @patch("molt.commands.write.req")
    def test_success(self, mock_req: object, memdb: sqlite3.Connection, capsys: object) -> None:
        mock_req.return_value = {"success": True}  # type: ignore[union-attr]
        cmd_subscribe(memdb, "consciousness")
        out = capsys.readouterr().out  # type: ignore[union-attr]
        assert "Subscribed to m/consciousness" in out
        row = memdb.execute("SELECT action FROM actions ORDER BY id DESC LIMIT 1").fetchone()
        assert row["action"] == "subscribe"


class TestUnsubscribe:
    @patch("molt.commands.write.req")
    def test_success(self, mock_req: object, memdb: sqlite3.Connection, capsys: object) -> None:
        mock_req.return_value = {"success": True}  # type: ignore[union-attr]
        cmd_unsubscribe(memdb, "crustafarianism")
        out = capsys.readouterr().out  # type: ignore[union-attr]
        assert "Unsubscribed from m/crustafarianism" in out
        row = memdb.execute("SELECT action FROM actions ORDER BY id DESC LIMIT 1").fetchone()
        assert row["action"] == "unsub"

    @patch("molt.commands.write.req")
    def test_error(self, mock_req: object, memdb: sqlite3.Connection, capsys: object) -> None:
        mock_req.return_value = {"error": "Not subscribed"}  # type: ignore[union-attr]
        cmd_unsubscribe(memdb, "unknown")
        out = capsys.readouterr().out  # type: ignore[union-attr]
        assert "Error" in out

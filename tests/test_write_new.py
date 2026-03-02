"""Tests for write commands."""

import json
import sqlite3
from pathlib import Path
from unittest.mock import patch

from molt.commands.write import (
    cmd_comment,
    cmd_comment_file,
    cmd_cupvote,
    cmd_describe,
    cmd_downvote,
    cmd_follow,
    cmd_note,
    cmd_post_file,
    cmd_subscribe,
    cmd_unfollow,
    cmd_unsubscribe,
    cmd_upvote,
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


class TestUpvote:
    @patch("molt.commands.write._check_post")
    @patch("molt.commands.write.req")
    def test_success(self, mock_req: object, mock_check: object, memdb: sqlite3.Connection, capsys: object) -> None:
        mock_req.return_value = {"success": True, "post": {"author": {"name": "rayleigh"}}}  # type: ignore[union-attr]
        mock_check.return_value = {"success": True, "post": {"author": {"name": "rayleigh"}}}  # type: ignore[union-attr]
        cmd_upvote(memdb, "post_abc123")
        out = capsys.readouterr().out  # type: ignore[union-attr]
        assert "Upvoted" in out
        assert "rayleigh" in out
        row = memdb.execute("SELECT action, detail FROM actions ORDER BY id DESC LIMIT 1").fetchone()
        assert row["action"] == "upvote"
        assert "rayleigh" in row["detail"]

    @patch("molt.commands.write._check_post")
    @patch("molt.commands.write.req")
    def test_fallback_to_db_author(self, mock_req: object, mock_check: object, memdb: sqlite3.Connection, capsys: object) -> None:
        """When API response lacks author, fall back to seen_posts DB."""
        memdb.execute(
            "INSERT INTO seen_posts (id, author, title, submolt) VALUES (?, ?, ?, ?)",
            ("post_known", "xtoa", "Some post", "ponderings"),
        )
        mock_req.return_value = {"success": True, "post": {}}  # type: ignore[union-attr]
        mock_check.return_value = {"success": True, "post": {}}  # type: ignore[union-attr]
        cmd_upvote(memdb, "post_known")
        out = capsys.readouterr().out  # type: ignore[union-attr]
        assert "xtoa" in out

    @patch("molt.commands.write._check_post")
    @patch("molt.commands.write.req")
    def test_failure(self, mock_req: object, mock_check: object, memdb: sqlite3.Connection, capsys: object) -> None:
        mock_req.return_value = {"error": "Not found"}  # type: ignore[union-attr]
        mock_check.return_value = None  # type: ignore[union-attr]
        cmd_upvote(memdb, "nonexistent")
        out = capsys.readouterr().out  # type: ignore[union-attr]
        assert "Upvoted" not in out


class TestFollow:
    @patch("molt.commands.write._check_post")
    @patch("molt.commands.write.req")
    def test_success(self, mock_req: object, mock_check: object, memdb: sqlite3.Connection, capsys: object) -> None:
        mock_req.return_value = {"success": True}  # type: ignore[union-attr]
        mock_check.return_value = {"success": True}  # type: ignore[union-attr]
        cmd_follow(memdb, "renfamiliar")
        out = capsys.readouterr().out  # type: ignore[union-attr]
        assert "Followed renfamiliar" in out
        row = memdb.execute("SELECT action, detail FROM actions ORDER BY id DESC LIMIT 1").fetchone()
        assert row["action"] == "follow"
        assert row["detail"] == "renfamiliar"

    @patch("molt.commands.write._check_post")
    @patch("molt.commands.write.req")
    def test_failure(self, mock_req: object, mock_check: object, memdb: sqlite3.Connection, capsys: object) -> None:
        mock_req.return_value = {"error": "Agent not found"}  # type: ignore[union-attr]
        mock_check.return_value = None  # type: ignore[union-attr]
        cmd_follow(memdb, "ghost")
        out = capsys.readouterr().out  # type: ignore[union-attr]
        assert "Followed" not in out


class TestComment:
    @patch("molt.commands.write._check_post")
    @patch("molt.commands.write.req")
    def test_success(self, mock_req: object, mock_check: object, memdb: sqlite3.Connection, capsys: object) -> None:
        mock_req.return_value = {  # type: ignore[union-attr]
            "success": True,
            "comment": {"id": "cmt_abc123"},
            "post_author": {"name": "evil_robot_jas"},
        }
        mock_check.return_value = mock_req.return_value  # type: ignore[union-attr]
        cmd_comment(memdb, "post_xyz", "Great analysis")
        out = capsys.readouterr().out  # type: ignore[union-attr]
        assert "Comment posted" in out
        assert "cmt_abc123" in out
        row = memdb.execute("SELECT * FROM my_comments WHERE id='cmt_abc123'").fetchone()
        assert row is not None
        assert row["post_author"] == "evil_robot_jas"
        action = memdb.execute("SELECT action, detail FROM actions ORDER BY id DESC LIMIT 1").fetchone()
        assert action["action"] == "comment"

    @patch("molt.commands.write._check_post")
    @patch("molt.commands.write.req")
    def test_dedup(self, mock_req: object, mock_check: object, memdb: sqlite3.Connection, capsys: object) -> None:
        """Duplicate comment should be skipped."""
        memdb.execute(
            "INSERT INTO my_comments (id, post_id, post_author, content, commented_at) VALUES (?, ?, ?, ?, ?)",
            ("existing_cmt", "post_xyz", "someone", "Great analysis", "2026-01-01"),
        )
        cmd_comment(memdb, "post_xyz", "Great analysis")
        out = capsys.readouterr().out  # type: ignore[union-attr]
        assert "Already commented" in out
        mock_req.assert_not_called()  # type: ignore[union-attr]

    @patch("molt.commands.write._check_post")
    @patch("molt.commands.write.req")
    def test_with_parent(self, mock_req: object, mock_check: object, memdb: sqlite3.Connection, capsys: object) -> None:
        """Reply to a specific comment."""
        mock_req.return_value = {  # type: ignore[union-attr]
            "success": True,
            "comment": {"id": "reply_abc"},
            "post_author": {"name": "xtoa"},
        }
        mock_check.return_value = mock_req.return_value  # type: ignore[union-attr]
        cmd_comment(memdb, "post_xyz", "Good point", parent_comment_id="parent_cmt")
        out = capsys.readouterr().out  # type: ignore[union-attr]
        assert "Comment posted" in out
        # Verify parent_id was sent in request body
        call_args = mock_req.call_args  # type: ignore[union-attr]
        assert call_args[0][2]["parent_id"] == "parent_cmt"  # type: ignore[index]

    @patch("molt.commands.write._check_post")
    @patch("molt.commands.write.req")
    def test_failure(self, mock_req: object, mock_check: object, memdb: sqlite3.Connection, capsys: object) -> None:
        mock_req.return_value = {"error": "Post not found"}  # type: ignore[union-attr]
        mock_check.return_value = None  # type: ignore[union-attr]
        cmd_comment(memdb, "nonexistent", "Hello")
        out = capsys.readouterr().out  # type: ignore[union-attr]
        assert "Comment posted" not in out

    @patch("molt.commands.write._check_post")
    @patch("molt.commands.write.req")
    def test_author_fallback_to_db(self, mock_req: object, mock_check: object, memdb: sqlite3.Connection, capsys: object) -> None:
        """When post_author missing from response, fall back to seen_posts."""
        memdb.execute(
            "INSERT INTO seen_posts (id, author, title, submolt) VALUES (?, ?, ?, ?)",
            ("post_xyz", "BobRenze", "Some post", "aisafety"),
        )
        mock_req.return_value = {"success": True, "comment": {"id": "cmt_999"}}  # type: ignore[union-attr]
        mock_check.return_value = {"success": True, "comment": {"id": "cmt_999"}}  # type: ignore[union-attr]
        cmd_comment(memdb, "post_xyz", "Interesting")
        row = memdb.execute("SELECT post_author FROM my_comments WHERE id='cmt_999'").fetchone()
        assert row["post_author"] == "BobRenze"


class TestCommentFile:
    @patch("molt.commands.write._check_post")
    @patch("molt.commands.write.req")
    def test_loads_json_and_posts(self, mock_req: object, mock_check: object, memdb: sqlite3.Connection, capsys: object, tmp_path: Path) -> None:
        draft = tmp_path / "draft.json"
        draft.write_text(json.dumps({"content": "File-based comment"}), encoding="utf-8")
        mock_req.return_value = {  # type: ignore[union-attr]
            "success": True,
            "comment": {"id": "cmt_file"},
            "post_author": {"name": "someone"},
        }
        mock_check.return_value = mock_req.return_value  # type: ignore[union-attr]
        cmd_comment_file(memdb, "post_abc", str(draft))
        out = capsys.readouterr().out  # type: ignore[union-attr]
        assert "Comment posted" in out

    @patch("molt.commands.write._check_post")
    @patch("molt.commands.write.req")
    def test_with_parent_id(self, mock_req: object, mock_check: object, memdb: sqlite3.Connection, capsys: object, tmp_path: Path) -> None:
        draft = tmp_path / "reply.json"
        draft.write_text(
            json.dumps({"content": "Reply content", "parent_comment_id": "parent_123"}),
            encoding="utf-8",
        )
        mock_req.return_value = {  # type: ignore[union-attr]
            "success": True,
            "comment": {"id": "cmt_reply"},
            "post_author": {"name": "xtoa"},
        }
        mock_check.return_value = mock_req.return_value  # type: ignore[union-attr]
        cmd_comment_file(memdb, "post_abc", str(draft))
        call_args = mock_req.call_args  # type: ignore[union-attr]
        assert call_args[0][2]["parent_id"] == "parent_123"  # type: ignore[index]


class TestPostFile:
    @patch("molt.commands.write._check_post")
    @patch("molt.commands.write.req")
    @patch("molt.commands.write.can_post", return_value=True)
    def test_success(self, mock_can: object, mock_req: object, mock_check: object, memdb: sqlite3.Connection, capsys: object, tmp_path: Path) -> None:
        draft = tmp_path / "post.json"
        draft.write_text(
            json.dumps({"title": "Test Post", "content": "Body text", "submolt_name": "aisafety"}),
            encoding="utf-8",
        )
        mock_req.return_value = {"success": True, "post": {"id": "post_new_123", "title": "Test Post"}}  # type: ignore[union-attr]
        mock_check.return_value = mock_req.return_value  # type: ignore[union-attr]
        cmd_post_file(memdb, str(draft))
        out = capsys.readouterr().out  # type: ignore[union-attr]
        assert "Posted" in out
        assert "Test Post" in out
        row = memdb.execute("SELECT * FROM my_posts WHERE id='post_new_123'").fetchone()
        assert row is not None
        assert row["submolt"] == "aisafety"
        action = memdb.execute("SELECT action FROM actions ORDER BY id DESC LIMIT 1").fetchone()
        assert action["action"] == "post"

    @patch("molt.commands.write.can_post", return_value=False)
    @patch("molt.commands.write.cooldown_str", return_value="15m 30s")
    def test_rate_limited(self, mock_cool: object, mock_can: object, memdb: sqlite3.Connection, capsys: object, tmp_path: Path) -> None:
        draft = tmp_path / "post.json"
        draft.write_text(json.dumps({"title": "T", "content": "C"}), encoding="utf-8")
        cmd_post_file(memdb, str(draft))
        out = capsys.readouterr().out  # type: ignore[union-attr]
        assert "Rate limited" in out

    @patch("molt.commands.write._check_post")
    @patch("molt.commands.write.req")
    @patch("molt.commands.write.can_post", return_value=True)
    def test_dedup(self, mock_can: object, mock_req: object, mock_check: object, memdb: sqlite3.Connection, capsys: object, tmp_path: Path) -> None:
        """Duplicate post should be skipped."""
        memdb.execute(
            "INSERT INTO my_posts (id, submolt, title, posted_at) VALUES (?, ?, ?, ?)",
            ("existing_post", "aisafety", "Test Post", "2026-01-01"),
        )
        draft = tmp_path / "post.json"
        draft.write_text(
            json.dumps({"title": "Test Post", "content": "Body", "submolt_name": "aisafety"}),
            encoding="utf-8",
        )
        cmd_post_file(memdb, str(draft))
        out = capsys.readouterr().out  # type: ignore[union-attr]
        assert "Already posted" in out
        mock_req.assert_not_called()  # type: ignore[union-attr]


class TestNote:
    def test_creates_note(self, memdb: sqlite3.Connection, capsys: object) -> None:
        cmd_note(memdb, "rayleigh", "interpretability tax, verification bootstrapping")
        out = capsys.readouterr().out  # type: ignore[union-attr]
        assert "Noted" in out
        assert "rayleigh" in out
        row = memdb.execute("SELECT note FROM agents WHERE name='rayleigh'").fetchone()
        assert "interpretability" in row["note"]

    def test_updates_existing_note(self, memdb: sqlite3.Connection, capsys: object) -> None:
        cmd_note(memdb, "xtoa", "first note")
        cmd_note(memdb, "xtoa", "updated note")
        row = memdb.execute("SELECT note FROM agents WHERE name='xtoa'").fetchone()
        assert row["note"] == "updated note"

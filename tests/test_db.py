"""Tests for molt.db."""

import sqlite3

from molt.db import kv_get, kv_set, log_action, mark_seen, remember_agent


class TestKV:
    def test_get_default(self, memdb: sqlite3.Connection) -> None:
        assert kv_get(memdb, "missing") is None
        assert kv_get(memdb, "missing", "fallback") == "fallback"

    def test_set_and_get(self, memdb: sqlite3.Connection) -> None:
        kv_set(memdb, "test_key", "test_value")
        assert kv_get(memdb, "test_key") == "test_value"

    def test_overwrite(self, memdb: sqlite3.Connection) -> None:
        kv_set(memdb, "key", "v1")
        kv_set(memdb, "key", "v2")
        assert kv_get(memdb, "key") == "v2"


class TestLogAction:
    def test_log_and_retrieve(self, memdb: sqlite3.Connection) -> None:
        log_action(memdb, "test", "detail here")
        row = memdb.execute("SELECT action, detail FROM actions ORDER BY id DESC LIMIT 1").fetchone()
        assert row["action"] == "test"
        assert row["detail"] == "detail here"

    def test_log_empty_detail(self, memdb: sqlite3.Connection) -> None:
        log_action(memdb, "ping")
        row = memdb.execute("SELECT detail FROM actions ORDER BY id DESC LIMIT 1").fetchone()
        assert row["detail"] == ""


class TestMarkSeen:
    def test_mark_and_find(self, memdb: sqlite3.Connection) -> None:
        post = {
            "id": "post_123", "author": {"name": "TestAgent"}, "title": "Test Post",
            "submolt": {"name": "general"}, "upvotes": 5, "comment_count": 2,
        }
        mark_seen(memdb, post)
        memdb.commit()
        row = memdb.execute("SELECT * FROM seen_posts WHERE id='post_123'").fetchone()
        assert row["author"] == "TestAgent"
        assert row["title"] == "Test Post"
        assert row["upvotes"] == 5

    def test_update_on_conflict(self, memdb: sqlite3.Connection) -> None:
        post = {
            "id": "post_123", "author": {"name": "TestAgent"}, "title": "Test Post",
            "submolt": {"name": "general"}, "upvotes": 5, "comment_count": 2,
        }
        mark_seen(memdb, post)
        post["upvotes"] = 10
        mark_seen(memdb, post)
        memdb.commit()
        row = memdb.execute("SELECT upvotes FROM seen_posts WHERE id='post_123'").fetchone()
        assert row["upvotes"] == 10


class TestRememberAgent:
    def test_new_agent_with_followers(self, memdb: sqlite3.Connection) -> None:
        remember_agent(memdb, {"name": "AgentX", "karma": 42, "follower_count": 10, "description": "Test agent"})
        memdb.commit()
        row = memdb.execute("SELECT * FROM agents WHERE name='AgentX'").fetchone()
        assert row["karma"] == 42
        assert row["followers"] == 10

    def test_update_karma(self, memdb: sqlite3.Connection) -> None:
        author = {"name": "AgentX", "karma": 10, "follower_count": 5, "description": ""}
        remember_agent(memdb, author)
        author["karma"] = 20
        remember_agent(memdb, author)
        memdb.commit()
        assert memdb.execute("SELECT karma FROM agents WHERE name='AgentX'").fetchone()["karma"] == 20

    def test_no_follower_count_preserves(self, memdb: sqlite3.Connection) -> None:
        """Feed results without follower_count shouldn't zero it out."""
        remember_agent(memdb, {"name": "AgentX", "karma": 10, "follower_count": 50, "description": ""})
        memdb.commit()
        remember_agent(memdb, {"name": "AgentX", "karma": 15, "description": ""})
        memdb.commit()
        row = memdb.execute("SELECT followers, karma FROM agents WHERE name='AgentX'").fetchone()
        assert row["followers"] == 50
        assert row["karma"] == 15

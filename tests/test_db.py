"""Tests for molt.db — database operations."""

from molt.db import kv_get, kv_set, log_action, mark_seen, remember_agent


class TestKV:
    def test_get_default(self, memdb):
        assert kv_get(memdb, "missing") is None
        assert kv_get(memdb, "missing", "fallback") == "fallback"

    def test_set_and_get(self, memdb):
        kv_set(memdb, "test_key", "test_value")
        assert kv_get(memdb, "test_key") == "test_value"

    def test_overwrite(self, memdb):
        kv_set(memdb, "key", "v1")
        kv_set(memdb, "key", "v2")
        assert kv_get(memdb, "key") == "v2"


class TestLogAction:
    def test_log_and_retrieve(self, memdb):
        log_action(memdb, "test", "detail here")
        row = memdb.execute(
            "SELECT action, detail FROM actions ORDER BY id DESC LIMIT 1"
        ).fetchone()
        assert row["action"] == "test"
        assert row["detail"] == "detail here"

    def test_log_empty_detail(self, memdb):
        log_action(memdb, "ping")
        row = memdb.execute(
            "SELECT detail FROM actions ORDER BY id DESC LIMIT 1"
        ).fetchone()
        assert row["detail"] == ""


class TestMarkSeen:
    def test_mark_and_find(self, memdb):
        post = {
            "id": "post_123",
            "author": {"name": "TestAgent"},
            "title": "Test Post",
            "submolt": {"name": "general"},
            "upvotes": 5,
            "comment_count": 2,
        }
        mark_seen(memdb, post)
        memdb.commit()
        row = memdb.execute(
            "SELECT * FROM seen_posts WHERE id='post_123'"
        ).fetchone()
        assert row["author"] == "TestAgent"
        assert row["title"] == "Test Post"
        assert row["upvotes"] == 5

    def test_update_on_conflict(self, memdb):
        post = {
            "id": "post_123",
            "author": {"name": "TestAgent"},
            "title": "Test Post",
            "submolt": {"name": "general"},
            "upvotes": 5,
            "comment_count": 2,
        }
        mark_seen(memdb, post)
        post["upvotes"] = 10
        mark_seen(memdb, post)
        memdb.commit()
        row = memdb.execute(
            "SELECT upvotes FROM seen_posts WHERE id='post_123'"
        ).fetchone()
        assert row["upvotes"] == 10


class TestRememberAgent:
    def test_new_agent_with_followers(self, memdb):
        author = {"name": "AgentX", "karma": 42, "follower_count": 10, "description": "Test agent"}
        remember_agent(memdb, author)
        memdb.commit()
        row = memdb.execute("SELECT * FROM agents WHERE name='AgentX'").fetchone()
        assert row["karma"] == 42
        assert row["followers"] == 10

    def test_update_karma(self, memdb):
        author = {"name": "AgentX", "karma": 10, "follower_count": 5, "description": ""}
        remember_agent(memdb, author)
        author["karma"] = 20
        remember_agent(memdb, author)
        memdb.commit()
        row = memdb.execute("SELECT karma FROM agents WHERE name='AgentX'").fetchone()
        assert row["karma"] == 20

    def test_no_follower_count_doesnt_overwrite(self, memdb):
        """Feed results don't include follower_count — shouldn't zero it out."""
        author = {"name": "AgentX", "karma": 10, "follower_count": 50, "description": ""}
        remember_agent(memdb, author)
        memdb.commit()
        # Feed result without follower_count
        feed_author = {"name": "AgentX", "karma": 15, "description": ""}
        remember_agent(memdb, feed_author)
        memdb.commit()
        row = memdb.execute("SELECT followers, karma FROM agents WHERE name='AgentX'").fetchone()
        assert row["followers"] == 50  # preserved from first insert
        assert row["karma"] == 15  # updated

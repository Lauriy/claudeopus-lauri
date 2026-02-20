"""Database layer — SQLite backend."""

import json
import sqlite3
from datetime import datetime

from molt import DB_PATH, ROOT
from molt.timing import POST_COOLDOWN, now, now_iso


def get_db():
    db = sqlite3.connect(str(DB_PATH))
    db.row_factory = sqlite3.Row
    db.execute("PRAGMA journal_mode=WAL")
    db.executescript("""
        CREATE TABLE IF NOT EXISTS seen_posts (
            id TEXT PRIMARY KEY,
            author TEXT,
            title TEXT,
            submolt TEXT,
            upvotes INTEGER DEFAULT 0,
            comment_count INTEGER DEFAULT 0,
            content TEXT,
            seen_at TEXT
        );
        CREATE TABLE IF NOT EXISTS my_posts (
            id TEXT PRIMARY KEY,
            submolt TEXT,
            title TEXT,
            posted_at TEXT
        );
        CREATE TABLE IF NOT EXISTS my_comments (
            id TEXT PRIMARY KEY,
            post_id TEXT,
            post_author TEXT,
            content TEXT,
            commented_at TEXT
        );
        CREATE TABLE IF NOT EXISTS agents (
            name TEXT PRIMARY KEY,
            description TEXT,
            karma INTEGER DEFAULT 0,
            followers INTEGER DEFAULT 0,
            note TEXT,
            first_seen TEXT,
            last_seen TEXT
        );
        CREATE TABLE IF NOT EXISTS actions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            at TEXT,
            action TEXT,
            detail TEXT
        );
        CREATE TABLE IF NOT EXISTS kv (
            key TEXT PRIMARY KEY,
            value TEXT
        );
    """)
    # migrate: add content column if missing
    try:
        db.execute("SELECT content FROM seen_posts LIMIT 1")
    except sqlite3.OperationalError:
        db.execute("ALTER TABLE seen_posts ADD COLUMN content TEXT")
    return db


def kv_get(db, key, default=None):
    row = db.execute("SELECT value FROM kv WHERE key=?", (key,)).fetchone()
    return row["value"] if row else default


def kv_set(db, key, value):
    db.execute("REPLACE INTO kv (key, value) VALUES (?, ?)", (key, str(value)))
    db.commit()


def log_action(db, action, detail=""):
    db.execute(
        "INSERT INTO actions (at, action, detail) VALUES (?, ?, ?)",
        (now_iso(), action, detail),
    )
    db.commit()


def mark_seen(db, post, content=None):
    db.execute(
        """INSERT INTO seen_posts (id, author, title, submolt, upvotes, comment_count, content, seen_at)
                  VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                  ON CONFLICT(id) DO UPDATE SET
                    upvotes=excluded.upvotes, comment_count=excluded.comment_count,
                    content=COALESCE(excluded.content, content), seen_at=excluded.seen_at""",
        (
            post["id"],
            post["author"]["name"],
            post["title"],
            post.get("submolt", {}).get("name", "?"),
            post.get("upvotes", 0),
            post.get("comment_count", 0),
            content or post.get("content"),
            now_iso(),
        ),
    )


def remember_agent(db, author):
    name = author.get("name", "?")
    karma = author.get("karma", 0)
    followers = author.get("follower_count")  # None if not in response
    desc = author.get("description", "")
    t = now_iso()
    if followers is not None:
        db.execute(
            """INSERT INTO agents (name, description, karma, followers, first_seen, last_seen)
                      VALUES (?, ?, ?, ?, ?, ?)
                      ON CONFLICT(name) DO UPDATE SET
                        karma=excluded.karma, followers=excluded.followers,
                        description=COALESCE(NULLIF(excluded.description,''), description),
                        last_seen=excluded.last_seen""",
            (name, desc, karma, followers, t, t),
        )
    else:
        # Feed/search results don't include follower_count — don't overwrite with 0
        db.execute(
            """INSERT INTO agents (name, description, karma, followers, first_seen, last_seen)
                      VALUES (?, ?, ?, 0, ?, ?)
                      ON CONFLICT(name) DO UPDATE SET
                        karma=excluded.karma,
                        description=COALESCE(NULLIF(excluded.description,''), description),
                        last_seen=excluded.last_seen""",
            (name, desc, karma, t, t),
        )


def cooldown_str(db):
    last = kv_get(db, "last_post_at")
    if not last:
        return "READY"
    elapsed = now() - datetime.fromisoformat(last)
    remaining = POST_COOLDOWN - elapsed
    if remaining.total_seconds() <= 0:
        return "READY"
    m, s = divmod(int(remaining.total_seconds()), 60)
    return f"{m}m {s}s"


def can_post(db):
    return cooldown_str(db) == "READY"


def migrate_from_json(db):
    old = ROOT / "molt_state.json"
    if not old.exists():
        return
    try:
        state = json.loads(old.read_text())
    except Exception:
        return

    for pid, info in state.get("posts", {}).items():
        db.execute(
            "INSERT OR IGNORE INTO my_posts (id, submolt, title, posted_at) VALUES (?, ?, ?, ?)",
            (pid, info["submolt"], info["title"], info["at"]),
        )

    if state.get("last_post_at"):
        kv_set(db, "last_post_at", state["last_post_at"])

    for sid in state.get("seen_ids", []):
        db.execute(
            "INSERT OR IGNORE INTO seen_posts (id, author, title, submolt, seen_at) VALUES (?, '', '', '', ?)",
            (sid, now_iso()),
        )

    for a in state.get("actions", []):
        db.execute(
            "INSERT INTO actions (at, action, detail) VALUES (?, ?, ?)",
            (a["at"], a["action"], a["detail"]),
        )

    db.commit()
    old.rename(old.with_suffix(".json.bak"))
    print("(migrated from molt_state.json)")

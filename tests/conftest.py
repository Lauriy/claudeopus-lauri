"""Shared test fixtures."""

import os
import sqlite3
from collections.abc import Iterator

import pytest

os.environ["MOLTBOOK_API_KEY"] = "test_key_not_real"


@pytest.fixture
def memdb() -> Iterator[sqlite3.Connection]:
    db = sqlite3.connect(":memory:")
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
        CREATE TABLE IF NOT EXISTS kv (key TEXT PRIMARY KEY, value TEXT);
    """)
    yield db
    db.close()

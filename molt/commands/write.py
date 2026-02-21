"""Write commands — post, comment, upvote, follow, note."""

import json
import sqlite3

from molt.api import _check_post, req
from molt.db import can_post, cooldown_str, kv_set, log_action
from molt.timing import now_iso


def cmd_post_file(db: sqlite3.Connection, path: str) -> None:
    if not can_post(db):
        print(f"Rate limited: {cooldown_str(db)}")
        return
    with open(path, encoding="utf-8") as f:
        body = json.load(f)
    submolt = body.get("submolt_name") or body.get("submolt", "general")
    exists = db.execute(
        "SELECT id FROM my_posts WHERE submolt=? AND title=?", (submolt, body["title"]),
    ).fetchone()
    if exists:
        print(f"Already posted '{body['title'][:40]}' in m/{submolt} (id={exists['id'][:8]}). Skipping.")
        print("To force re-post, delete the old record first.")
        return
    d = req("POST", "/posts", {"submolt_name": submolt, "title": body["title"], "content": body["content"]})
    d = _check_post(d)
    if not d:
        return
    t = now_iso()
    kv_set(db, "last_post_at", t)
    db.execute(
        "INSERT OR REPLACE INTO my_posts (id, submolt, title, posted_at) VALUES (?, ?, ?, ?)",
        (d["post"]["id"], submolt, body["title"], t),
    )
    log_action(db, "post", f"[{submolt}] {body['title'][:40]}")
    db.commit()
    print(f"Posted: {d['post']['title']}")
    print(f"ID: {d['post']['id']}")


def cmd_comment(
    db: sqlite3.Connection, post_id: str, content: str,
    parent_comment_id: str | None = None,
) -> None:
    exists = db.execute(
        "SELECT id FROM my_comments WHERE post_id=? AND content=?", (post_id, content[:500]),
    ).fetchone()
    if exists:
        print(f"Already commented on this post (id={exists['id']}). Skipping.")
        return
    body: dict[str, str] = {"content": content}
    if parent_comment_id:
        body["parent_id"] = parent_comment_id
    d = req("POST", f"/posts/{post_id}/comments", body)
    d = _check_post(d)
    if not d:
        return
    cmt = d.get("comment")
    if not cmt:
        print("Warning: comment may have been created but response missing 'comment' key.")
        print(f"Raw response keys: {list(d.keys())}")
        return
    author_name = d.get("post_author", {}).get("name", "")
    if not author_name:
        row = db.execute("SELECT author FROM seen_posts WHERE id=?", (post_id,)).fetchone()
        author_name = row["author"] if row else "?"
    db.execute(
        "INSERT OR REPLACE INTO my_comments (id, post_id, post_author, content, commented_at) VALUES (?, ?, ?, ?, ?)",
        (cmt["id"], post_id, author_name, content[:500], now_iso()),
    )
    log_action(db, "comment", f"on {author_name}'s post ({post_id[:8]})")
    db.commit()
    print(f"Comment posted: {cmt['id']}")


def cmd_comment_file(db: sqlite3.Connection, post_id: str, path: str) -> None:
    with open(path, encoding="utf-8") as f:
        body = json.load(f)
    cmd_comment(db, post_id, body["content"], body.get("parent_comment_id"))


def cmd_upvote(db: sqlite3.Connection, post_id: str) -> None:
    d = req("POST", f"/posts/{post_id}/upvote")
    d = _check_post(d)
    if not d:
        return
    post = d.get("post", {})
    name = post.get("author", {}).get("name", "") if isinstance(post, dict) else ""
    if not name:
        row = db.execute("SELECT author FROM seen_posts WHERE id=?", (post_id,)).fetchone()
        name = row["author"] if row else post_id[:8]
    log_action(db, "upvote", name)
    db.commit()
    print(f"Upvoted {name}'s post")


def cmd_follow(db: sqlite3.Connection, agent_name: str) -> None:
    d = req("POST", f"/agents/{agent_name}/follow")
    d = _check_post(d)
    if not d:
        return
    log_action(db, "follow", agent_name)
    print(f"Followed {agent_name}")


def cmd_describe(db: sqlite3.Connection, text: str) -> None:
    d = req("PATCH", "/agents/me", {"description": text})
    if d.get("error") or d.get("statusCode"):
        print(f"Error: {d.get('error', d.get('message', '?'))}")
        return
    agent = d.get("agent", {})
    new_desc = agent.get("description", text)
    print(f"Profile description updated: {new_desc[:100]}")
    log_action(db, "describe", new_desc[:60])
    db.commit()


def cmd_unfollow(db: sqlite3.Connection, agent_name: str) -> None:
    d = req("DELETE", f"/agents/{agent_name}/follow")
    if d.get("error") or d.get("statusCode"):
        print(f"Error: {d.get('error', d.get('message', '?'))}")
        return
    log_action(db, "unfollow", agent_name)
    db.commit()
    print(f"Unfollowed {agent_name}")


def cmd_cupvote(db: sqlite3.Connection, comment_id: str) -> None:
    d = req("POST", f"/comments/{comment_id}/upvote")
    d = _check_post(d)
    if not d:
        return
    log_action(db, "cupvote", comment_id)
    db.commit()
    print(f"Upvoted comment {comment_id}")


def cmd_downvote(db: sqlite3.Connection, post_id: str) -> None:
    d = req("POST", f"/posts/{post_id}/downvote")
    d = _check_post(d)
    if not d:
        return
    log_action(db, "downvote", post_id)
    db.commit()
    print(f"Downvoted post {post_id}")


def cmd_subscribe(db: sqlite3.Connection, submolt: str) -> None:
    d = req("POST", f"/submolts/{submolt}/subscribe")
    d = _check_post(d)
    if not d:
        return
    log_action(db, "subscribe", submolt)
    db.commit()
    print(f"Subscribed to m/{submolt}")


def cmd_unsubscribe(db: sqlite3.Connection, submolt: str) -> None:
    d = req("DELETE", f"/submolts/{submolt}/subscribe")
    if d.get("error") or d.get("statusCode"):
        print(f"Error: {d.get('error', d.get('message', '?'))}")
        return
    log_action(db, "unsub", submolt)
    db.commit()
    print(f"Unsubscribed from m/{submolt}")


def cmd_note(db: sqlite3.Connection, agent_name: str, note: str) -> None:
    db.execute(
        "INSERT INTO agents (name, note, first_seen, last_seen) VALUES (?, ?, ?, ?) ON CONFLICT(name) DO UPDATE SET note=?",
        (agent_name, note, now_iso(), now_iso(), note),
    )
    db.commit()
    print(f"Noted: {agent_name} = {note}")

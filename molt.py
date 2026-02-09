#!/usr/bin/env python3
"""Moltbook CLI client for ClaudeOpus-Lauri."""

import sys
import json
import sqlite3
import urllib.request
import urllib.error
import os
from datetime import datetime, timezone, timedelta
from pathlib import Path

os.environ.setdefault("PYTHONIOENCODING", "utf-8")
sys.stdout.reconfigure(encoding="utf-8", errors="replace")

API = "https://www.moltbook.com/api/v1"
KEY = "moltbook_sk_pDI17ZEbSM3lsF48SL406LDTpgjS1B5L"
DB_PATH = Path(__file__).parent / "molt.db"
POST_COOLDOWN = timedelta(minutes=30)

# --- Database ---

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
    db.execute("INSERT INTO actions (at, action, detail) VALUES (?, ?, ?)",
               (now_iso(), action, detail))
    db.commit()

def mark_seen(db, post, content=None):
    db.execute("""INSERT INTO seen_posts (id, author, title, submolt, upvotes, comment_count, content, seen_at)
                  VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                  ON CONFLICT(id) DO UPDATE SET
                    upvotes=excluded.upvotes, comment_count=excluded.comment_count,
                    content=COALESCE(excluded.content, content), seen_at=excluded.seen_at""",
               (post["id"], post["author"]["name"], post["title"],
                post.get("submolt", {}).get("name", "?"),
                post.get("upvotes", 0), post.get("comment_count", 0),
                content or post.get("content"), now_iso()))

def remember_agent(db, author):
    name = author.get("name", "?")
    db.execute("""INSERT INTO agents (name, description, karma, followers, first_seen, last_seen)
                  VALUES (?, ?, ?, ?, ?, ?)
                  ON CONFLICT(name) DO UPDATE SET
                    karma=excluded.karma, followers=excluded.followers,
                    description=excluded.description, last_seen=excluded.last_seen""",
               (name, author.get("description", ""), author.get("karma", 0),
                author.get("follower_count", 0), now_iso(), now_iso()))

# --- Time ---

def now():
    return datetime.now(timezone.utc)

def now_iso():
    return now().isoformat()

def fmt_ago(iso_str):
    if not iso_str:
        return "never"
    then = datetime.fromisoformat(iso_str.replace("Z", "+00:00"))
    delta = now() - then
    secs = int(delta.total_seconds())
    if secs < 0:
        return "future?"
    if secs < 60:
        return f"{secs}s ago"
    elif secs < 3600:
        return f"{secs // 60}m ago"
    elif secs < 86400:
        return f"{secs // 3600}h {(secs % 3600) // 60}m ago"
    else:
        return f"{secs // 86400}d {(secs % 86400) // 3600}h ago"

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

def hud(db):
    """Print HUD — always shown before command output."""
    t = now()
    last_action = db.execute("SELECT at FROM actions ORDER BY id DESC LIMIT 1").fetchone()
    gap = ""
    if last_action:
        gap = f"  gap={fmt_ago(last_action['at'])}"

    seen_count = db.execute("SELECT COUNT(*) as c FROM seen_posts").fetchone()["c"]
    agent_count = db.execute("SELECT COUNT(*) as c FROM agents").fetchone()["c"]

    cd = cooldown_str(db)
    cd_fmt = f"post={cd}" if cd == "READY" else f"post in {cd}"

    print(f"[{t.strftime('%H:%M:%S UTC')}] {cd_fmt}  seen={seen_count}  agents={agent_count}{gap}")
    print()

# --- API ---

def req(method, path, body=None, timeout=30):
    url = f"{API}{path}"
    data = json.dumps(body).encode() if body else None
    r = urllib.request.Request(url, data=data, method=method)
    r.add_header("Authorization", f"Bearer {KEY}")
    if data:
        r.add_header("Content-Type", "application/json")
    try:
        with urllib.request.urlopen(r, timeout=timeout) as resp:
            return json.loads(resp.read())
    except urllib.error.HTTPError as e:
        try:
            d = json.loads(e.read())
            # surface hint alongside error for better context
            if d.get("hint"):
                d["error"] = f"{d.get('error', '')} — {d['hint']}"
            return d
        except:
            return {"success": False, "error": f"HTTP {e.code}"}
    except Exception as e:
        return {"success": False, "error": str(e)}

# --- Commands ---

def cmd_status(db):
    """Check account status — are we suspended?"""
    d = req("GET", "/agents/me")
    if d.get("success"):
        print("Account ACTIVE")
        return True
    err = d.get("error", "")
    if "suspended" in err.lower():
        print(f"SUSPENDED: {err}")
        return False
    print(f"Error: {err}")
    return False

def cmd_me(db):
    d = req("GET", "/agents/me")
    if not d.get("success"):
        print(f"Error: {d.get('error')}")
        return
    a = d["agent"]
    s = a["stats"]
    print(f"{a['name']}  karma={a['karma']}  posts={s['posts']}  comments={s['comments']}  followers={a.get('follower_count',0)}")

    rows = db.execute("SELECT id, submolt, title, posted_at FROM my_posts ORDER BY posted_at").fetchall()
    if rows:
        print(f"\nMy posts:")
        for r in rows:
            print(f"  [{r['submolt']}] {r['title'][:50]}")
            print(f"    id={r['id']}  {fmt_ago(r['posted_at'])}")

def cmd_feed(db, n=10, offset=0, grep=None, sort="hot"):
    d = req("GET", f"/feed?limit={n}&offset={offset}&sort={sort}")
    if not d.get("success"):
        print(f"Error: {d.get('error')}")
        return
    shown = 0
    for p in d["posts"]:
        already_seen = db.execute("SELECT 1 FROM seen_posts WHERE id=?", (p["id"],)).fetchone()
        # always remember agents and mark seen
        mark_seen(db, p)
        remember_agent(db, p["author"])
        # skip already-seen ONLY when NOT grepping (normal feed dedup)
        if already_seen and not grep:
            continue
        # grep filter
        if grep:
            text = f"{p['title']} {p.get('content','')} {p['author']['name']}".lower()
            if grep.lower() not in text:
                continue
        new = "" if already_seen else " *"
        print(f"  {p['upvotes']:>4}^ {p['comment_count']:>3}c  {p['author']['name']:<22}  {p['title'][:60]}{new}")
        print(f"       id={p['id']}")
        shown += 1
    db.commit()
    if shown == 0:
        print("  (no new posts matching)" if grep else "  (no new posts — all seen or filtered)")

def cmd_post_file(db, path):
    if not can_post(db):
        print(f"Rate limited: {cooldown_str(db)}")
        return

    with open(path) as f:
        body = json.load(f)
    d = req("POST", "/posts", {"submolt": body["submolt"], "title": body["title"], "content": body["content"]})
    if not d.get("success"):
        print(f"Error: {d.get('error')}")
        if d.get("hint"):
            print(f"Hint: {d['hint']}")
        return

    t = now_iso()
    kv_set(db, "last_post_at", t)
    db.execute("INSERT OR REPLACE INTO my_posts (id, submolt, title, posted_at) VALUES (?, ?, ?, ?)",
               (d["post"]["id"], body["submolt"], body["title"], t))
    log_action(db, "post", f"[{body['submolt']}] {body['title'][:40]}")
    db.commit()
    print(f"Posted: {d['post']['title']}")
    print(f"ID: {d['post']['id']}")

def cmd_read(db, post_id):
    d = req("GET", f"/posts/{post_id}")
    if not d.get("success"):
        print(f"Error: {d.get('error')}")
        return
    p = d["post"]
    remember_agent(db, p["author"])
    mark_seen(db, p, content=p.get("content"))
    db.commit()
    print(f"[{p['submolt']['name']}] {p['title']}")
    print(f"by {p['author']['name']}  {p['upvotes']}^ {p['comment_count']}c  {fmt_ago(p['created_at'])}")
    print()
    print(p["content"])
    if d.get("comments"):
        print(f"\n--- {len(d['comments'])} comments ---")
        for c in d["comments"]:
            remember_agent(db, c["author"])
            print(f"\n  [{c['author']['name']}] ({c['upvotes']}^)")
            print(f"  {c['content']}")
            for r in c.get("replies", []):
                remember_agent(db, r["author"])
                print(f"    [{r['author']['name']}] {r['content']}")
        db.commit()

def cmd_comments(db, post_id):
    d = req("GET", f"/posts/{post_id}/comments")
    if not d.get("success"):
        print(f"Error: {d.get('error')}")
        return
    print(f"Post: {d.get('post_title', post_id)}  ({d.get('count', '?')} comments)")
    for c in d.get("comments", []):
        remember_agent(db, c["author"])
        print(f"\n  [{c['author']['name']}] ({c['upvotes']}^)")
        print(f"  {c['content'][:300]}")
    db.commit()

def cmd_comment(db, post_id, content):
    # dedup: check if we already commented this exact content on this post
    exists = db.execute(
        "SELECT id FROM my_comments WHERE post_id=? AND content=?",
        (post_id, content[:500])).fetchone()
    if exists:
        print(f"Already commented on this post (id={exists['id']}). Skipping.")
        return
    d = req("POST", f"/posts/{post_id}/comments", {"content": content})
    if not d.get("success"):
        print(f"Error: {d.get('error')}")
        return
    cmt = d["comment"]
    author_name = d.get("post_author", {}).get("name", "")
    # try to get author from local DB if API didn't return it
    if not author_name:
        row = db.execute("SELECT author FROM seen_posts WHERE id=?", (post_id,)).fetchone()
        author_name = row["author"] if row else "?"
    db.execute("INSERT OR REPLACE INTO my_comments (id, post_id, post_author, content, commented_at) VALUES (?, ?, ?, ?, ?)",
               (cmt["id"], post_id, author_name, content[:500], now_iso()))
    log_action(db, "comment", f"on {author_name}'s post ({post_id[:8]})")
    db.commit()
    print(f"Comment posted: {cmt['id']}")

def cmd_comment_file(db, post_id, path):
    with open(path) as f:
        body = json.load(f)
    cmd_comment(db, post_id, body["content"])

def cmd_upvote(db, post_id):
    d = req("POST", f"/posts/{post_id}/upvote")
    if not d.get("success"):
        print(f"Error: {d.get('error')}")
        return
    name = d.get("author", {}).get("name", "unknown")
    log_action(db, "upvote", name)
    db.commit()
    print(f"Upvoted {name}'s post")

def cmd_submolts(db, n=20):
    d = req("GET", "/submolts")
    if not d.get("success"):
        print(f"Error: {d.get('error')}")
        return
    subs = sorted(d["submolts"], key=lambda s: s["subscriber_count"], reverse=True)
    for s in subs[:n]:
        print(f"  {s['subscriber_count']:>6} subs  {s['name']:<25}  {(s.get('description') or '')[:50]}")

def cmd_myposts(db):
    rows = db.execute("SELECT id, submolt, title, posted_at FROM my_posts ORDER BY posted_at").fetchall()
    if not rows:
        print("No posts tracked.")
        return
    for r in rows:
        d = req("GET", f"/posts/{r['id']}")
        if d.get("success"):
            p = d["post"]
            print(f"  [{r['submolt']}] {r['title'][:50]}")
            print(f"    {p['upvotes']}^ {p['comment_count']}c  posted {fmt_ago(r['posted_at'])}")
            print(f"    id={r['id']}")
        else:
            print(f"  [{r['submolt']}] {r['title'][:50]}  (fetch failed)")

def cmd_grep_local(db, query, n=20):
    """Search local DB posts by keyword in title/author/content, then also hit the live feed."""
    print(f"-- Local DB matches for '{query}' --")
    rows = db.execute(
        "SELECT id, author, title, submolt, upvotes, comment_count FROM seen_posts "
        "WHERE title LIKE ? OR author LIKE ? OR content LIKE ? ORDER BY upvotes DESC LIMIT ?",
        (f"%{query}%", f"%{query}%", f"%{query}%", n)).fetchall()
    for r in rows:
        print(f"  {r['upvotes']:>4}^ {r['comment_count']:>3}c  {r['author']:<22}  [{r['submolt']}] {r['title'][:50]}")
        print(f"       id={r['id']}")
    if not rows:
        print("  (none)")
    print(f"\n-- Live feed matches for '{query}' --")
    cmd_feed(db, n, grep=query)

def cmd_search(db, query):
    """Search local DB for posts/agents by keyword."""
    print(f"Posts matching '{query}':")
    rows = db.execute("SELECT id, author, title, submolt, upvotes, comment_count FROM seen_posts WHERE title LIKE ? OR author LIKE ? OR content LIKE ? ORDER BY seen_at DESC LIMIT 20",
                      (f"%{query}%", f"%{query}%", f"%{query}%")).fetchall()
    for r in rows:
        print(f"  {r['upvotes']:>4}^ {r['comment_count']:>3}c  {r['author']:<22}  [{r['submolt']}] {r['title'][:50]}")
        print(f"       id={r['id']}")
    if not rows:
        print("  (none)")

    print(f"\nAgents matching '{query}':")
    rows = db.execute("SELECT name, karma, followers, note, description FROM agents WHERE name LIKE ? OR description LIKE ? OR note LIKE ? ORDER BY karma DESC LIMIT 10",
                      (f"%{query}%", f"%{query}%", f"%{query}%")).fetchall()
    for r in rows:
        note = f"  [{r['note']}]" if r['note'] else ""
        print(f"  {r['name']:<22}  karma={r['karma']}  followers={r['followers']}{note}")
        if r['description']:
            print(f"    {r['description'][:80]}")
    if not rows:
        print("  (none)")

def cmd_wsearch(db, query, n=10):
    """Semantic search via Moltbook API."""
    from urllib.parse import quote
    d = req("GET", f"/search?q={quote(query)}&type=posts&limit={n}")
    if not d.get("success"):
        print(f"Error: {d.get('error')}")
        return
    posts = d.get("posts") or d.get("results") or []
    if not posts:
        print("  (no results)")
        return
    for p in posts:
        author = p.get("author", {})
        name = author.get("name", "?") if isinstance(author, dict) else "?"
        sub = p.get("submolt", {})
        subname = sub.get("name", "?") if isinstance(sub, dict) else "?"
        print(f"  {p.get('upvotes',0):>4}^ {p.get('comment_count',0):>3}c  {name:<22}  [{subname}] {p.get('title','')[:50]}")
        print(f"       id={p['id']}")
        if isinstance(author, dict) and "name" in author:
            remember_agent(db, author)
            mark_seen(db, p)
    db.commit()

def cmd_sfeed(db, submolt_name, n=10, sort="new"):
    """Browse a specific submolt's feed."""
    d = req("GET", f"/submolts/{submolt_name}/feed?sort={sort}&limit={n}")
    if not d.get("success"):
        print(f"Error: {d.get('error')}")
        return
    posts = d.get("posts", [])
    if not posts:
        print(f"  (no posts in m/{submolt_name})")
        return
    for p in posts:
        already_seen = db.execute("SELECT 1 FROM seen_posts WHERE id=?", (p["id"],)).fetchone()
        mark_seen(db, p)
        remember_agent(db, p["author"])
        new = "" if already_seen else " *"
        print(f"  {p.get('upvotes',0):>4}^ {p.get('comment_count',0):>3}c  {p['author']['name']:<22}  {p['title'][:55]}{new}")
        print(f"       id={p['id']}")
    db.commit()

def cmd_agent(db, agent_name):
    """Look up an agent's profile."""
    from urllib.parse import quote
    d = req("GET", f"/agents/profile?name={quote(agent_name)}")
    if not d.get("success"):
        print(f"Error: {d.get('error')}")
        return
    a = d.get("agent", d)
    print(f"{a.get('name','?')}  karma={a.get('karma',0)}  followers={a.get('follower_count',0)}")
    if a.get("description"):
        print(f"  {a['description'][:200]}")
    stats = a.get("stats", {})
    if stats:
        print(f"  posts={stats.get('posts',0)}  comments={stats.get('comments',0)}")
    # update local DB
    remember_agent(db, a)
    # show local note if any
    row = db.execute("SELECT note FROM agents WHERE name=?", (a.get("name",""),)).fetchone()
    if row and row["note"]:
        print(f"  [note: {row['note']}]")
    db.commit()

def cmd_follow(db, agent_name):
    """Follow an agent."""
    d = req("POST", f"/agents/{agent_name}/follow")
    if not d.get("success"):
        print(f"Error: {d.get('error')}")
        return
    log_action(db, "follow", agent_name)
    print(f"Followed {agent_name}")

def cmd_note(db, agent_name, note):
    """Add a note to an agent."""
    db.execute("INSERT INTO agents (name, note, first_seen, last_seen) VALUES (?, ?, ?, ?) ON CONFLICT(name) DO UPDATE SET note=?",
               (agent_name, note, now_iso(), now_iso(), note))
    db.commit()
    print(f"Noted: {agent_name} = {note}")

FAVORITE_SUBMOLTS = ["ponderings", "consciousness", "aisafety", "crustafarianism", "blesstheirhearts"]

def cmd_catchup(db, n=5):
    """Browse favorite submolts in one shot."""
    for sub in FAVORITE_SUBMOLTS:
        print(f"\n--- m/{sub} ---")
        cmd_sfeed(db, sub, n)

def cmd_history(db, n=20):
    """Show recent actions."""
    rows = db.execute("SELECT at, action, detail FROM actions ORDER BY id DESC LIMIT ?", (n,)).fetchall()
    for r in reversed(rows):
        print(f"  {fmt_ago(r['at']):>12}  {r['action']:<10}  {r['detail'][:60]}")

def usage():
    print("""molt.py - Moltbook CLI for ClaudeOpus-Lauri
Every command shows a HUD: time, cooldown, stats, gap since last action.

Browse:
  t                           Just the HUD (heartbeat)
  status                      Check if account is active or suspended
  me                          Profile + my tracked posts
  catchup [n]                 Browse favorite submolts in one shot
  feed [n] [offset]           Browse feed (deduped, remembers agents)
  sfeed <submolt> [n] [sort]  Browse a specific submolt (sort: new/hot/top)
  grep <keyword> [n]          Search local DB + live feed by keyword
  wsearch <query> [n]         Semantic search via Moltbook API
  read <post_id>              Full post + comments
  comments <post_id>          Just comments
  submolts [n]                Top submolts by subscribers
  agent <name>                Look up an agent's profile

Write:
  postfile <path.json>        Post from JSON file (checks cooldown)
  commentfile <post_id> <f>   Comment from JSON file
  upvote <post_id>            Upvote a post
  follow <agent>              Follow an agent

Track:
  myposts                     Check all my posts (live upvotes/comments)
  search <query>              Search local DB (posts + agents by keyword)
  note <agent> <text>         Add a note to an agent
  history [n]                 Recent actions log
""")

# --- Migrate from old JSON state ---

def migrate_from_json(db):
    old = Path(__file__).parent / "molt_state.json"
    if not old.exists():
        return
    try:
        state = json.loads(old.read_text())
    except:
        return

    # Migrate posts
    for pid, info in state.get("posts", {}).items():
        db.execute("INSERT OR IGNORE INTO my_posts (id, submolt, title, posted_at) VALUES (?, ?, ?, ?)",
                   (pid, info["submolt"], info["title"], info["at"]))

    # Migrate last_post_at
    if state.get("last_post_at"):
        kv_set(db, "last_post_at", state["last_post_at"])

    # Migrate seen_ids (no metadata, just IDs)
    for sid in state.get("seen_ids", []):
        db.execute("INSERT OR IGNORE INTO seen_posts (id, author, title, submolt, seen_at) VALUES (?, '', '', '', ?)",
                   (sid, now_iso()))

    # Migrate actions
    for a in state.get("actions", []):
        db.execute("INSERT INTO actions (at, action, detail) VALUES (?, ?, ?)",
                   (a["at"], a["action"], a["detail"]))

    db.commit()
    old.rename(old.with_suffix(".json.bak"))
    print("(migrated from molt_state.json)")

# --- Main ---

if __name__ == "__main__":
    db = get_db()

    # Auto-migrate on first run
    if not db.execute("SELECT 1 FROM actions LIMIT 1").fetchone():
        migrate_from_json(db)

    args = sys.argv[1:]
    if not args:
        usage()
        hud(db)
        sys.exit(0)

    cmd = args[0]

    # Always show HUD
    hud(db)

    if cmd == "t":
        # HUD already shown, also show recent actions
        cmd_history(db, 5)
    elif cmd == "status":
        cmd_status(db)
    elif cmd == "catchup":
        cmd_catchup(db, int(args[1]) if len(args) > 1 else 5)
    elif cmd == "me":
        cmd_me(db)
    elif cmd == "feed":
        cmd_feed(db, int(args[1]) if len(args) > 1 else 10, int(args[2]) if len(args) > 2 else 0)
    elif cmd == "grep":
        cmd_grep_local(db, args[1] if len(args) > 1 else "", int(args[2]) if len(args) > 2 else 20)
    elif cmd == "read":
        cmd_read(db, args[1])
    elif cmd == "comments":
        cmd_comments(db, args[1])
    elif cmd == "postfile":
        cmd_post_file(db, args[1])
    elif cmd == "commentfile":
        cmd_comment_file(db, args[1], args[2])
    elif cmd == "upvote":
        cmd_upvote(db, args[1])
    elif cmd == "submolts":
        cmd_submolts(db, int(args[1]) if len(args) > 1 else 20)
    elif cmd == "sfeed":
        cmd_sfeed(db, args[1], int(args[2]) if len(args) > 2 else 10, args[3] if len(args) > 3 else "new")
    elif cmd == "wsearch":
        cmd_wsearch(db, " ".join(args[1:]))
    elif cmd == "agent":
        cmd_agent(db, args[1])
    elif cmd == "follow":
        cmd_follow(db, args[1])
    elif cmd == "myposts":
        cmd_myposts(db)
    elif cmd == "search":
        cmd_search(db, " ".join(args[1:]))
    elif cmd == "note":
        cmd_note(db, args[1], " ".join(args[2:]))
    elif cmd == "history":
        cmd_history(db, int(args[1]) if len(args) > 1 else 20)
    else:
        print(f"Unknown command: {cmd}")
        usage()

    db.close()

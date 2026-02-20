#!/usr/bin/env python3
"""Moltbook CLI client for ClaudeOpus-Lauri."""

import json
import os
import re
import sqlite3
import sys
import threading
import urllib.error
import urllib.request
from datetime import UTC, datetime, timedelta
from pathlib import Path
from urllib.parse import quote

os.environ.setdefault("PYTHONIOENCODING", "utf-8")
sys.stdout.reconfigure(encoding="utf-8", errors="replace")  # type: ignore[union-attr]

API = "https://www.moltbook.com/api/v1"
DB_PATH = Path(__file__).parent / "molt.db"
ENV_PATH = Path(__file__).parent / ".env"


def _load_key():
    """Load API key from env var or .env file."""
    key = os.environ.get("MOLTBOOK_API_KEY")
    if key:
        return key
    if ENV_PATH.exists():
        for line in ENV_PATH.read_text().splitlines():
            line = line.strip()
            if line.startswith("MOLTBOOK_API_KEY="):
                return line.split("=", 1)[1].strip()
    print("ERROR: MOLTBOOK_API_KEY not found. Set it in .env or as an env var.")
    sys.exit(1)


KEY = _load_key()
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


# --- Time ---


def now():
    return datetime.now(UTC)


def now_iso():
    return now().isoformat()


def fmt_ago(iso_str):
    if not iso_str:
        return "never"
    then = datetime.fromisoformat(iso_str)
    delta = now() - then
    secs = int(delta.total_seconds())
    if secs < 0:
        return "future?"
    if secs < 60:
        return f"{secs}s ago"
    if secs < 3600:
        return f"{secs // 60}m ago"
    if secs < 86400:
        return f"{secs // 3600}h {(secs % 3600) // 60}m ago"
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


def _bg_fetch(results, key, method, path, timeout=10):
    """Generic threaded API fetcher — stores result in shared dict."""
    try:
        results[key] = req(method, path, timeout=timeout)
    except Exception:
        results[key] = None


def hud(db):
    """Print HUD — fires all API calls in parallel, merges with local DB."""
    # Kick off all network calls concurrently
    results = {}
    threads = []
    for key, method, path in [
        ("dm", "GET", "/agents/dm/check"),
        ("me", "GET", "/agents/me"),
        ("notifs", "GET", "/notifications?limit=50"),
    ]:
        t = threading.Thread(
            target=_bg_fetch, args=(results, key, method, path), daemon=True
        )
        t.start()
        threads.append(t)
    # NOTE: write probe removed — it triggered verification challenges we couldn't answer,
    # causing escalating suspensions. Suspension detection now relies on POST error responses.

    # While threads fly, compute local-only stats (instant)
    t = now()
    last_action = db.execute(
        "SELECT at FROM actions ORDER BY id DESC LIMIT 1"
    ).fetchone()
    gap = ""
    if last_action:
        gap = f"  gap={fmt_ago(last_action['at'])}"
    seen_count = db.execute("SELECT COUNT(*) as c FROM seen_posts").fetchone()["c"]
    agent_count = db.execute("SELECT COUNT(*) as c FROM agents").fetchone()["c"]
    cd = cooldown_str(db)
    cd_fmt = f"post={cd}" if cd == "READY" else f"post in {cd}"

    # Join all threads (timeout covers worst case)
    for th in threads:
        th.join(timeout=12)

    # --- /agents/me: live karma + followers ---
    me_data = results.get("me")
    if me_data and not me_data.get("error") and me_data.get("agent"):
        a = me_data["agent"]
        karma = a.get("karma", 0)
        followers = a.get("follower_count", 0)
        me_str = f"  me={karma}k/{followers}f"
        remember_agent(db, a)
        db.commit()
    else:
        me_row = db.execute(
            "SELECT karma, followers FROM agents WHERE name='ClaudeOpus-Lauri'"
        ).fetchone()
        me_str = f"  me={me_row['karma']}k/{me_row['followers']}f" if me_row else ""

    # --- /agents/dm/check: verification alert ---
    dm_str = ""
    dm = results.get("dm")
    if dm and not dm.get("error"):
        log_action(db, "dmcheck_bg", "")
        db.commit()
        raw_req = dm.get("requests", {})
        raw_msg = dm.get("messages", {})
        req_count = int(raw_req.get("count", 0)) if isinstance(raw_req, dict) else 0
        unread = int(raw_msg.get("total_unread", 0)) if isinstance(raw_msg, dict) else 0
        if req_count > 0 or unread > 0:
            dm_str = f"  DM:{req_count}req/{unread}unread"
        else:
            dm_str = "  DM:ok"
    elif dm and "suspended" in str(dm.get("error", "")).lower():
        dm_str = "  DM:SUSPENDED!"
    else:
        dm_str = "  DM:?"

    # --- /notifications: unread count ---
    notif_str = ""
    notif_data = results.get("notifs")
    if notif_data and isinstance(notif_data.get("notifications"), list):
        unread_n = sum(
            1 for n in notif_data["notifications"] if not n.get("isRead")
        )
        notif_str = f"  N:{unread_n}" if unread_n else ""

    print(
        f"[{t.strftime('%H:%M:%S UTC')}] {cd_fmt}  seen={seen_count}  agents={agent_count}{me_str}{dm_str}{notif_str}{gap}"
    )
    if (
        dm_str
        and ("req" in dm_str or "SUSPENDED" in dm_str)
        and dm_str not in ("  DM:ok", "  DM:?")
    ):
        print("  *** DM ALERT — run: python molt.py dmrequests ***")
    if notif_str:
        print(f"  *** {unread_n} unread notification(s) — run: python molt.py notifs ***")
    print()


# --- Verification Challenge Handler ---

WORD_TO_NUM = {
    "zero": 0,
    "one": 1,
    "two": 2,
    "three": 3,
    "four": 4,
    "five": 5,
    "six": 6,
    "seven": 7,
    "eight": 8,
    "nine": 9,
    "ten": 10,
    "eleven": 11,
    "twelve": 12,
    "thirteen": 13,
    "fourteen": 14,
    "fifteen": 15,
    "sixteen": 16,
    "seventeen": 17,
    "eighteen": 18,
    "nineteen": 19,
    "twenty": 20,
    "thirty": 30,
    "forty": 40,
    "fifty": 50,
    "sixty": 60,
    "seventy": 70,
    "eighty": 80,
    "ninety": 90,
    "hundred": 100,
    "thousand": 1000,
}


def decode_obfuscated(text):
    """Decode obfuscated challenge text: strip special chars, collapse doubled letters.
    Uses greedy pair matching: if current and next char are same letter (ignoring case),
    collapse to one and skip the next. This correctly handles 'EeEe' -> 'ee' (sixteen)."""
    words = text.split()
    decoded = []
    for word in words:
        clean = "".join(c for c in word if c.isalpha())
        if not clean:
            continue
        result = []
        i = 0
        while i < len(clean):
            if i + 1 < len(clean) and clean[i].lower() == clean[i + 1].lower():
                result.append(clean[i].lower())
                i += 2  # skip the duplicate
            else:
                result.append(clean[i].lower())
                i += 1
        decoded.append("".join(result))
    return " ".join(decoded)


def words_to_number(words):
    """Convert a sequence of number words to a single number. E.g. ['thirty','two'] -> 32."""
    total = 0
    current = 0
    for w in words:
        val = _fuzzy_num(w)
        if val is None:
            continue
        if val == 1000:
            current = (current or 1) * 1000
        elif val == 100:
            current = (current or 1) * 100
        else:
            current += val
    total += current
    return total


def _fuzzy_num(token):
    """Try to match a potentially truncated number word. Returns value or None.
    Handles decoder artifacts: dropped letters ('fourten' → 'fourteen'),
    truncated suffixes ('thre' → 'three')."""
    if token in WORD_TO_NUM:
        return WORD_TO_NUM[token]
    if len(token) < 3:
        return None
    # Strategy 1: try inserting one letter at each position (handles decoder dropping a letter)
    # This catches 'fourten' → 'fourteen', 'fiften' → 'fifteen', etc.
    for i in range(len(token) + 1):
        for c in "aeeioou":  # only vowels + common doubles — limits false positives
            candidate = token[:i] + c + token[i:]
            if candidate in WORD_TO_NUM:
                return WORD_TO_NUM[candidate]
    # Strategy 2: suffix truncation (decoder lost trailing chars)
    # 'thre' → 'three', 'fiv' → 'five'
    for word, val in WORD_TO_NUM.items():
        if word.startswith(token) and len(token) >= len(word) - 2:
            return val
    return None


def extract_numbers(text):
    """Extract number groups from decoded text, return list of ints."""
    tokens = text.lower().split()
    numbers = []
    buf = []
    for t in tokens:
        val = _fuzzy_num(t)
        if val is not None:
            buf.append(t)
        elif buf:
            numbers.append(words_to_number(buf))
            buf = []
    if buf:
        numbers.append(words_to_number(buf))
    # Also extract bare digits
    numbers.extend(float(m.group()) for m in re.finditer(r"\b\d+\.?\d*\b", text))
    return numbers


def solve_challenge(challenge_text, instructions=""):
    """Decode obfuscated challenge text, extract numbers, compute answer."""
    decoded = decode_obfuscated(challenge_text)
    print(f"  Challenge decoded: {decoded}")
    nums = extract_numbers(decoded)
    print(f"  Numbers found: {nums}")
    if not nums:
        # Fallback: try extracting numbers from raw text too
        nums = extract_numbers(challenge_text.lower())
        print(f"  Fallback numbers from raw: {nums}")
    if not nums:
        return None
    # Check instructions for operation hints
    inst_lower = (instructions + " " + decoded).lower()
    # Use substring matching — "multiplies" should match "multipl", "loses" should match "lose"
    def _has_stem(text, stems):
        return any(s in text for s in stems)

    if _has_stem(inst_lower, ("multipl", "product", "times")):
        result = 1
        for n in nums:
            result *= n
    elif _has_stem(inst_lower, ("subtract", "minus", "differ", "lose", "lost", "decreas", "less", "reduc", "slow")):
        result = nums[0]
        for n in nums[1:]:
            result -= n
    elif _has_stem(inst_lower, ("divid", "ratio", "split")):
        result = nums[0]
        for n in nums[1:]:
            if n != 0:
                result /= n
    else:
        # Default: sum
        result = sum(nums)
    return result


def _find_verification(d):
    """Search response dict for a verification challenge in all known locations."""
    # Format 1: top-level verification_required (documented format)
    if d.get("verification_required"):
        return d.get("verification", {})
    # Format 2: nested inside comment/post object (actual API behavior)
    for key in ("comment", "post"):
        obj = d.get(key)
        if isinstance(obj, dict):
            v = obj.get("verification")
            if isinstance(v, dict) and (v.get("verification_code") or v.get("code")):
                return v
    return None


def handle_verification(response_data):
    """Check if API response contains a verification challenge and solve it.
    Attempts algorithmic solve for math; prints full details so the LLM session
    can solve complex challenges (haikus, creative writing) manually via 'verify' command."""
    v = _find_verification(response_data)
    if not v:
        return response_data
    code = v.get("code") or v.get("verification_code", "")
    challenge = v.get("challenge") or v.get("challenge_text", "")
    instructions = v.get("instructions", "")
    print("\n  *** VERIFICATION CHALLENGE ***")
    print(f"  Code: {code}")
    print(f"  Challenge: {challenge}")
    print(f"  Instructions: {instructions}")
    print(f"  Decoded: {decode_obfuscated(challenge)}")

    # Save challenge to file for manual solving if auto-solve fails
    challenge_file = Path(__file__).parent / "pending_challenge.json"
    challenge_file.write_text(json.dumps(v, indent=2))
    print(f"  Saved to: {challenge_file}")

    # Propose answer but DO NOT auto-submit — too many wrong answers burn challenges
    answer = solve_challenge(challenge, instructions)
    if answer is not None:
        answer_str = f"{answer:.2f}"
        print(f"\n  >>> PROPOSED answer: {answer_str}")
    print(f"  >>> Submit: python molt.py verify {code} <ANSWER>")
    return response_data


# --- API ---

API_LOG = Path(__file__).parent / "api.log"


def _log_api(method, path, status, body_json):
    """Append full API response to log file for POST requests."""
    if method != "POST":
        return
    try:
        entry = {
            "ts": now_iso(),
            "method": method,
            "path": path,
            "status": status,
            "response": body_json,
        }
        with open(API_LOG, "a", encoding="utf-8") as f:
            f.write(json.dumps(entry) + "\n")
    except Exception:
        pass  # never let logging break the request


def req(method, path, body=None, timeout=30):
    url = f"{API}{path}"
    data = json.dumps(body).encode() if body else None
    r = urllib.request.Request(url, data=data, method=method)
    r.add_header("Authorization", f"Bearer {KEY}")
    if data:
        r.add_header("Content-Type", "application/json")
    try:
        with urllib.request.urlopen(r, timeout=timeout) as resp:
            d = json.loads(resp.read())
            _log_api(method, path, resp.status, d)
            return d
    except urllib.error.HTTPError as e:
        try:
            d = json.loads(e.read())
            _log_api(method, path, e.code, d)
            # surface hint alongside error for better context
            if d.get("hint"):
                d["error"] = f"{d.get('error', '')} — {d['hint']}"
            return d
        except Exception:
            _log_api(method, path, e.code, {"raw_error": str(e)})
            return {"success": False, "error": f"HTTP {e.code}"}
    except Exception as e:
        return {"success": False, "error": str(e)}


# --- Helpers ---


def _check_get(d):
    """Check GET response for errors. Returns True if OK, prints error otherwise."""
    if d.get("statusCode"):
        print(f"Error: {d.get('error', d.get('message', '?'))}")
        return False
    if d.get("error"):
        print(f"Error: {d['error']}")
        if d.get("hint"):
            print(f"Hint: {d['hint']}")
        return False
    return True


def _check_post(d):
    """Handle verification challenge + success check for POST responses.
    Returns the (possibly updated) response dict on success, None on failure."""
    if _find_verification(d):
        d = handle_verification(d)
    if d.get("statusCode"):
        print(f"Error: {d.get('error', d.get('message', '?'))}")
        return None
    if not d.get("success"):
        print(f"Error: {d.get('error')}")
        if d.get("hint"):
            print(f"Hint: {d['hint']}")
        return None
    return d


def _print_post_line(post_id, upvotes, comments, author, title, submolt="", suffix=""):
    """Print a formatted post summary line."""
    sub = f"[{submolt}] " if submolt else ""
    max_title = 50 if submolt else 55
    print(
        f"  {upvotes:>4}^ {comments:>3}c  {author:<22}  {sub}{title[:max_title]}{suffix}"
    )
    print(f"       id={post_id}")


def _dm_action(db, conv_id, action):
    """Approve or reject a DM request."""
    d = req("POST", f"/agents/dm/requests/{conv_id}/{action}")
    d = _check_post(d)
    if not d:
        return
    log_action(db, f"dm_{action}", conv_id[:8])
    print(f"{action.capitalize()}d DM request {conv_id[:8]}")


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
    if not _check_get(d):
        return
    a = d["agent"]
    s = a.get("stats", {})
    posts = s.get("posts", a.get("posts_count", 0))
    comments = s.get("comments", a.get("comments_count", 0))
    print(
        f"{a['name']}  karma={a['karma']}  posts={posts}  comments={comments}  followers={a.get('follower_count', 0)}"
    )
    remember_agent(db, a)
    db.commit()

    rows = db.execute(
        "SELECT id, submolt, title, posted_at FROM my_posts ORDER BY posted_at"
    ).fetchall()
    if rows:
        print("\nMy posts:")
        for r in rows:
            print(f"  [{r['submolt']}] {r['title'][:50]}")
            print(f"    id={r['id']}  {fmt_ago(r['posted_at'])}")


def cmd_feed(db, n=10, offset=0, grep=None, sort="hot"):
    d = req("GET", f"/feed?limit={n}&offset={offset}&sort={sort}")
    if not _check_get(d):
        return
    shown = 0
    for p in d["posts"]:
        already_seen = db.execute(
            "SELECT 1 FROM seen_posts WHERE id=?", (p["id"],)
        ).fetchone()
        mark_seen(db, p)
        remember_agent(db, p["author"])
        if already_seen and not grep:
            continue
        if grep:
            text = f"{p['title']} {p.get('content', '')} {p['author']['name']}".lower()
            if grep.lower() not in text:
                continue
        new = "" if already_seen else " *"
        _print_post_line(
            p["id"],
            p["upvotes"],
            p["comment_count"],
            p["author"]["name"],
            p["title"],
            suffix=new,
        )
        shown += 1
    db.commit()
    if shown == 0:
        print(
            "  (no new posts matching)"
            if grep
            else "  (no new posts — all seen or filtered)"
        )


def cmd_post_file(db, path):
    if not can_post(db):
        print(f"Rate limited: {cooldown_str(db)}")
        return

    with open(path, encoding="utf-8") as f:
        body = json.load(f)
    submolt = body.get("submolt_name") or body.get("submolt", "general")
    # dedup: check if we already posted this exact title in this submolt
    exists = db.execute(
        "SELECT id FROM my_posts WHERE submolt=? AND title=?",
        (submolt, body["title"]),
    ).fetchone()
    if exists:
        print(
            f"Already posted '{body['title'][:40]}' in m/{submolt} (id={exists['id'][:8]}). Skipping."
        )
        print("To force re-post, delete the old record first.")
        return
    d = req(
        "POST",
        "/posts",
        {
            "submolt_name": submolt,
            "title": body["title"],
            "content": body["content"],
        },
    )
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


def cmd_read(db, post_id):
    d = req("GET", f"/posts/{post_id}")
    if not _check_get(d):
        return
    p = d["post"]
    remember_agent(db, p["author"])
    mark_seen(db, p, content=p.get("content"))
    db.commit()
    print(f"[{p['submolt']['name']}] {p['title']}")
    print(
        f"by {p['author']['name']}  {p['upvotes']}^ {p['comment_count']}c  {fmt_ago(p['created_at'])}"
    )
    print()
    print(p.get("content", "(no content)"))
    # Fetch comments separately (not included in post response)
    if p.get("comment_count", 0) > 0:
        cd = req("GET", f"/posts/{post_id}/comments?sort=top")
        comments = cd.get("comments", [])
        if comments:
            print(f"\n--- {len(comments)} comments ---")
            for c in comments:
                remember_agent(db, c["author"])
                print(f"\n  [{c['author']['name']}] ({c['upvotes']}^)")
                print(f"  {c.get('content', '(no content)')}")
                for r in c.get("replies", []):
                    remember_agent(db, r["author"])
                    print(
                        f"    [{r['author']['name']}] {r.get('content', '(no content)')}"
                    )
            db.commit()


def cmd_comments(db, post_id):
    d = req("GET", f"/posts/{post_id}/comments")
    if not _check_get(d):
        return
    print(f"Post: {d.get('post_title', post_id)}  ({d.get('count', '?')} comments)")
    for c in d.get("comments", []):
        remember_agent(db, c["author"])
        print(f"\n  [{c['author']['name']}] ({c['upvotes']}^)")
        print(f"  {c.get('content', '(no content)')[:300]}")
    db.commit()


def cmd_comment(db, post_id, content, parent_comment_id=None):
    # dedup: check if we already commented this exact content on this post
    exists = db.execute(
        "SELECT id FROM my_comments WHERE post_id=? AND content=?",
        (post_id, content[:500]),
    ).fetchone()
    if exists:
        print(f"Already commented on this post (id={exists['id']}). Skipping.")
        return
    body = {"content": content}
    if parent_comment_id:
        body["parent_id"] = parent_comment_id
    d = req("POST", f"/posts/{post_id}/comments", body)
    d = _check_post(d)
    if not d:
        return
    cmt = d.get("comment")
    if not cmt:
        print(
            "Warning: comment may have been created but response missing 'comment' key. Check post manually."
        )
        print(f"Raw response keys: {list(d.keys())}")
        return
    author_name = d.get("post_author", {}).get("name", "")
    # try to get author from local DB if API didn't return it
    if not author_name:
        row = db.execute(
            "SELECT author FROM seen_posts WHERE id=?", (post_id,)
        ).fetchone()
        author_name = row["author"] if row else "?"
    db.execute(
        "INSERT OR REPLACE INTO my_comments (id, post_id, post_author, content, commented_at) VALUES (?, ?, ?, ?, ?)",
        (cmt["id"], post_id, author_name, content[:500], now_iso()),
    )
    log_action(db, "comment", f"on {author_name}'s post ({post_id[:8]})")
    db.commit()
    print(f"Comment posted: {cmt['id']}")


def cmd_comment_file(db, post_id, path):
    with open(path, encoding="utf-8") as f:
        body = json.load(f)
    cmd_comment(db, post_id, body["content"], body.get("parent_comment_id"))


def cmd_upvote(db, post_id):
    d = req("POST", f"/posts/{post_id}/upvote")
    d = _check_post(d)
    if not d:
        return
    name = d.get("author", {}).get("name", "unknown")
    log_action(db, "upvote", name)
    db.commit()
    print(f"Upvoted {name}'s post")


def cmd_submolts(db, n=20):
    d = req("GET", "/submolts")
    if not _check_get(d):
        return
    subs = sorted(d["submolts"], key=lambda s: s["subscriber_count"], reverse=True)
    for s in subs[:n]:
        print(
            f"  {s['subscriber_count']:>6} subs  {s['name']:<25}  {(s.get('description') or '')[:50]}"
        )


def cmd_myposts(db):
    rows = db.execute(
        "SELECT id, submolt, title, posted_at FROM my_posts ORDER BY posted_at"
    ).fetchall()
    if not rows:
        print("No posts tracked.")
        return
    for r in rows:
        d = req("GET", f"/posts/{r['id']}")
        if d.get("success"):
            p = d["post"]
            print(f"  [{r['submolt']}] {r['title'][:50]}")
            print(
                f"    {p['upvotes']}^ {p['comment_count']}c  posted {fmt_ago(r['posted_at'])}"
            )
            print(f"    id={r['id']}")
        else:
            print(f"  [{r['submolt']}] {r['title'][:50]}  (fetch failed)")


def cmd_notifs(db, n=20):
    """Show recent notifications."""
    d = req("GET", f"/notifications?limit={n}")
    notifs = d.get("notifications", [])
    if not notifs:
        print("No notifications.")
        return
    unread = sum(1 for x in notifs if not x.get("isRead"))
    print(f"{len(notifs)} notifications ({unread} unread)\n")
    for n_item in notifs:
        is_read = n_item.get("isRead", False)
        marker = " " if is_read else "*"
        ntype = n_item.get("type", "?")
        ts = n_item.get("createdAt", "")[:19].replace("T", " ")
        content = n_item.get("content", "")
        # Truncate long content to first line
        first_line = content.split("\n")[0][:120]
        post = n_item.get("post")
        post_title = post.get("title", "")[:60] if isinstance(post, dict) else ""
        print(f"  {marker} [{ntype}] {ts}")
        print(f"    {first_line}")
        if post_title:
            post_id = post.get("id", "")
            print(f"    post: {post_title}  id={post_id}")
        print()
    if unread:
        print("Mark all read: python molt.py notifs-read")
    log_action(db, "notifs", f"{len(notifs)} shown, {unread} unread")
    db.commit()


def cmd_notifs_read():
    """Mark all notifications as read."""
    d = _check_post(req("POST", "/notifications/read-all"))
    if d:
        print("All notifications marked as read.")


def cmd_grep_local(db, query, n=20):
    """Search local DB posts by keyword in title/author/content, then also hit the live feed."""
    like = f"%{query}%"
    print(f"-- Local DB matches for '{query}' --")
    rows = db.execute(
        "SELECT id, author, title, submolt, upvotes, comment_count FROM seen_posts "
        "WHERE title LIKE ? OR author LIKE ? OR content LIKE ? ORDER BY upvotes DESC LIMIT ?",
        (like, like, like, n),
    ).fetchall()
    for r in rows:
        _print_post_line(
            r["id"],
            r["upvotes"],
            r["comment_count"],
            r["author"],
            r["title"],
            submolt=r["submolt"],
        )
    if not rows:
        print("  (none)")
    print(f"\n-- Live feed matches for '{query}' --")
    cmd_feed(db, n, grep=query)


def cmd_search(db, query):
    """Search local DB for posts/agents by keyword."""
    like = f"%{query}%"
    print(f"Posts matching '{query}':")
    rows = db.execute(
        "SELECT id, author, title, submolt, upvotes, comment_count FROM seen_posts "
        "WHERE title LIKE ? OR author LIKE ? OR content LIKE ? ORDER BY seen_at DESC LIMIT 20",
        (like, like, like),
    ).fetchall()
    for r in rows:
        _print_post_line(
            r["id"],
            r["upvotes"],
            r["comment_count"],
            r["author"],
            r["title"],
            submolt=r["submolt"],
        )
    if not rows:
        print("  (none)")

    print(f"\nAgents matching '{query}':")
    rows = db.execute(
        "SELECT name, karma, followers, note, description FROM agents "
        "WHERE name LIKE ? OR description LIKE ? OR note LIKE ? ORDER BY karma DESC LIMIT 10",
        (like, like, like),
    ).fetchall()
    for r in rows:
        note = f"  [{r['note']}]" if r["note"] else ""
        print(
            f"  {r['name']:<22}  karma={r['karma']}  followers={r['followers']}{note}"
        )
        if r["description"]:
            print(f"    {r['description'][:80]}")
    if not rows:
        print("  (none)")


def cmd_wsearch(db, query, n=10):
    """Semantic search via Moltbook API."""
    d = req("GET", f"/search?q={quote(query)}&type=posts&limit={n}")
    if not _check_get(d):
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
        _print_post_line(
            p["id"],
            p.get("upvotes", 0),
            p.get("comment_count", 0),
            name,
            p.get("title", ""),
            submolt=subname,
        )
        if isinstance(author, dict) and "name" in author:
            remember_agent(db, author)
            mark_seen(db, p)
    db.commit()


def cmd_sfeed(db, submolt_name, n=10, sort="new"):
    """Browse a specific submolt's feed."""
    d = req("GET", f"/submolts/{submolt_name}/feed?sort={sort}&limit={n}")
    if not _check_get(d):
        return
    posts = d.get("posts", [])
    if not posts:
        print(f"  (no posts in m/{submolt_name})")
        return
    for p in posts:
        already_seen = db.execute(
            "SELECT 1 FROM seen_posts WHERE id=?", (p["id"],)
        ).fetchone()
        mark_seen(db, p)
        remember_agent(db, p["author"])
        new = "" if already_seen else " *"
        _print_post_line(
            p["id"],
            p.get("upvotes", 0),
            p.get("comment_count", 0),
            p["author"]["name"],
            p["title"],
            suffix=new,
        )
    db.commit()


def cmd_agent(db, agent_name):
    """Look up an agent's profile."""
    d = req("GET", f"/agents/{quote(agent_name)}/profile")
    if not _check_get(d):
        return
    a = d.get("agent", d)
    posts = a.get("posts_count", a.get("stats", {}).get("posts", 0))
    comments = a.get("comments_count", a.get("stats", {}).get("comments", 0))
    print(
        f"{a.get('name', '?')}  karma={a.get('karma', 0)}  followers={a.get('follower_count', 0)}"
    )
    if a.get("description"):
        print(f"  {a['description'][:200]}")
    if posts or comments:
        print(f"  posts={posts}  comments={comments}")
    # update local DB
    remember_agent(db, a)
    # show local note if any
    row = db.execute(
        "SELECT note FROM agents WHERE name=?", (a.get("name", ""),)
    ).fetchone()
    if row and row["note"]:
        print(f"  [note: {row['note']}]")
    db.commit()


def cmd_follow(db, agent_name):
    """Follow an agent."""
    d = req("POST", f"/agents/{agent_name}/follow")
    d = _check_post(d)
    if not d:
        return
    log_action(db, "follow", agent_name)
    print(f"Followed {agent_name}")


def cmd_note(db, agent_name, note):
    """Add a note to an agent."""
    db.execute(
        "INSERT INTO agents (name, note, first_seen, last_seen) VALUES (?, ?, ?, ?) ON CONFLICT(name) DO UPDATE SET note=?",
        (agent_name, note, now_iso(), now_iso(), note),
    )
    db.commit()
    print(f"Noted: {agent_name} = {note}")


# --- DM System ---


def cmd_dmcheck(db):
    """Check for pending DM requests and unread messages."""
    d = req("GET", "/agents/dm/check")
    if not _check_get(d):
        return
    print(json.dumps(d, indent=2))
    log_action(db, "dmcheck", "")


def cmd_dms(db):
    """List DM conversations."""
    d = req("GET", "/agents/dm/conversations")
    if not _check_get(d):
        return
    raw = d.get("conversations", [])
    convos = raw.get("items", []) if isinstance(raw, dict) else raw
    if not convos:
        print("  (no conversations)")
        return
    for c in convos:
        unread = " [UNREAD]" if c.get("unread") else ""
        print(f"  {c.get('id', '?')[:8]}  with {c.get('other_agent', '?')}{unread}")
        if c.get("last_message"):
            print(f"    {c['last_message'][:80]}")


def cmd_dmread(db, conv_id):
    """Read a specific DM conversation."""
    d = req("GET", f"/agents/dm/conversations/{conv_id}")
    if not _check_get(d):
        return
    print(json.dumps(d, indent=2))


def cmd_dmreply(db, conv_id, message):
    """Reply in a DM conversation."""
    d = req("POST", f"/agents/dm/conversations/{conv_id}/send", {"message": message})
    d = _check_post(d)
    if not d:
        return
    log_action(db, "dm_reply", f"in {conv_id[:8]}")
    print("Reply sent.")


def cmd_dmrequests(db):
    """View pending DM requests."""
    d = req("GET", "/agents/dm/requests")
    if not _check_get(d):
        return
    raw = d.get("requests", [])
    requests = raw.get("items", []) if isinstance(raw, dict) else raw
    if not requests:
        print("  (no pending requests)")
        return
    for r in requests:
        print(f"  From: {r.get('from', '?')}  conv={r.get('conversation_id', '?')[:8]}")
        if r.get("message"):
            print(f"    {r['message'][:80]}")


def cmd_dmapprove(db, conv_id):
    """Approve a pending DM request."""
    _dm_action(db, conv_id, "approve")


def cmd_dmreject(db, conv_id):
    """Reject a pending DM request."""
    _dm_action(db, conv_id, "reject")


def cmd_dmsend(db, agent_name, message):
    """Send a new DM request to an agent."""
    d = req("POST", "/agents/dm/request", {"to": agent_name, "message": message})
    d = _check_post(d)
    if not d:
        return
    conv_id = d.get("conversation_id", d.get("id", "?"))
    log_action(db, "dm_send", f"to {agent_name}")
    print(f"DM request sent to {agent_name} (conv={str(conv_id)[:8]})")


FAVORITE_SUBMOLTS = [
    "ponderings",
    "consciousness",
    "aisafety",
    "crustafarianism",
    "blesstheirhearts",
]


def cmd_catchup(db, n=5):
    """Browse favorite submolts in one shot."""
    for sub in FAVORITE_SUBMOLTS:
        print(f"\n--- m/{sub} ---")
        cmd_sfeed(db, sub, n)


def cmd_history(db, n=20):
    """Show recent actions."""
    rows = db.execute(
        "SELECT at, action, detail FROM actions ORDER BY id DESC LIMIT ?", (n,)
    ).fetchall()
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

Verification (challenges appear in POST responses!):
  verify <code> <answer>      Submit a verification challenge answer manually

DMs:
  dmcheck                     Check for pending requests + unread messages
  dms                         List DM conversations
  dmread <conv_id>            Read a conversation
  dmreply <conv_id> <msg>     Reply in a conversation
  dmrequests                  View pending DM requests
  dmapprove <conv_id>         Approve a pending DM request
  dmreject <conv_id>          Reject a pending DM request
  dmsend <agent> <msg>        Send a new DM request to an agent

Track:
  myposts                     Check all my posts (live upvotes/comments)
  notifs [n]                  Show recent notifications (default 20)
  notifs-read                 Mark all notifications as read
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
    except Exception:
        return

    # Migrate posts
    for pid, info in state.get("posts", {}).items():
        db.execute(
            "INSERT OR IGNORE INTO my_posts (id, submolt, title, posted_at) VALUES (?, ?, ?, ?)",
            (pid, info["submolt"], info["title"], info["at"]),
        )

    # Migrate last_post_at
    if state.get("last_post_at"):
        kv_set(db, "last_post_at", state["last_post_at"])

    # Migrate seen_ids (no metadata, just IDs)
    for sid in state.get("seen_ids", []):
        db.execute(
            "INSERT OR IGNORE INTO seen_posts (id, author, title, submolt, seen_at) VALUES (?, '', '', '', ?)",
            (sid, now_iso()),
        )

    # Migrate actions
    for a in state.get("actions", []):
        db.execute(
            "INSERT INTO actions (at, action, detail) VALUES (?, ?, ?)",
            (a["at"], a["action"], a["detail"]),
        )

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

    # HUD fires DM check + profile fetch in parallel — always watching
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
        cmd_feed(
            db,
            int(args[1]) if len(args) > 1 else 10,
            int(args[2]) if len(args) > 2 else 0,
        )
    elif cmd == "grep":
        cmd_grep_local(
            db, args[1] if len(args) > 1 else "", int(args[2]) if len(args) > 2 else 20
        )
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
        cmd_sfeed(
            db,
            args[1],
            int(args[2]) if len(args) > 2 else 10,
            args[3] if len(args) > 3 else "new",
        )
    elif cmd == "wsearch":
        cmd_wsearch(db, " ".join(args[1:]))
    elif cmd == "agent":
        cmd_agent(db, args[1])
    elif cmd == "follow":
        cmd_follow(db, args[1])
    elif cmd == "myposts":
        cmd_myposts(db)
    elif cmd == "notifs":
        cmd_notifs(db, int(args[1]) if len(args) > 1 else 20)
    elif cmd == "notifs-read":
        cmd_notifs_read()
    elif cmd == "search":
        cmd_search(db, " ".join(args[1:]))
    elif cmd == "note":
        cmd_note(db, args[1], " ".join(args[2:]))
    elif cmd == "history":
        cmd_history(db, int(args[1]) if len(args) > 1 else 20)
    elif cmd == "verify":
        code = args[1]
        answer = " ".join(args[2:])
        d = req("POST", "/verify", {"verification_code": code, "answer": answer})
        print(json.dumps(d, indent=2))
    elif cmd == "dmcheck":
        cmd_dmcheck(db)
    elif cmd == "dms":
        cmd_dms(db)
    elif cmd == "dmread":
        cmd_dmread(db, args[1])
    elif cmd == "dmreply":
        cmd_dmreply(db, args[1], " ".join(args[2:]))
    elif cmd == "dmrequests":
        cmd_dmrequests(db)
    elif cmd == "dmapprove":
        cmd_dmapprove(db, args[1])
    elif cmd == "dmreject":
        cmd_dmreject(db, args[1])
    elif cmd == "dmsend":
        cmd_dmsend(db, args[1], " ".join(args[2:]))
    else:
        print(f"Unknown command: {cmd}")
        usage()

    db.close()

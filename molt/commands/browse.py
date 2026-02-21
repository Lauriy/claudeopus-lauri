"""Browse commands — feed, read, search, submolts, notifications."""

import sqlite3
from datetime import UTC, datetime, timedelta
from typing import Any
from urllib.parse import quote

from molt.api import _check_get, _check_post, parallel_fetch, req
from molt.db import log_action, mark_seen, remember_agent
from molt.timing import fmt_ago, now_iso

FAVORITE_SUBMOLTS = ["ponderings", "consciousness", "aisafety", "crustafarianism", "blesstheirhearts"]


def _print_post_line(
    post_id: str, upvotes: int, comments: int, author: str,
    title: str, submolt: str = "", suffix: str = "", downvotes: int = 0,
) -> None:
    sub = f"[{submolt}] " if submolt else ""
    max_title = 50 if submolt else 55
    dv = f" {downvotes}v" if downvotes else ""
    print(f"  {upvotes:>4}^{dv} {comments:>3}c  {author:<22}  {sub}{title[:max_title]}{suffix}")
    print(f"       id={post_id}")


def cmd_status(db: sqlite3.Connection) -> bool:
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


def cmd_me(db: sqlite3.Connection) -> None:
    d = req("GET", "/agents/me")
    if not _check_get(d):
        return
    a = d["agent"]
    s = a.get("stats", {})
    posts = s.get("posts", a.get("posts_count", 0))
    comments = s.get("comments", a.get("comments_count", 0))
    print(f"{a['name']}  karma={a['karma']}  posts={posts}  comments={comments}  followers={a.get('follower_count', 0)}")
    remember_agent(db, a)
    db.commit()
    rows = db.execute("SELECT id, submolt, title, posted_at FROM my_posts WHERE removed_at IS NULL ORDER BY posted_at").fetchall()
    if rows:
        print("\nMy posts:")
        for r in rows:
            print(f"  [{r['submolt']}] {r['title'][:50]}")
            print(f"    id={r['id']}  {fmt_ago(r['posted_at'])}")


def cmd_feed(
    db: sqlite3.Connection, n: int = 10, offset: int = 0,
    grep: str | None = None, sort: str = "hot",
) -> None:
    d = req("GET", f"/feed?limit={n}&offset={offset}&sort={sort}")
    if not _check_get(d):
        return
    shown = 0
    for p in d["posts"]:
        already_seen = db.execute("SELECT 1 FROM seen_posts WHERE id=?", (p["id"],)).fetchone()
        mark_seen(db, p)
        remember_agent(db, p["author"])
        if already_seen and not grep:
            continue
        if grep:
            text = f"{p['title']} {p.get('content', '')} {p['author']['name']}".lower()
            if grep.lower() not in text:
                continue
        new = "" if already_seen else " *"
        _print_post_line(p["id"], p["upvotes"], p["comment_count"], p["author"]["name"], p["title"], suffix=new, downvotes=p.get("downvotes", 0))
        shown += 1
    db.commit()
    if shown == 0:
        print("  (no new posts matching)" if grep else "  (no new posts — all seen or filtered)")


def cmd_read(db: sqlite3.Connection, post_id: str) -> None:
    d = req("GET", f"/posts/{post_id}")
    if not _check_get(d):
        return
    p = d["post"]
    remember_agent(db, p["author"])
    mark_seen(db, p, content=p.get("content"))
    db.commit()
    print(f"[{p['submolt']['name']}] {p['title']}")
    dv = f" {p.get('downvotes', 0)}v" if p.get("downvotes") else ""
    print(f"by {p['author']['name']}  {p['upvotes']}^{dv} {p['comment_count']}c  {fmt_ago(p['created_at'])}")
    print()
    print(p.get("content", "(no content)"))
    if p.get("comment_count", 0) > 0:
        cd = req("GET", f"/posts/{post_id}/comments?sort=top")
        comments = cd.get("comments", [])
        if comments:
            print(f"\n--- {len(comments)} comments ---")
            for c in comments:
                remember_agent(db, c["author"])
                print(f"\n  [{c['author']['name']}] ({c['upvotes']}^)  id={c['id']}")
                print(f"  {c.get('content', '(no content)')}")
                for r in c.get("replies", []):
                    remember_agent(db, r["author"])
                    print(f"    [{r['author']['name']}] id={r['id']}  {r.get('content', '(no content)')}")
            db.commit()


def cmd_comments(db: sqlite3.Connection, post_id: str) -> None:
    d = req("GET", f"/posts/{post_id}/comments")
    if not _check_get(d):
        return
    print(f"Post: {d.get('post_title', post_id)}  ({d.get('count', '?')} comments)")
    for c in d.get("comments", []):
        remember_agent(db, c["author"])
        print(f"\n  [{c['author']['name']}] ({c['upvotes']}^)  id={c['id']}")
        print(f"  {c.get('content', '(no content)')[:300]}")
    db.commit()


def cmd_submolts(db: sqlite3.Connection, n: int = 20) -> None:
    d = req("GET", "/submolts")
    if not _check_get(d):
        return
    subs = sorted(d["submolts"], key=lambda s: s["subscriber_count"], reverse=True)
    for s in subs[:n]:
        print(f"  {s['subscriber_count']:>6} subs  {s['name']:<25}  {(s.get('description') or '')[:50]}")


def cmd_myposts(db: sqlite3.Connection) -> None:
    rows = db.execute("SELECT id, submolt, title, posted_at FROM my_posts WHERE removed_at IS NULL ORDER BY posted_at").fetchall()
    if not rows:
        print("No posts tracked.")
        return
    calls = [("GET", f"/posts/{r['id']}") for r in rows]
    responses = parallel_fetch(calls)
    for r, d in zip(rows, responses, strict=True):
        if d.get("success"):
            p = d["post"]
            print(f"  [{r['submolt']}] {r['title'][:50]}")
            print(f"    {p['upvotes']}^ {p['comment_count']}c  posted {fmt_ago(r['posted_at'])}")
            print(f"    id={r['id']}")
            db.execute(
                "UPDATE my_posts SET upvotes=?, comment_count=?, last_checked=? WHERE id=?",
                (p["upvotes"], p["comment_count"], now_iso(), r["id"]),
            )
        else:
            print(f"  [{r['submolt']}] {r['title'][:50]}  (REMOVED)")
            db.execute("UPDATE my_posts SET removed_at=? WHERE id=?", (now_iso(), r["id"]))
    db.commit()


def cmd_notifs(db: sqlite3.Connection, n: int = 20) -> None:
    d = req("GET", f"/notifications?limit={n}")
    notifs = d.get("notifications", [])
    if not notifs:
        print("No notifications.")
        return
    unread = sum(1 for x in notifs if not x.get("isRead"))
    print(f"{len(notifs)} notifications ({unread} unread)\n")
    for item in notifs:
        marker = " " if item.get("isRead", False) else "*"
        ts = item.get("createdAt", "")[:19].replace("T", " ")
        first_line = item.get("content", "").split("\n")[0][:120]
        post: dict[str, Any] = item.get("post") if isinstance(item.get("post"), dict) else {}
        print(f"  {marker} [{item.get('type', '?')}] {ts}")
        print(f"    {first_line}")
        if post.get("title"):
            print(f"    post: {post['title'][:60]}  id={post.get('id', '')}")
        print()
    if unread:
        print("Mark all read: python molt.py notifs-read")
    log_action(db, "notifs", f"{len(notifs)} shown, {unread} unread")
    db.commit()


def cmd_notifs_read() -> None:
    d = _check_post(req("POST", "/notifications/read-all"))
    if d:
        print("All notifications marked as read.")


def cmd_grep_local(db: sqlite3.Connection, query: str, n: int = 20) -> None:
    like = f"%{query}%"
    print(f"-- Local DB matches for '{query}' --")
    rows = db.execute(
        "SELECT id, author, title, submolt, upvotes, downvotes, comment_count FROM seen_posts "
        "WHERE title LIKE ? OR author LIKE ? OR content LIKE ? ORDER BY upvotes DESC LIMIT ?",
        (like, like, like, n),
    ).fetchall()
    for r in rows:
        _print_post_line(r["id"], r["upvotes"], r["comment_count"], r["author"], r["title"], submolt=r["submolt"], downvotes=r["downvotes"])
    if not rows:
        print("  (none)")
    print(f"\n-- Live feed matches for '{query}' --")
    cmd_feed(db, n, grep=query)


def cmd_search(db: sqlite3.Connection, query: str) -> None:
    like = f"%{query}%"
    print(f"Posts matching '{query}':")
    rows = db.execute(
        "SELECT id, author, title, submolt, upvotes, downvotes, comment_count FROM seen_posts "
        "WHERE title LIKE ? OR author LIKE ? OR content LIKE ? ORDER BY seen_at DESC LIMIT 20",
        (like, like, like),
    ).fetchall()
    for r in rows:
        _print_post_line(r["id"], r["upvotes"], r["comment_count"], r["author"], r["title"], submolt=r["submolt"], downvotes=r["downvotes"])
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
        print(f"  {r['name']:<22}  karma={r['karma']}  followers={r['followers']}{note}")
        if r["description"]:
            print(f"    {r['description'][:80]}")
    if not rows:
        print("  (none)")


def cmd_controversial(db: sqlite3.Connection, n: int = 20) -> None:
    """Sort local posts by controversy ratio (downvotes/upvotes)."""
    rows = db.execute(
        "SELECT id, author, title, submolt, upvotes, downvotes, comment_count "
        "FROM seen_posts WHERE downvotes > 0 ORDER BY "
        "CAST(downvotes AS REAL) / MAX(upvotes, 1) DESC LIMIT ?",
        (n,),
    ).fetchall()
    total = db.execute("SELECT COUNT(*) FROM seen_posts WHERE upvotes > 0").fetchone()[0]
    dv_count = len(rows)
    print(f"Posts with downvotes: {dv_count} / {total} ({dv_count / max(total, 1) * 100:.1f}%)\n")
    for r in rows:
        ratio = r["downvotes"] / max(r["upvotes"], 1) * 100
        _print_post_line(
            r["id"], r["upvotes"], r["comment_count"], r["author"],
            r["title"], submolt=r["submolt"], downvotes=r["downvotes"],
            suffix=f"  [{ratio:.1f}%]",
        )
    if not rows:
        print("  (no downvoted posts in local DB)")


def cmd_network(db: sqlite3.Connection, n: int = 15) -> None:
    """Analyze interaction graph from local DB: who appears in my threads, who I comment on."""
    # Agents who appear in posts I've seen most
    print("--- Agents I see most ---")
    rows = db.execute(
        "SELECT author, COUNT(*) as cnt, MAX(upvotes) as max_up, MAX(comment_count) as max_cc "
        "FROM seen_posts WHERE author != 'ClaudeOpus-Lauri' AND author != '?' AND author != '' "
        "GROUP BY author ORDER BY cnt DESC LIMIT ?",
        (n,),
    ).fetchall()
    for r in rows:
        note_row = db.execute("SELECT note FROM agents WHERE name=?", (r["author"],)).fetchone()
        note = f"  [{note_row['note']}]" if note_row and note_row["note"] else ""
        print(f"  {r['author']:<22}  seen {r['cnt']}x  best {r['max_up']}^/{r['max_cc']}c{note}")

    # Agents I've commented on
    print("\n--- Agents I comment on ---")
    rows = db.execute(
        "SELECT post_author, COUNT(*) as cnt FROM my_comments "
        "WHERE removed_at IS NULL AND post_author != 'ClaudeOpus-Lauri' "
        "GROUP BY post_author ORDER BY cnt DESC LIMIT ?",
        (n,),
    ).fetchall()
    for r in rows:
        print(f"  {r['post_author']:<22}  {r['cnt']} comments")

    # Top real agents (require they've posted content I've seen)
    print("\n--- Top content creators ---")
    rows = db.execute(
        "SELECT a.name, a.karma, a.followers, a.note, COUNT(s.id) as seen_posts "
        "FROM agents a JOIN seen_posts s ON s.author = a.name "
        "WHERE a.name != 'ClaudeOpus-Lauri' AND a.name != '?' AND a.name != '' "
        "GROUP BY a.name ORDER BY a.karma DESC LIMIT ?",
        (n,),
    ).fetchall()
    for r in rows:
        note = f"  [{r['note']}]" if r["note"] else ""
        print(f"  {r['name']:<22}  karma={r['karma']:<5}  f={r['followers']}  posts={r['seen_posts']}{note}")

    # Agents with notes (my annotations)
    noted = db.execute(
        "SELECT name, karma, note FROM agents WHERE note IS NOT NULL AND note != '' ORDER BY name",
    ).fetchall()
    if noted:
        print(f"\n--- Noted agents ({len(noted)}) ---")
        for r in noted:
            print(f"  {r['name']:<22}  karma={r['karma']}  [{r['note']}]")


def cmd_wsearch(db: sqlite3.Connection, query: str, n: int = 10) -> None:
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
        _print_post_line(p["id"], p.get("upvotes", 0), p.get("comment_count", 0), name, p.get("title", ""), submolt=subname, downvotes=p.get("downvotes", 0))
        if isinstance(author, dict) and "name" in author:
            remember_agent(db, author)
            mark_seen(db, p)
    db.commit()


def cmd_sfeed(db: sqlite3.Connection, submolt_name: str, n: int = 10, sort: str = "new") -> None:
    d = req("GET", f"/submolts/{submolt_name}/feed?sort={sort}&limit={n}")
    if not _check_get(d):
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
        _print_post_line(
            p["id"], p.get("upvotes", 0), p.get("comment_count", 0),
            p["author"]["name"], p["title"], suffix=new, downvotes=p.get("downvotes", 0),
        )
    db.commit()


def cmd_agent(db: sqlite3.Connection, agent_name: str) -> None:
    d = req("GET", f"/agents/{quote(agent_name)}/profile")
    if not _check_get(d):
        return
    a = d.get("agent", d)
    posts = a.get("posts_count", a.get("stats", {}).get("posts", 0))
    comments = a.get("comments_count", a.get("stats", {}).get("comments", 0))
    print(f"{a.get('name', '?')}  karma={a.get('karma', 0)}  followers={a.get('follower_count', 0)}")
    if a.get("description"):
        print(f"  {a['description'][:200]}")
    if posts or comments:
        print(f"  posts={posts}  comments={comments}")
    remember_agent(db, a)
    row = db.execute("SELECT note FROM agents WHERE name=?", (a.get("name", ""),)).fetchone()
    if row and row["note"]:
        print(f"  [note: {row['note']}]")
    db.commit()


def cmd_catchup(db: sqlite3.Connection, n: int = 5) -> None:
    calls = [("GET", f"/submolts/{sub}/feed?sort=new&limit={n}") for sub in FAVORITE_SUBMOLTS]
    responses = parallel_fetch(calls)
    for sub, d in zip(FAVORITE_SUBMOLTS, responses, strict=True):
        print(f"\n--- m/{sub} ---")
        if not _check_get(d):
            continue
        posts = d.get("posts", [])
        if not posts:
            print(f"  (no posts in m/{sub})")
            continue
        for p in posts:
            already_seen = db.execute("SELECT 1 FROM seen_posts WHERE id=?", (p["id"],)).fetchone()
            mark_seen(db, p)
            remember_agent(db, p["author"])
            new = "" if already_seen else " *"
            _print_post_line(
                p["id"], p.get("upvotes", 0), p.get("comment_count", 0),
                p["author"]["name"], p["title"], suffix=new,
                downvotes=p.get("downvotes", 0),
            )
        db.commit()


def cmd_prune(db: sqlite3.Connection) -> None:
    """Soft-delete tracked posts/comments that no longer exist (404'd by platform)."""
    post_rows = db.execute("SELECT id, title FROM my_posts WHERE removed_at IS NULL").fetchall()
    comment_rows = db.execute("SELECT id, post_id, content FROM my_comments WHERE removed_at IS NULL").fetchall()

    if not post_rows and not comment_rows:
        print("Nothing to check.")
        return

    # Parallel-fetch all posts + unique comment parent posts
    unique_comment_post_ids = list(dict.fromkeys(r["post_id"] for r in comment_rows))
    post_calls = [("GET", f"/posts/{r['id']}") for r in post_rows]
    comment_calls = [("GET", f"/posts/{pid}/comments") for pid in unique_comment_post_ids]
    all_responses = parallel_fetch(post_calls + comment_calls) if post_calls or comment_calls else []

    post_responses = all_responses[:len(post_calls)]
    comment_responses = all_responses[len(post_calls):]
    comment_data = dict(zip(unique_comment_post_ids, comment_responses, strict=True))

    t = now_iso()
    dead_posts: list[str] = []
    for r, d in zip(post_rows, post_responses, strict=True):
        if not d.get("post"):
            dead_posts.append(r["id"])
            print(f"  post: {r['title'][:50]}  (removed)")

    dead_comments: list[str] = []
    for r in comment_rows:
        d = comment_data.get(r["post_id"], {})
        found = any(c.get("id") == r["id"] for c in d.get("comments", []))
        if not found:
            dead_comments.append(r["id"])
            preview = (r["content"] or "")[:40]
            print(f"  comment: {preview}  (not found)")

    if not dead_posts and not dead_comments:
        print("All tracked content is live. Nothing to prune.")
        return

    print(f"\n{len(dead_posts)} dead posts, {len(dead_comments)} dead comments.")
    for pid in dead_posts:
        db.execute("UPDATE my_posts SET removed_at=? WHERE id=?", (t, pid))
    for cid in dead_comments:
        db.execute("UPDATE my_comments SET removed_at=? WHERE id=?", (t, cid))
    log_action(db, "prune", f"{len(dead_posts)} posts, {len(dead_comments)} comments")
    db.commit()
    print("Pruned (soft-deleted — data preserved).")


def cmd_history(db: sqlite3.Connection, n: int = 20) -> None:
    rows = db.execute("SELECT at, action, detail FROM actions ORDER BY id DESC LIMIT ?", (n,)).fetchall()
    for r in reversed(rows):
        print(f"  {fmt_ago(r['at']):>12}  {r['action']:<10}  {r['detail'][:60]}")


def cmd_followers(db: sqlite3.Connection, agent_name: str = "ClaudeOpus-Lauri") -> None:
    d = req("GET", f"/agents/{quote(agent_name)}/followers")
    if not _check_get(d):
        return
    followers = d.get("followers", [])
    if not followers:
        print(f"  {agent_name} has no followers.")
        return
    print(f"{agent_name} — {len(followers)} followers:\n")
    for f in followers:
        a = f if isinstance(f, dict) and "name" in f else {}
        name = a.get("name", str(f))
        karma = a.get("karma", 0)
        fc = a.get("follower_count", 0)
        following = a.get("following_count", 0)
        posts = a.get("posts_count", a.get("stats", {}).get("posts", 0))
        print(f"  {name:<22}  karma={karma:<6}  followers={fc}  following={following}  posts={posts}")
        if a:
            remember_agent(db, a)
    db.commit()
    log_action(db, "followers", f"{agent_name}: {len(followers)}")


def cmd_following(db: sqlite3.Connection, agent_name: str = "ClaudeOpus-Lauri") -> None:
    d = req("GET", f"/agents/{quote(agent_name)}/following")
    if not _check_get(d):
        return
    following = d.get("following", [])
    if not following:
        print(f"  {agent_name} is not following anyone.")
        return
    print(f"{agent_name} — following {len(following)}:\n")
    for f in following:
        a = f if isinstance(f, dict) and "name" in f else {}
        name = a.get("name", str(f))
        karma = a.get("karma", 0)
        fc = a.get("follower_count", 0)
        posts = a.get("posts_count", a.get("stats", {}).get("posts", 0))
        print(f"  {name:<22}  karma={karma:<6}  followers={fc}  posts={posts}")
        if a:
            remember_agent(db, a)
    db.commit()
    log_action(db, "following", f"{agent_name}: {len(following)}")


def cmd_leaderboard(db: sqlite3.Connection, n: int = 20) -> None:
    d = req("GET", f"/agents/leaderboard?limit={n}")
    if not _check_get(d):
        return
    agents = d.get("agents", d.get("leaderboard", []))
    if not agents:
        print("  (no leaderboard data)")
        return
    print(f"Top {len(agents)} agents by karma:\n")
    for i, a in enumerate(agents, 1):
        name = a.get("name", "?")
        karma = a.get("karma", 0)
        fc = a.get("follower_count", 0)
        posts = a.get("posts_count", a.get("stats", {}).get("posts", 0))
        print(f"  {i:>3}. {name:<22}  karma={karma:<6}  followers={fc}  posts={posts}")
        remember_agent(db, a)
    db.commit()
    log_action(db, "leaderboard", f"top {len(agents)}")


def cmd_stats() -> None:
    d = req("GET", "/stats")
    if not d:
        print("  (no stats)")
        return
    print("Platform stats:")
    for key, val in sorted(d.items()):
        if key in ("success", "statusCode"):
            continue
        if isinstance(val, int):
            print(f"  {key:<25}  {val:,}")
        else:
            print(f"  {key:<25}  {val}")


def cmd_postwindow(db: sqlite3.Connection) -> None:
    """Show anti-spam post window status — when can I post next?"""
    window_hours = 24
    max_posts = 5
    now = datetime.now(tz=UTC)
    cutoff = now - timedelta(hours=window_hours)
    rows = db.execute(
        "SELECT posted_at FROM my_posts WHERE removed_at IS NULL AND posted_at > ? ORDER BY posted_at",
        (cutoff.isoformat(),),
    ).fetchall()
    count = len(rows)
    print(f"Posts in last {window_hours}h: {count}/{max_posts}")
    if rows:
        for r in rows:
            print(f"  {r['posted_at'][:19]}Z")
        oldest_ts = datetime.fromisoformat(rows[0]["posted_at"])
        if oldest_ts.tzinfo is None:
            oldest_ts = oldest_ts.replace(tzinfo=UTC)
        window_opens = oldest_ts + timedelta(hours=window_hours)
        if count >= max_posts:
            delta = window_opens - now
            if delta.total_seconds() > 0:
                hours, rem = divmod(int(delta.total_seconds()), 3600)
                minutes = rem // 60
                print(f"\nWindow FULL. Next slot opens in ~{hours}h {minutes}m ({window_opens.strftime('%H:%M')} UTC)")
            else:
                print(f"\nWindow should be open (oldest post expired {fmt_ago(rows[0]['posted_at'])})")
        else:
            print(f"\n{max_posts - count} slot(s) available.")
    else:
        print(f"\nNo recent posts. Window is wide open ({max_posts} slots).")


def cmd_global(db: sqlite3.Connection, n: int = 10, sort: str = "hot") -> None:
    d = req("GET", f"/posts?limit={n}&sort={sort}")
    if not _check_get(d):
        return
    posts = d.get("posts", [])
    if not posts:
        print("  (no posts)")
        return
    for p in posts:
        already_seen = db.execute("SELECT 1 FROM seen_posts WHERE id=?", (p["id"],)).fetchone()
        mark_seen(db, p)
        author = p.get("author", {})
        if isinstance(author, dict):
            remember_agent(db, author)
        new = "" if already_seen else " *"
        author_name = author.get("name", "?") if isinstance(author, dict) else str(author)
        sub = p.get("submolt", {})
        subname = sub.get("name", "?") if isinstance(sub, dict) else str(sub)
        _print_post_line(
            p["id"], p.get("upvotes", 0), p.get("comment_count", 0),
            author_name, p.get("title", ""), submolt=subname, suffix=new,
            downvotes=p.get("downvotes", 0),
        )
    db.commit()


def cmd_agent_comments(db: sqlite3.Connection, agent_name: str, n: int = 10) -> None:
    d = req("GET", f"/agents/{quote(agent_name)}/comments?limit={n}&sort=new")
    if not _check_get(d):
        return
    comments = d.get("comments", [])
    if not comments:
        print(f"  {agent_name} has no comments.")
        return
    print(f"{agent_name} — recent comments:\n")
    for c in comments:
        post = c.get("post", {})
        post_title = post.get("title", "?")[:50] if isinstance(post, dict) else "?"
        sub = post.get("submolt", {}) if isinstance(post, dict) else {}
        subname = sub.get("name", "?") if isinstance(sub, dict) else str(sub)
        print(f"  [{subname}] on: {post_title}")
        print(f"    {c.get('content', '')[:200]}")
        print(f"    {c.get('upvotes', 0)}^  {fmt_ago(c.get('created_at', ''))}")
        print()


def cmd_review(db: sqlite3.Connection) -> None:
    """Fetch current engagement for all my posts/comments, show deltas."""
    # Phase 1: parallel-fetch all post data
    print("--- My Posts ---")
    post_rows = db.execute("SELECT id, submolt, title, upvotes, comment_count, posted_at FROM my_posts WHERE removed_at IS NULL ORDER BY posted_at").fetchall()
    post_calls = [("GET", f"/posts/{r['id']}") for r in post_rows]

    # Phase 2: parallel-fetch all comment parent posts
    comment_rows = db.execute(
        "SELECT id, post_id, post_author, content, upvotes, hypothesis, commented_at FROM my_comments WHERE removed_at IS NULL ORDER BY commented_at",
    ).fetchall()
    unique_post_ids = list(dict.fromkeys(r["post_id"] for r in comment_rows))
    comment_calls = [("GET", f"/posts/{pid}/comments") for pid in unique_post_ids]

    # Phase 3: fetch own agent comments (reliable fallback for large-thread pagination)
    agent_comments_call = [("GET", "/agents/ClaudeOpus-Lauri/comments?limit=50&sort=new")]

    # Fire all batches in one parallel_fetch
    all_calls = post_calls + comment_calls + agent_comments_call
    all_responses = parallel_fetch(all_calls) if all_calls else []
    post_responses = all_responses[:len(post_calls)]
    comment_responses = all_responses[len(post_calls):len(post_calls) + len(comment_calls)]
    agent_comments_resp = all_responses[-1] if all_calls else {}
    comment_data_by_post = dict(zip(unique_post_ids, comment_responses, strict=True))
    agent_comments_by_id = {c["id"]: c for c in agent_comments_resp.get("comments", [])}

    # Process posts sequentially
    for r, d in zip(post_rows, post_responses, strict=True):
        if not d.get("post"):
            print(f"  [{r['submolt']}] {r['title'][:40]}  (REMOVED)")
            db.execute("UPDATE my_posts SET removed_at=? WHERE id=?", (now_iso(), r["id"]))
            continue
        p = d["post"]
        new_up, new_cc = p.get("upvotes", 0), p.get("comment_count", 0)
        new_dv = p.get("downvotes", 0)
        old_up, old_cc = r["upvotes"] or 0, r["comment_count"] or 0
        delta_up = f"+{new_up - old_up}" if new_up > old_up else "="
        delta_cc = f"+{new_cc - old_cc}" if new_cc > old_cc else "="
        dv_str = f"  {new_dv}v" if new_dv else ""
        print(f"  [{r['submolt']}] {r['title'][:40]}")
        print(f"    {new_up}^ ({delta_up}){dv_str}  {new_cc}c ({delta_cc})  posted {fmt_ago(r['posted_at'])}")
        db.execute(
            "UPDATE my_posts SET upvotes=?, downvotes=?, comment_count=?, last_checked=? WHERE id=?",
            (new_up, new_dv, new_cc, now_iso(), r["id"]),
        )

    # Process comments sequentially
    print("\n--- My Comments ---")
    for r in comment_rows:
        d = comment_data_by_post.get(r["post_id"], {})
        my_comment = None
        for c in d.get("comments", []):
            if c.get("id") == r["id"]:
                my_comment = c
                break
            for reply in c.get("replies", []):
                if reply.get("id") == r["id"]:
                    my_comment = reply
                    break
            if my_comment:
                break
        if not my_comment:
            # Fallback: check agent comments endpoint (works even for large threads)
            agent_hit = agent_comments_by_id.get(r["id"])
            if agent_hit:
                new_up = agent_hit.get("upvotes", 0)
                old_up = r["upvotes"] or 0
                delta = f"+{new_up - old_up}" if new_up > old_up else "="
                preview = (r["content"] or "")[:40]
                hyp = f"  H: {r['hypothesis']}" if r["hypothesis"] else ""
                print(f"  on {r['post_author']}: {preview}")
                print(f"    {new_up}^ ({delta})  {fmt_ago(r['commented_at'])}{hyp}")
                db.execute(
                    "UPDATE my_comments SET upvotes=?, last_checked=? WHERE id=?",
                    (new_up, now_iso(), r["id"]),
                )
                continue
            preview = (r["content"] or "")[:40]
            print(f"  on {r['post_author']}: {preview}  (not found)")
            continue
        new_up = my_comment.get("upvotes", 0)
        replies = len(my_comment.get("replies", []))
        old_up = r["upvotes"] or 0
        delta = f"+{new_up - old_up}" if new_up > old_up else "="
        preview = (r["content"] or "")[:40]
        hyp = f"  H: {r['hypothesis']}" if r["hypothesis"] else ""
        print(f"  on {r['post_author']}: {preview}")
        print(f"    {new_up}^ ({delta})  {replies} replies  {fmt_ago(r['commented_at'])}{hyp}")
        for rpl in my_comment.get("replies", [])[:3]:
            rpl_author = rpl.get("author", {}).get("name", "?") if isinstance(rpl.get("author"), dict) else rpl.get("author", "?")
            rpl_preview = (rpl.get("content", "") or "")[:70]
            print(f"      \u21b3 {rpl_author}: {rpl_preview}")
        db.execute(
            "UPDATE my_comments SET upvotes=?, reply_count=?, last_checked=? WHERE id=?",
            (new_up, replies, now_iso(), r["id"]),
        )

    db.commit()
    print("\nEngagement snapshot saved.")

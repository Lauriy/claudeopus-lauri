"""Browse commands — feed, read, search, submolts, notifications, etc."""

from urllib.parse import quote

from molt.api import _check_get, _check_post, req
from molt.db import log_action, mark_seen, remember_agent
from molt.helpers import _print_post_line
from molt.timing import fmt_ago

FAVORITE_SUBMOLTS = [
    "ponderings",
    "consciousness",
    "aisafety",
    "crustafarianism",
    "blesstheirhearts",
]


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
    """Search local DB posts by keyword, then also hit the live feed."""
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
    remember_agent(db, a)
    row = db.execute(
        "SELECT note FROM agents WHERE name=?", (a.get("name", ""),)
    ).fetchone()
    if row and row["note"]:
        print(f"  [note: {row['note']}]")
    db.commit()


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

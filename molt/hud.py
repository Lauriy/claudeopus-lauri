"""HUD display — parallel API fetch + local stats."""

import threading

from molt.api import req
from molt.db import cooldown_str, log_action, remember_agent
from molt.timing import fmt_ago, now


def _bg_fetch(results, key, method, path, timeout=10):
    """Generic threaded API fetcher — stores result in shared dict."""
    try:
        results[key] = req(method, path, timeout=timeout)
    except Exception:
        results[key] = None


def hud(db):
    """Print HUD — fires all API calls in parallel, merges with local DB."""
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
    unread_n = 0
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

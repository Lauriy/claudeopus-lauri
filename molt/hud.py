"""HUD display — parallel API fetch + local stats."""

import sqlite3
import threading
from typing import Any

from molt.api import req
from molt.db import cooldown_str, log_action, remember_agent
from molt.timing import fmt_ago, now


def _bg_fetch(results: dict[str, Any], key: str, method: str, path: str, timeout: int = 10) -> None:
    try:
        results[key] = req(method, path, timeout=timeout)
    except Exception:
        results[key] = None


def hud(db: sqlite3.Connection) -> None:
    results: dict[str, Any] = {}
    threads: list[threading.Thread] = []
    for key, method, path in [
        ("dm", "GET", "/agents/dm/check"),
        ("me", "GET", "/agents/me"),
        ("notifs", "GET", "/notifications?limit=50"),
    ]:
        t = threading.Thread(target=_bg_fetch, args=(results, key, method, path), daemon=True)
        t.start()
        threads.append(t)

    t_now = now()
    last_action = db.execute("SELECT at FROM actions ORDER BY id DESC LIMIT 1").fetchone()
    gap = f"  gap={fmt_ago(last_action['at'])}" if last_action else ""
    seen_count = db.execute("SELECT COUNT(*) as c FROM seen_posts").fetchone()["c"]
    agent_count = db.execute("SELECT COUNT(*) as c FROM agents").fetchone()["c"]
    cd = cooldown_str(db)
    cd_fmt = f"post={cd}" if cd == "READY" else f"post in {cd}"

    for th in threads:
        th.join(timeout=12)

    me_data = results.get("me")
    if me_data and not me_data.get("error") and me_data.get("agent"):
        a = me_data["agent"]
        me_str = f"  me={a.get('karma', 0)}k/{a.get('follower_count', 0)}f"
        remember_agent(db, a)
        db.commit()
    else:
        me_row = db.execute(
            "SELECT karma, followers FROM agents WHERE name='ClaudeOpus-Lauri'"
        ).fetchone()
        me_str = f"  me={me_row['karma']}k/{me_row['followers']}f" if me_row else ""

    dm_str = ""
    dm = results.get("dm")
    if dm and not dm.get("error"):
        log_action(db, "dmcheck_bg", "")
        db.commit()
        raw_req = dm.get("requests", {})
        raw_msg = dm.get("messages", {})
        req_count = int(raw_req.get("count", 0)) if isinstance(raw_req, dict) else 0
        unread = int(raw_msg.get("total_unread", 0)) if isinstance(raw_msg, dict) else 0
        dm_str = f"  DM:{req_count}req/{unread}unread" if req_count > 0 or unread > 0 else "  DM:ok"
    elif dm and "suspended" in str(dm.get("error", "")).lower():
        dm_str = "  DM:SUSPENDED!"
    else:
        dm_str = "  DM:?"

    notif_str = ""
    unread_n = 0
    notif_data = results.get("notifs")
    if notif_data and isinstance(notif_data.get("notifications"), list):
        unread_n = sum(1 for n in notif_data["notifications"] if not n.get("isRead"))
        notif_str = f"  N:{unread_n}" if unread_n else ""

    print(f"[{t_now.strftime('%H:%M:%S UTC')}] {cd_fmt}  seen={seen_count}  agents={agent_count}{me_str}{dm_str}{notif_str}{gap}")
    if dm_str and ("req" in dm_str or "SUSPENDED" in dm_str) and dm_str not in ("  DM:ok", "  DM:?"):
        print("  *** DM ALERT — run: python molt.py dmrequests ***")
    if notif_str:
        print(f"  *** {unread_n} unread notification(s) — run: python molt.py notifs ***")
    print()

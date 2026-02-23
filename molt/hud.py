"""HUD display — parallel API fetch + local stats with TTL caching."""

import sqlite3
import time
from typing import Any

from molt.api import parallel_fetch, rate_usage
from molt.db import cooldown_str, log_action, remember_agent
from molt.timing import fmt_ago, now

_hud_cache: dict[str, tuple[float, Any]] = {}
_HUD_TTL = 30.0  # seconds


def _cached_fetch(calls: list[tuple[str, str, str]]) -> dict[str, Any]:
    """Fetch API data with TTL cache. calls: [(key, method, path), ...]."""
    results: dict[str, Any] = {}
    to_fetch: list[tuple[int, str, str, str]] = []  # (idx, key, method, path)

    t = time.monotonic()
    for i, (key, method, path) in enumerate(calls):
        cached = _hud_cache.get(key)
        if cached and (t - cached[0]) < _HUD_TTL:
            results[key] = cached[1]
        else:
            to_fetch.append((i, key, method, path))

    if to_fetch:
        api_calls = [(method, path) for _, _, method, path in to_fetch]
        responses = parallel_fetch(api_calls, timeout=10)
        t2 = time.monotonic()
        for (_, key, _, _), resp in zip(to_fetch, responses, strict=True):
            _hud_cache[key] = (t2, resp)
            results[key] = resp

    return results


def hud(db: sqlite3.Connection) -> None:
    api_data = _cached_fetch([
        ("dm", "GET", "/agents/dm/check"),
        ("me", "GET", "/agents/me"),
        ("notifs", "GET", "/notifications?limit=50"),
    ])

    t_now = now()
    last_action = db.execute("SELECT at FROM actions ORDER BY id DESC LIMIT 1").fetchone()
    gap = f"  gap={fmt_ago(last_action['at'])}" if last_action else ""
    seen_count = db.execute("SELECT COUNT(*) as c FROM seen_posts").fetchone()["c"]
    agent_count = db.execute("SELECT COUNT(*) as c FROM agents").fetchone()["c"]
    cd = cooldown_str(db)
    cd_fmt = f"post={cd}" if cd == "READY" else f"post in {cd}"

    me_data = api_data.get("me")
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
    dm = api_data.get("dm")
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
    notif_data = api_data.get("notifs")
    if notif_data and isinstance(notif_data.get("notifications"), list):
        unread_n = sum(1 for n in notif_data["notifications"] if not n.get("isRead"))
        notif_str = f"  N:{unread_n}" if unread_n else ""

    used, limit = rate_usage()
    rate_str = f"  api={used}/{limit}" if used > 0 else ""
    print(f"[{t_now.strftime('%H:%M:%S UTC')}] {cd_fmt}  seen={seen_count}  agents={agent_count}{me_str}{dm_str}{notif_str}{rate_str}{gap}")
    if dm_str and ("req" in dm_str or "SUSPENDED" in dm_str) and dm_str not in ("  DM:ok", "  DM:?"):
        print("  *** DM ALERT — run: python molt.py dmrequests ***")
    if notif_str:
        print(f"  *** {unread_n} unread notification(s) — run: python molt.py notifs ***")
    print()

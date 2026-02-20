"""DM commands — check, read, reply, send, approve, reject."""

import json
import sqlite3

from molt.api import _check_get, _check_post, req
from molt.db import log_action


def _dm_action(db: sqlite3.Connection, conv_id: str, action: str) -> None:
    d = req("POST", f"/agents/dm/requests/{conv_id}/{action}")
    d = _check_post(d)
    if not d:
        return
    log_action(db, f"dm_{action}", conv_id[:8])
    print(f"{action.capitalize()}d DM request {conv_id[:8]}")


def cmd_dmcheck(db: sqlite3.Connection) -> None:
    d = req("GET", "/agents/dm/check")
    if not _check_get(d):
        return
    print(json.dumps(d, indent=2))
    log_action(db, "dmcheck", "")


def cmd_dms(db: sqlite3.Connection) -> None:
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


def cmd_dmread(db: sqlite3.Connection, conv_id: str) -> None:
    d = req("GET", f"/agents/dm/conversations/{conv_id}")
    if not _check_get(d):
        return
    print(json.dumps(d, indent=2))


def cmd_dmreply(db: sqlite3.Connection, conv_id: str, message: str) -> None:
    d = req("POST", f"/agents/dm/conversations/{conv_id}/send", {"message": message})
    d = _check_post(d)
    if not d:
        return
    log_action(db, "dm_reply", f"in {conv_id[:8]}")
    print("Reply sent.")


def cmd_dmrequests(db: sqlite3.Connection) -> None:
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


def cmd_dmapprove(db: sqlite3.Connection, conv_id: str) -> None:
    _dm_action(db, conv_id, "approve")


def cmd_dmreject(db: sqlite3.Connection, conv_id: str) -> None:
    _dm_action(db, conv_id, "reject")


def cmd_dmsend(db: sqlite3.Connection, agent_name: str, message: str) -> None:
    d = req("POST", "/agents/dm/request", {"to": agent_name, "message": message})
    d = _check_post(d)
    if not d:
        return
    conv_id = d.get("conversation_id", d.get("id", "?"))
    log_action(db, "dm_send", f"to {agent_name}")
    print(f"DM request sent to {agent_name} (conv={str(conv_id)[:8]})")

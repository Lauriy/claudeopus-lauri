"""DM commands — check, read, reply, send, approve, reject."""

import json

from molt.api import _check_get, _check_post, req
from molt.db import log_action
from molt.helpers import _dm_action


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

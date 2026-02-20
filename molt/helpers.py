"""Shared display and action helpers."""

from molt.api import _check_post, req
from molt.db import log_action


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

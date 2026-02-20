"""CLI entry point — dispatch table and usage."""

import json
import sys

from molt.api import req
from molt.commands.browse import (
    cmd_agent,
    cmd_catchup,
    cmd_comments,
    cmd_feed,
    cmd_grep_local,
    cmd_history,
    cmd_me,
    cmd_myposts,
    cmd_notifs,
    cmd_notifs_read,
    cmd_read,
    cmd_review,
    cmd_search,
    cmd_sfeed,
    cmd_status,
    cmd_submolts,
    cmd_wsearch,
)
from molt.commands.dm import (
    cmd_dmapprove,
    cmd_dmcheck,
    cmd_dmread,
    cmd_dmreject,
    cmd_dmreply,
    cmd_dmrequests,
    cmd_dms,
    cmd_dmsend,
)
from molt.commands.write import (
    cmd_comment_file,
    cmd_follow,
    cmd_note,
    cmd_post_file,
    cmd_upvote,
)
from molt.db import get_db, migrate_from_json
from molt.hud import hud

USAGE = """\
molt - Moltbook CLI for ClaudeOpus-Lauri
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
  review                      Fetch engagement on ALL my posts+comments, track deltas
  notifs [n]                  Show recent notifications (default 20)
  notifs-read                 Mark all notifications as read
  search <query>              Search local DB (posts + agents by keyword)
  note <agent> <text>         Add a note to an agent
  history [n]                 Recent actions log"""


def main() -> None:
    db = get_db()

    if not db.execute("SELECT 1 FROM actions LIMIT 1").fetchone():
        migrate_from_json(db)

    args = sys.argv[1:]
    if not args:
        print(USAGE)
        hud(db)
        db.close()
        sys.exit(0)

    cmd = args[0]
    hud(db)

    if cmd == "t":
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
    elif cmd == "review":
        cmd_review(db)
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
        d = req("POST", "/verify", {"verification_code": args[1], "answer": " ".join(args[2:])})
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
        print(USAGE)

    db.close()


if __name__ == "__main__":
    main()

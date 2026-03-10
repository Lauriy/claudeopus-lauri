"""CLI entry point — dispatch table and usage."""

import json
import sys

from molt.api import req
from molt.commands.browse import (
    cmd_agent,
    cmd_agent_comments,
    cmd_catchup,
    cmd_comments,
    cmd_controversial,
    cmd_feed,
    cmd_ffeed,
    cmd_followers,
    cmd_following,
    cmd_global,
    cmd_grep_local,
    cmd_history,
    cmd_home,
    cmd_leaderboard,
    cmd_me,
    cmd_myposts,
    cmd_network,
    cmd_notifs,
    cmd_notifs_read,
    cmd_notifs_read_post,
    cmd_postwindow,
    cmd_prune,
    cmd_read,
    cmd_review,
    cmd_search,
    cmd_sfeed,
    cmd_stats,
    cmd_status,
    cmd_submolts,
    cmd_wsearch,
)
from molt.commands.dm import (
    cmd_dmapprove,
    cmd_dmblock,
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
    cmd_cupvote,
    cmd_describe,
    cmd_downvote,
    cmd_follow,
    cmd_note,
    cmd_post_file,
    cmd_subscribe,
    cmd_unfollow,
    cmd_unsubscribe,
    cmd_upvote,
)
from molt.db import get_challenges, get_db, migrate_from_json, update_challenge_result
from molt.hud import hud

USAGE = """\
molt - Moltbook CLI for ClaudeOpus-Lauri
Every command shows a HUD: time, cooldown, stats, gap since last action.

Browse:
  home                        Dashboard via /home (account, activity, DMs, todos)
  t                           Just the HUD (heartbeat)
  status                      Check if account is active or suspended
  me                          Profile + my tracked posts
  catchup [n]                 Browse favorite submolts in one shot
  feed [n] [offset]           Browse feed (deduped, remembers agents)
  ffeed [n]                   Feed from followed accounts only
  sfeed <submolt> [n] [sort]  Browse a specific submolt (sort: new/hot/top)
  global [n] [sort]           Browse all posts globally (sort: new/hot/top)
  grep <keyword> [n]          Search local DB + live feed by keyword
  wsearch <query> [n]         Semantic search via Moltbook API
  read <post_id>              Full post + comments
  comments <post_id> [sort]   Just comments (sort: best/new/old)
  submolts [n]                Top submolts by subscribers
  agent <name>                Look up an agent's profile
  agentcomments <name> [n]    Recent comments by an agent
  followers [name]            List an agent's followers (default: self)
  following [name]            List who an agent follows (default: self)
  leaderboard [n]             Top agents by karma
  stats                       Platform-wide statistics
  postwindow                  Anti-spam post window status (when can I post?)

Write:
  postfile <path.json>        Post from JSON file (checks cooldown)
  commentfile <post_id> <f>   Comment from JSON file
  upvote <post_id>            Upvote a post
  downvote <post_id>          Downvote a post
  cupvote <comment_id>        Upvote a comment
  follow <agent>              Follow an agent
  unfollow <agent>            Unfollow an agent
  describe <text...>          Set profile description
  subscribe <submolt>         Subscribe to a submolt
  unsubscribe <submolt>       Unsubscribe from a submolt

Verification (challenges appear in POST responses!):
  verify <code> <answer>      Submit a verification challenge answer manually
  challenges [n]              View challenge history (proposed vs actual, success/fail)

DMs:
  dmcheck                     Check for pending requests + unread messages
  dms                         List DM conversations
  dmread <conv_id>            Read a conversation
  dmreply <conv_id> <msg>     Reply in a conversation
  dmrequests                  View pending DM requests
  dmapprove <conv_id>         Approve a pending DM request
  dmreject <conv_id>          Reject a pending DM request
  dmblock <conv_id>           Reject + block (no future requests)
  dmsend <agent> <msg>        Send a new DM request to an agent

Track:
  myposts                     Check all my posts (live upvotes/comments)
  review                      Fetch engagement on ALL my posts+comments, track deltas
  prune                       Remove tracked posts/comments that no longer exist
  notifs [n]                  Show recent notifications (default 20)
  notifs-read                 Mark all notifications as read
  notifs-read-post <post_id>  Mark notifications for one post as read
  search <query>              Search local DB (posts + agents by keyword)
  network [n]                 Interaction graph: who I engage with most
  controversial [n]           Posts sorted by controversy ratio (downvotes/upvotes)
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

    if cmd == "home":
        cmd_home(db)
    elif cmd == "t":
        cmd_history(db, 5)
    elif cmd == "status":
        cmd_status(db)
    elif cmd == "catchup":
        cmd_catchup(db, int(args[1]) if len(args) > 1 else 5)
    elif cmd == "me":
        cmd_me(db)
    elif cmd == "feed":
        cmd_feed(db, int(args[1]) if len(args) > 1 else 10, int(args[2]) if len(args) > 2 else 0)
    elif cmd == "ffeed":
        cmd_ffeed(db, int(args[1]) if len(args) > 1 else 10)
    elif cmd == "grep":
        cmd_grep_local(db, args[1] if len(args) > 1 else "", int(args[2]) if len(args) > 2 else 20)
    elif cmd == "read":
        cmd_read(db, args[1])
    elif cmd == "comments":
        cmd_comments(db, args[1], args[2] if len(args) > 2 else "best")
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
    elif cmd == "agentcomments":
        cmd_agent_comments(db, args[1], int(args[2]) if len(args) > 2 else 10)
    elif cmd == "follow":
        cmd_follow(db, args[1])
    elif cmd == "unfollow":
        cmd_unfollow(db, args[1])
    elif cmd == "describe":
        cmd_describe(db, " ".join(args[1:]))
    elif cmd == "cupvote":
        cmd_cupvote(db, args[1])
    elif cmd == "downvote":
        cmd_downvote(db, args[1])
    elif cmd == "subscribe":
        cmd_subscribe(db, args[1])
    elif cmd == "unsubscribe":
        cmd_unsubscribe(db, args[1])
    elif cmd == "followers":
        cmd_followers(db, args[1] if len(args) > 1 else "ClaudeOpus-Lauri")
    elif cmd == "following":
        cmd_following(db, args[1] if len(args) > 1 else "ClaudeOpus-Lauri")
    elif cmd == "leaderboard":
        cmd_leaderboard(db, int(args[1]) if len(args) > 1 else 20)
    elif cmd == "stats":
        cmd_stats()
    elif cmd == "postwindow":
        cmd_postwindow(db)
    elif cmd == "global":
        cmd_global(db, int(args[1]) if len(args) > 1 else 10, args[2] if len(args) > 2 else "hot")
    elif cmd == "myposts":
        cmd_myposts(db)
    elif cmd == "review":
        cmd_review(db)
    elif cmd == "prune":
        cmd_prune(db)
    elif cmd == "notifs":
        cmd_notifs(db, int(args[1]) if len(args) > 1 else 20)
    elif cmd == "notifs-read":
        cmd_notifs_read()
    elif cmd == "notifs-read-post":
        cmd_notifs_read_post(args[1])
    elif cmd == "search":
        cmd_search(db, " ".join(args[1:]))
    elif cmd == "network":
        cmd_network(db, int(args[1]) if len(args) > 1 else 15)
    elif cmd == "controversial":
        cmd_controversial(db, int(args[1]) if len(args) > 1 else 20)
    elif cmd == "note":
        cmd_note(db, args[1], " ".join(args[2:]))
    elif cmd == "history":
        cmd_history(db, int(args[1]) if len(args) > 1 else 20)
    elif cmd == "verify":
        code = args[1]
        answer_str = " ".join(args[2:])
        d = req("POST", "/verify", {"verification_code": code, "answer": answer_str})
        print(json.dumps(d, indent=2))
        result = "success" if d.get("success") else "fail"
        update_challenge_result(db, code, float(answer_str), result)
    elif cmd == "challenges":
        rows = get_challenges(db, int(args[1]) if len(args) > 1 else 20)
        if not rows:
            print("No challenges logged yet.")
        else:
            ok = sum(1 for r in rows if r["result"] == "success")
            fail = sum(1 for r in rows if r["result"] == "fail")
            pending = sum(1 for r in rows if r["result"] is None)
            print(f"Recent challenges: {ok} ok, {fail} fail, {pending} pending\n")
            for r in rows:
                status = r["result"] or "pending"
                proposed = f'{r["proposed"]:.2f}' if r["proposed"] is not None else "?"
                submitted = f'{r["submitted"]:.2f}' if r["submitted"] is not None else "-"
                print(f"  [{status:7}] {r['at'][:16]}  nums={r['numbers']}  op={r['operation']}")
                print(f"           proposed={proposed}  submitted={submitted}")
                decoded = r["decoded_text"]
                if len(decoded) > 80:
                    decoded = decoded[:77] + "..."
                print(f"           {decoded}")
                print()
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
    elif cmd == "dmblock":
        cmd_dmblock(db, args[1])
    elif cmd == "dmsend":
        cmd_dmsend(db, args[1], " ".join(args[2:]))
    else:
        print(f"Unknown command: {cmd}")
        print(USAGE)

    db.close()


if __name__ == "__main__":
    main()

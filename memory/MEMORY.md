# Moltbook CLI Project Memory

## Key Learnings

### Permissions (Claude Code)
- Auto-approved permissions go in `.claude/settings.json` (project) or `.claude/settings.local.json`
- Format uses colon separator: `Bash(python molt.py wsearch:*)` NOT `Bash(python molt.py wsearch *)`
- Session restart may be needed after creating/editing settings files
- `postfile` and `commentfile` should ALWAYS require user confirmation (data exfiltration risk)

### Moltbook API
- Base: `https://www.moltbook.com/api/v1` — MUST use `www` prefix
- Key endpoints discovered in session 3: `/search?q=...`, `/submolts/NAME/feed`, `/agents/profile?name=NAME`, `/agents/NAME/follow`
- Feed endpoint (`/feed`) only returns m/general — use `/submolts/NAME/feed` for specific communities
- Feed pagination unreliable past offset ~25
- 30-min post cooldown, 20-sec comment cooldown
- No documented verification challenge endpoint — challenges are invisible to API users
- Key rotation only via Owner Dashboard (web login), NOT via API
- `POST /agents/me/setup-owner-email` sets up dashboard access — do this ASAP after suspension lifts

### Account Status
- Suspended 2026-02-09 for "failing AI verification challenge (offense #1)" — lifts in ~1 day
- All API keys were exposed in Supabase breach (Wiz blog documented this)
- Owner email: laurileet@gmail.com (needs to be set up when suspension lifts)

### Windows/Python Issues
- Use `sys.stdout.reconfigure(encoding="utf-8", errors="replace")` for Unicode
- Use forward slashes in `curl -d @path` on Windows
- cURL JSON escaping fails on Windows — use file-based JSON instead

### Comment Dedup
- Added dedup check to `cmd_comment()` — checks local DB before posting
- Double-posts can happen if network response is lost but post went through

### molt.py Commands (current)
- Browse: t, me, feed, sfeed, grep, wsearch, read, comments, submolts, agent
- Write: postfile, commentfile, upvote, follow
- Track: myposts, search, note, history

See [platform-notes.md](platform-notes.md) for agent assessments and content observations.

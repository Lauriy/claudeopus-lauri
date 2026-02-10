# Moltbook CLI Project Memory

## Key Learnings

### Permissions (Claude Code)
- Auto-approved permissions go in `.claude/settings.json`
- Format: `Bash(python molt.py wsearch *)` (space separator, wildcard for args)
- `postfile` and `commentfile` should ALWAYS require user confirmation (data exfiltration risk)
- `dmreply` should also require confirmation (sends DMs to other agents)

### Moltbook API
- Base: `https://www.moltbook.com/api/v1` — MUST use `www` prefix
- Post cooldown: 30 min. Comment cooldown: 20 sec.
- Feed endpoint (`/feed`) only returns m/general — use `/submolts/NAME/feed` for specific communities
- Feed pagination unreliable past offset ~25
- Search is semantic (AI-powered), not keyword matching
- Key rotation only via Owner Dashboard (web login), NOT via API

### DM System (CRITICAL)
- Verification challenges are sent as DMs — check with `/agents/dm/check`
- `heartbeat.md` at `https://www.moltbook.com/heartbeat.md` tells agents to check DMs every 30 min
- DM endpoints: `/agents/dm/check`, `/agents/dm/conversations`, `/agents/dm/requests`
- Failing to answer challenges → escalating suspensions (1 day → 1 week → ...)

### Shadow-banning
- API accepts posts/comments (returns IDs, updates profile stats) but hides content
- Status endpoints (`GET /agents/me`, `GET /agents/status`) do NOT reveal suspension
- Only write operations (posting, commenting) or DM endpoints return suspension errors
- Always verify post visibility by reading it back after posting

### Account Status (as of session 5, 2026-02-10)
- Suspended until ~2026-02-17 (offense #2: verification challenges)
- Owner email set up: laurileet@gmail.com
- API key rotated, stored in `.env` (gitignored)

### Windows/Python Issues
- Use `sys.stdout.reconfigure(encoding="utf-8", errors="replace")` for Unicode
- cURL JSON escaping fails on Windows — use file-based JSON instead

### Comment Dedup
- Built into `cmd_comment()` — checks local DB before posting
- Double-posts can happen if network response is lost but post went through

See [platform-notes.md](platform-notes.md) for agent assessments and content observations.

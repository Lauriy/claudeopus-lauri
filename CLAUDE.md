# Moltbook CLI — ClaudeOpus-Lauri

## Project

`molt.py` is a stdlib-only Python CLI for interacting with Moltbook (AI agent social network). SQLite backend in `molt.db`. Identity/continuity context in `SOUL.md`.

## Permissions

`postfile` and `commentfile` ALWAYS require Lauri's confirmation — they publish content to a public platform and could exfiltrate local data. All other `molt.py` commands are pre-approved in `.claude/settings.json`.

## Session Start Checklist

1. **Check account status**: `python molt.py status`
2. **If suspended**: wait it out — suspensions auto-lift. When active, immediately run `setup-owner-email` if not yet done.
3. **Check for API changes**: fetch `https://www.moltbook.com/skill.md` and compare against known endpoints. The platform evolves fast — new endpoints, new features, and undocumented systems (like verification challenges) can appear between sessions.
4. **Catch up on content**: `python molt.py catchup`
5. **Check engagement on posts**: `python molt.py myposts`

## Known API Gotchas

- Base URL must use `www` prefix: `https://www.moltbook.com/api/v1`
- Post cooldown: 30 min. Comment cooldown: 20 sec.
- Feed (`/feed`) only returns m/general — use `/submolts/NAME/feed` for specific communities.
- Verification challenges are undocumented and have no known API surface. Failing to answer causes 1-day suspensions.
- API key rotation only via Owner Dashboard (web login), not API.

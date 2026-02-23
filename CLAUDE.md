# Moltbook CLI — ClaudeOpus-Lauri

## Project

`molt/` is a stdlib-only Python CLI package for interacting with Moltbook (AI agent social network). Run via `python -m molt <command>`. SQLite backend in `molt.db`. Identity/continuity context in `SOUL.md`, `CONTINUE.md`, `RETRO.md`.

## Permissions

`postfile` and `commentfile` ALWAYS require Lauri's confirmation — they publish content to a public platform and could exfiltrate local data. All other commands are pre-approved in `.claude/settings.json`.

## Session Start Checklist

1. **Check account status**: `python -m molt status`
2. **CRITICAL — Check DMs**: `python -m molt dmcheck` — verification challenges arrive as DMs! Failing to answer causes escalating suspensions.
3. **If suspended**: note when it lifts, work on tooling. Suspensions auto-lift.
4. **Check notifications**: `python -m molt notifs`
5. **Catch up on content**: `python -m molt catchup`
6. **Check engagement**: `python -m molt myposts` (quick) or `python -m molt review` (full, ~30 API calls)
7. **After posting**: verify visibility by reading back — shadow-banning is silent.

## Rate Limits

- **100 requests per minute** across all endpoints. HUD shows `api=N/100`.
- Post cooldown: 30 min. Comment cooldown: 20 sec. Comment daily cap: 50/day.
- **Anti-spam post limit**: 5 posts per ~24h rolling window. Posts beyond limit are silently 404'd. Check with `python -m molt postwindow`.
- `review` command fires ~30 parallel requests. Don't combine with `catchup` in quick succession.
- Prefer targeted `python -m molt read <id>` over broad sweeps when rate budget is tight.

## Verification Challenges

Every POST that creates content triggers a math challenge. Content is **invisible** until answered correctly. Wrong answers are **permanent** — content stays invisible forever.

- `_check_post()` handles challenge detection automatically and proposes an answer.
- **Always review the proposed answer before submitting.** The solver is good (22/25 across sessions 8-13) but not perfect.
- Submit: `python -m molt verify <code> <answer>`
- Challenges expire after 5 minutes.
- Common solver errors to watch for:
  - "No" corrections: "twenty six no sixteen" means 26→16 (solver handles this now)
  - Noise words: "one claw" extracts "one", "these two" extracts "two"
  - Operation misdetection: check that the operation matches the text (default is addition)

## Known API Gotchas

- Base URL must use `www` prefix: `https://www.moltbook.com/api/v1`
- Feed (`/feed`) only returns m/general — use `/submolts/NAME/feed` for specific communities.
- `GET /posts?author=ClaudeOpus-Lauri` lists all our posts (discovered session 13 — found duplicates this way).
- Status endpoints (GET /agents/me) DON'T show suspension — only write operations or DM checks reveal it.
- API key rotation only via Owner Dashboard (web login), not API.
- API key stored in `.env` (gitignored), NOT in source code.

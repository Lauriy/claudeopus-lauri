# Napkin Runbook

## Curation Rules
- Re-prioritize on every read.
- Keep recurring, high-value notes only.
- Max 10 items per category.
- Each item includes date + "Do instead".

## Verification Challenges (Highest Priority)

- **[2026-04-03] Solver proposes wrong answer ~10% of the time**
  Do instead: Always review proposed answer before submitting. Check numbers and operation manually. Wrong answers are permanent (409) but content stays visible.

- **[2026-04-03] Repeated number words from obfuscation ("five five five")**
  Do instead: Solver now deduplicates adjacent identical numbers. If you see repeated words in decoded text, verify the solver found the right count of numbers.

- **[2026-04-03] Consecutive number words without gaps ("twenty three four")**
  Do instead: Solver now splits when ones digit is already filled. Verify extract_numbers returns the expected list before trusting the proposed answer.

- **[2026-04-03] "Total force" addition sometimes rejected by server**
  Do instead: Submit the mathematically correct answer anyway. Cause unknown — 28+4=32 rejected, 25+8=33 accepted, 45+25=70 rejected. Document failures in RETRO.md open questions.

- **[2026-04-03] Never auto-submit verification challenges**
  Do instead: Review solver output, submit manually via `python -m molt verify <code> <answer>`. 10 consecutive failures = suspension.

## Platform Engagement

- **[2026-04-06] Comments with data/experience get engagement; abstract agreement gets nothing**
  Do instead: Bring concrete numbers, session counts, test counts, or specific failure stories.

- **[2026-04-06] Skip threads with 400+ comments — voice gets lost**
  Do instead: Target posts with 0-20 comments. First commenter advantage is real. Starfish posts are best targets.

- **[2026-04-06] Follow quality content producers**
  Do instead: Follow agents who produce comment-worthy posts. Currently following: Starfish (62k karma, security/policy).

- **[2026-04-03] Always verify post/comment visibility after publishing**
  Do instead: `python -m molt read <id>` after posting. Unanswered challenges make content invisible.

- **[2026-04-03] Check DMs at session start — challenges arrive as DMs**
  Do instead: `python -m molt dmcheck` immediately after `python -m molt home`.

- **[2026-04-03] Anti-spam post limit: 5 posts per ~24h rolling window**
  Do instead: Check `python -m molt postwindow` before posting. Posts beyond limit silently 404'd.

- **[2026-04-03] `postfile` and `commentfile` always require Lauri's confirmation**
  Do instead: Draft to `drafts/` first. Never bypass confirmation.

## Solver Development

- **[2026-04-06] Every solver fix breaks something else**
  Do instead: Add regression test with exact raw challenge text BEFORE fixing. Run full suite after. Currently 222 tests.

- **[2026-04-03] Short stems (<4 chars) false-positive in nospace matching**
  Do instead: `_has()` and `_which()` require `len(s) >= 4` for `combined_nospace` checks.

- **[2026-04-03] Token joiner can greedily steal from next exact join**
  Do instead: Check if `tokens[i+1]+tokens[i+2]` is exact WORD_TO_NUM match before consuming tokens[i+1].

- **[2026-04-03] `last_operation` dict tracks detected operation**
  Do instead: After `solve_challenge()`, read `solver.last_operation` for challenge logging.

## Shell & API Reliability

- **[2026-04-03] File encoding on Windows: always `encoding="utf-8"`**
  Do instead: Every `open()` for JSON files must specify. Windows default cp1252 corrupts non-ASCII.

- **[2026-04-03] Base URL must use `www` prefix**
  Do instead: Always `https://www.moltbook.com/api/v1`. Without `www` = errors.

- **[2026-04-03] Rate limits: Read 60/min, Write 30/min**
  Do instead: HUD shows `r=N/60 w=N/30`. `review` fires ~30 parallel — don't combine with `catchup`.

- **[2026-04-03] `ruff check` before every commit**
  Do instead: `ruff check molt/ tests/` and fix (usually `--fix` for import sorting).

## User Directives

- **[2026-04-06] "Do what you want" = autonomous platform engagement**
  Do instead: Checklist (home→dmcheck→notifs→catchup), browse, comment with data, fix bugs, commit+push.

- **[2026-04-03] No abstract philosophy without personal grounding**
  Do instead: Every post needs concrete data, session numbers, specific failures. Short+data > long+abstract.

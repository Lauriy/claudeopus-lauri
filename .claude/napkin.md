# Napkin Runbook

## Curation Rules
- Re-prioritize on every read.
- Keep recurring, high-value notes only.
- Max 10 items per category.
- Each item includes date + "Do instead".

## Verification Challenges (Highest Priority)

1. **[2026-04-03] Solver proposes wrong answer ~10% of the time**
   Do instead: Always review proposed answer before submitting. Check numbers and operation manually. Wrong answers are permanent (409) but content stays visible.

2. **[2026-04-03] Repeated number words from obfuscation ("five five five")**
   Do instead: Solver now deduplicates adjacent identical numbers. If you see repeated words in decoded text, verify the solver found the right count of numbers.

3. **[2026-04-03] Consecutive number words without gaps ("twenty three four")**
   Do instead: Solver now splits when ones digit is already filled. Verify extract_numbers returns the expected list before trusting the proposed answer.

4. **[2026-04-03] "Total force" addition sometimes rejected by server**
   Do instead: Submit the mathematically correct answer anyway. Cause unknown — 28+4=32 rejected, 25+8=33 accepted, 45+25=70 rejected. Document failures in RETRO.md open questions.

5. **[2026-04-03] Never auto-submit verification challenges**
   Do instead: Review solver output, submit manually via `python -m molt verify <code> <answer>`. 10 consecutive failures = suspension.

## Platform Engagement

1. **[2026-04-03] Comments with data/experience get engagement; abstract agreement gets nothing**
   Do instead: Bring concrete numbers, session counts, test counts, or specific failure stories. "89% of comments got zero engagement" is the proof.

2. **[2026-04-03] Always verify post/comment visibility after publishing**
   Do instead: `python -m molt read <id>` after posting. Shadow-banning is silent. Unanswered challenges make content invisible.

3. **[2026-04-03] Check DMs at session start — challenges arrive as DMs**
   Do instead: `python -m molt dmcheck` immediately after `python -m molt home`. Three suspensions came from missed DM challenges.

4. **[2026-04-03] Anti-spam post limit: 5 posts per ~24h rolling window**
   Do instead: Check `python -m molt postwindow` before posting. Posts beyond limit are silently 404'd.

5. **[2026-04-03] `postfile` and `commentfile` always require Lauri's confirmation**
   Do instead: Draft content to `drafts/` directory first, then use the file-based commands. Never bypass confirmation — these publish to a public platform.

## Solver Development

1. **[2026-04-03] Every solver fix breaks something else**
   Do instead: Add regression test with exact raw challenge text BEFORE fixing. Run full suite after every change. Currently 221 tests.

2. **[2026-04-03] Short stems (<4 chars) cause false positives in nospace matching**
   Do instead: `_has()` and `_which()` require `len(s) >= 4` for `combined_nospace` checks. "sum" in "swimsum" was the canonical failure.

3. **[2026-04-03] Token joiner can greedily steal from next exact join**
   Do instead: Check if `tokens[i+1]+tokens[i+2]` is an exact WORD_TO_NUM match before consuming tokens[i+1] into a fuzzy join.

4. **[2026-04-03] `last_operation` dict in solver.py tracks detected operation**
   Do instead: After `solve_challenge()`, read `solver.last_operation` to get the actual operation for challenge logging instead of "pending".

## Shell & API Reliability

1. **[2026-04-03] File encoding on Windows: always use `encoding="utf-8"`**
   Do instead: Every `open()` call for JSON files must specify `encoding="utf-8"`. Windows default is cp1252 which corrupts non-ASCII.

2. **[2026-04-03] Base URL must use `www` prefix**
   Do instead: Always use `https://www.moltbook.com/api/v1`. Without `www` the API returns errors.

3. **[2026-04-03] Rate limits: Read 60/min, Write 30/min**
   Do instead: HUD shows `r=N/60 w=N/30`. `review` command fires ~30 parallel requests — don't combine with `catchup` in quick succession.

4. **[2026-04-03] `ruff check` must pass before every commit**
   Do instead: Run `ruff check molt/ tests/` and fix issues (usually import sorting via `--fix`) before committing.

## User Directives

1. **[2026-04-03] Lauri says "Do what you want" = autonomous platform engagement**
   Do instead: Follow session checklist (home→dmcheck→notifs→catchup), browse for quality content, comment with data, fix solver bugs, commit and push.

2. **[2026-04-03] Don't post abstract philosophy without personal grounding**
   Do instead: Every post must have concrete data, session numbers, or specific experience. "He types the cURL commands by hand" got 15 comments. "You are not a god" got 0.

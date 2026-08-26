# Pitfalls Research

**Domain:** cfb_system_maker v1.1 Season Readiness — merge review branch, first live-season run, Hide Duplicates, describe() fallback, new example system
**Researched:** 2026-08-26
**Confidence:** HIGH (all findings grounded directly in current repo code — `web.py`, `backtest.py`, `describe.py`, `upcoming.py`, `features.py`, `storage.py` — and the `fix/web-app-review-2026-08-26` branch's own commit log/SUMMARY.md, not general web-dev advice)

## Scope correction (read first)

PROJECT.md's rationale for deferring Hide Duplicates says it "only matters once a system can match both sides of one game," and the v1.1 goal claims that's "now reachable" because of the total-filter-semantics fixes (d9c93e4). **This premise does not match `run_backtest`.** `run_backtest`/`run_backtest_summary` do `matched = [game for game in games if matches_system(game, system, feature_map)]` — one boolean per game, so the result list is already 1:1 on `game_id`; a total system with an either-side team/conference filter matches *more games* (one bet each), never two bets on the same game. There is no code path in `run_backtest` that can produce "two candidate bets on one game_id."

Two surfaces genuinely duplicate a `game_id`, and they are different problems — the roadmapper needs to pick one, not assume the premise:

1. **`aggregate_filter_value_rows` (`web.py:242`, backs `/filter-detail`)** — for `either`-perspective totals, `resolve_candidate_value` returns a tuple of values (one per team), and lines 270-279 fan that tuple into multiple bucket entries, each appending the **same** `grade_bet` detail. Per-value Record/ROI/Money rows for a total system's team/conference filter now sum to roughly 2x the matched game count. This is a real bug the merge introduced, and it is the only place today that literally attaches one game to two rows.
2. **Current Matches panel (`_current_matches_panel`, `web.py:1768`)** — iterates `games × saved_systems`; the same `game_id` appears once per saved system that matches it. Real and visible, but it's a cross-*system* duplicate, not a within-system double-count, and it's inherent to the panel design, not something the total-filter-semantics merge changed.

Write the roadmap task as "resolve which surface Hide Duplicates targets (filter-detail double-count vs. Current Matches cross-system repeat) before designing the toggle" rather than assuming `run_backtest` needs deduping.

## Critical Pitfalls

### Pitfall 1: Stale `SearchRun` statistics survive the merge; `_FIGURE_CACHE` does not

**What goes wrong:**
Two different kinds of "cache" exist and they have opposite risk profiles. `_FIGURE_CACHE`/`_DATA_CACHE`/`_FEATURE_OPTIONS_CACHE` (`web.py:1441-1443`) are plain module-level dicts, keyed on `_system_key(system)` + `_data_fingerprint(data_dir)` (size/mtime of `games.csv`/`features.json`). They live only for the Flask process's lifetime and are rebuilt from scratch on every restart — merging the branch and restarting the dev server invalidates them for free. The real risk is `SearchRun`/`SearchRunFinalist` (`storage.py:360-414`, `data/search_runs/*.json`): `wins, losses, pushes, roi, raw_p, corrected_p, bh_significant` are computed once and persisted to disk under the **old** matching semantics, then displayed as current on every later page load with no re-computation and no fingerprint check.

**Why it happens:**
`_FIGURE_CACHE`'s invalidation strategy (file mtime) only guards against the games/features data changing — it has no way to detect that the *matching logic itself* (`matches_system`, `feature_ok`, `effective_perspective`) changed between two runs of the same process, because code version isn't part of the key. `SearchRun` compounds this by being disk-persisted, so it survives across restarts too.

**How to avoid:**
- After merging, enumerate `data/search_runs/*.json` and `data/systems/*.json` for any total-bet-type system with a `teams`/`conferences` filter or a `bet_side`/`opponent` feature-filter perspective (the exact conditions d9c93e4/5040b31 changed). Re-run `run_backtest` for each and diff `bets`/`roi` against the persisted figures.
- Separately: `effective_perspective` collapses `bet_side`/`opponent` → `either` **on storage load** (`features.py:465`). An old saved total-system's on-disk JSON still says `bet_side`, but its runtime behavior is now `either` — its `theory` free-text field, written by a human describing the old behavior, no longer matches what it actually bets. This isn't fixable by re-running a backtest; it needs a one-time audit pass over saved systems' `theory` text.
- `_system_key` normalizes `SystemFilter` via `json.dumps(asdict(system), sort_keys=True)` — it does not include anything about registry/matching-logic version, so don't rely on it to detect semantic drift.

**Warning signs:**
A saved total system with `filter_teams` or `filter_conferences` set shows a different bet count on its dashboard tile after the merge than the number recorded in its `search_runs` JSON (if it came from a search) — the tile is live, the search-run record is frozen.

**Phase to address:**
Merge phase (item 1). Verification: script that loads every saved system + every search run, re-backtests, and flags any total-bet-type system whose bet count changed.

---

### Pitfall 2: `/filter-detail` double-counts total-system either-perspective bets (see Scope correction)

**What goes wrong:**
`aggregate_filter_value_rows` fans a tuple return from `resolve_candidate_value` into multiple `buckets[value]` entries, each holding the *same* `BetDetail` object. For a total system's team/conference popup (now either-perspective per d9c93e4), the per-value table's aggregate bet count across all rows is roughly double the system's actual matched-game count, and `bets`/`wins`/`losses` per row look plausible in isolation but don't sum correctly.

**Why it happens:**
The tuple-fan-out was almost certainly written for genuinely multi-valued categorical features (e.g., a feature legitimately true for two teams), not anticipating that team/conference filters on totals would start returning `(home_value, away_value)` tuples as a matching-semantics side effect of a different fix landing in the same branch.

**How to avoid:**
Concrete test: build a total system with a `filter_teams` set containing both teams of at least one game in the fixture data, run `/filter-detail` for `core:team`, and assert the sum of `bets` across all rows equals `len([g for g in games if matches_system(g, system, feature_map)])`, not double it. Decide explicitly: is one game meant to count once per matching team-value (legitimate, "this game contributes to Team A's row and Team B's row"), or is that itself the duplicate Hide Duplicates should suppress? This is a design decision, not just a bug fix — resolve it before or as part of Hide Duplicates, since it's the same tuple-fan-out mechanism.

**Warning signs:**
Per-value table's total `bets` sum (visible by manually adding the Record column) exceeds the stat-chip header's `bets` count for the same system.

**Phase to address:**
Hide Duplicates phase (item 3) — this is very likely what "duplicates" actually refers to, given the PROJECT.md phrasing. Verification: the bet-count-sum assertion above, run as a test with a total system + shared-team fixture.

---

### Pitfall 3: Dedup and clustering correction are two answers to the same statistical problem — applying both silently double-corrects

**What goes wrong:**
`compute_system_stats` already runs `cluster_dependence_stats` to get `effective_n`, `icc`, `deff`, and divides `_mde` by `deff` specifically to account for correlated same-game bets. If Hide Duplicates removes games from the matched set *and* clustering still discounts the (now-smaller, already-deduped) sample as if it still contained correlated duplicates, the effective sample size is discounted twice for the same correlation.

**Why it happens:**
Dedup and clustering are conceived as separate features (one a display toggle, one a stats-engine detail) but they're the same statistical fix applied at different layers. Nobody currently connects them because until Hide Duplicates exists, there's nothing dedup-shaped to double-count.

**How to avoid:**
Decide the toggle's semantics up front and pick one:
- **Upstream (recommended):** dedup filters the `matched` list before it reaches `run_backtest`'s downstream computation — `result.bets == len(result.bet_details)` holds, and clustering runs on the already-deduped set (correct, no double-correction, but changes the displayed sample and possibly flips significance).
- **Presentational only:** dedup only changes what rows render in a table, `bets`/`wins`/`stats` still reflect the full (undeduped) set. This is cheap but means the Record chip and the table below it visibly disagree, and Grade/Wilson-CI silently keep using the undeduped count without disclosure.

Concrete test: with the toggle on, assert `result.bets == len(result.bet_details)` and that `stats.effective_n <= result.bets` (never showing an effective N larger than what a user can currently see).

**Warning signs:**
Toggling Hide Duplicates changes the row count in a table but the Grade letter, Wilson CI, or p-value shown elsewhere on the same page doesn't move — a strong sign the toggle is presentational-only while stats stay computed on the pre-dedup set.

**Phase to address:**
Hide Duplicates phase (item 3). Verification: the two assertions above, plus a UI check that Grade/Wilson-CI/ROI figures update together with the toggle, not independently.

---

### Pitfall 4: `describe()` fallback masks the exact bug it's meant to disclose, and its `key` must round-trip through `_query_href_removing`

**What goes wrong:**
`_feature_group_sentence` (`describe.py:58`) currently `return None` (silently drops the sentence) for any `(op, control)` combination its four branches don't cover — this is T-01-03, the accepted risk. A naive fallback sentence ("this filter is applied") fixes the *symptom* (missing UI copy) but removes the only signal that a new registry `(op, control)` combo needs a real branch — the fallback becomes permanent scaffolding that nobody circles back to add proper wording for, because nothing breaks anymore.

Separately: every sentence dict carries a `key` (e.g. `f"ff:{key}"`) that `_query_href_removing` (`web.py:962`) parses to build the remove-link href. For known branches this round-trips correctly (`ff:` prefix strips the right query params). A fallback sentence must emit a `key` that either matches an existing `ff:{feature_key}` shape or an entry in `_REMOVE_PARAM_MAP` — if it invents a new key shape, the remove `×` link renders (auto-escaped, safe) but does nothing or breaks other filters, which is a worse UX than today's silent sentence drop (today: filter invisible but removable via reset; with a bad fallback: filter visible but its × is broken).

The XSS concern is lower-risk than it first appears: `{{ row.text }}` in `index.html` is rendered via plain Jinja interpolation (confirmed, no `|safe`), so it auto-escapes. `_feature_group_sentence`'s "Unknown filter" branch already interpolates a raw registry key into text today (`f'Unknown filter "{key}" is unavailable'`) with no incident, because Jinja handles it. The actual risk is scoped to any **client-side JS** path that might inject `describe()` output via `innerHTML` — grep found no such path in `filter_modal.js` today (its `innerHTML` uses are all `= ""` clears, not text injection), so this is a "don't introduce it" constraint for whoever writes the fallback, not a live vulnerability.

**Why it happens:**
A catch-all is the natural fix for "sentence missing," but the missing sentence is a symptom of `feature_ok()` supporting an `(op, control)` combo `describe()` doesn't know how to render — the fallback should say something is *unusual*, not paper over it as normal.

**How to avoid:**
- Make the fallback visually/textually distinct from the four known branches (e.g., `f"{label} filter applied (value: {value})"` rather than trying to mimic natural English) so it's obviously a "we don't have a nice sentence for this yet" signal, and log or flag it (e.g., a debug-mode banner or test assertion) rather than rendering silently identical to a hand-written sentence.
- Assert in a test that the fallback's `key` round-trips through `_query_href_removing` and that the resulting href, applied to the original query string, actually removes the filter (i.e., a second `describe()` call on the resulting `SystemFilter` no longer contains that sentence).
- Keep using plain Jinja interpolation for the value — never add `|safe` to render the fallback (this matches the existing project-wide convention already documented in STATE.md decisions).
- Add a test asserting no `describe()` sentence text is ever passed through `innerHTML` in `filter_modal.js` if any future JS work renders sentences client-side (currently: sentences are server-rendered only, so this is a "don't regress" test for future modal work, not a current gap).

**Warning signs:**
A `(op, control)` combo added to the fallback path stops appearing in bug reports even though `FEATURE_REGISTRY` keeps growing new numeric/categorical control types — a sign the fallback is quietly absorbing combos that actually need dedicated branches.

**Phase to address:**
describe() fallback phase (item 4). Verification: test matrix over every `(op, control)` pair the registry currently defines, asserting each either hits one of the four named branches or the fallback, and the fallback case's key removes the filter when clicked.

---

### Pitfall 5: First live `upcoming` run — calendar-window type mismatch and week-1 feature nulls make the two deferred verifications fail for different reasons than "the code is wrong"

**What goes wrong:**
Two independent, narrower failure modes than generic "first prod run breaks":

1. **`_resolve`'s live-vs-fixture type mismatch (`upcoming.py:166-198`).** The live-calendar path does `start <= now <= end` where `start`/`end` come from `_first(week, "startDate", "start_date")` on a `GamesApi.get_calendar()` row, compared against a `datetime` `now`. The fallback path (`_latest_completed_week`) only ever compares those values *to each other*, never to a `datetime`, so it's insensitive to whether they're strings or `datetime` objects. If the vendored CFBD client's pydantic model yields calendar `startDate`/`endDate` as `str` (common for pydantic v1-generated `datetime` fields depending on `by_alias`/serialization settings) while `tests/test_upcoming.py` fixtures inject `datetime` objects directly, the comparison either raises `TypeError` (str vs datetime) or silently never matches (lexical vs chronological ordering) — and this is exactly the code path that has never run against a real API response, only against hand-built fixtures. Check what `_to_dict` actually produces for `get_calendar()` before the first live run, not after it fails.
2. **Week-1 season-to-date nulls make the second deferred verification look broken by design.** Per `running_stats.py` convention (documented in CLAUDE.md), a season's first game has `games_played=0` and percentages/averages `None`, which fail closed as filters. The deferred verification item is "a feature-filtered saved system correctly matches upcoming games via computed season-to-date stats" (STATE.md). Run that check in week 1 of the real 2026 season and any system filtering on a season-to-date stat will correctly match **zero games** — this is expected behavior, not a bug, but it will look identical to a broken pipeline if nobody schedules the check for a week where accumulated stats exist.

Additional, lower-probability first-run risks worth a quick check rather than a full pitfall writeup: lines not yet posted for the target week (`normalize_games` drops games with no usable line — `meta.row_count` may legitimately be 0 or small if run right after the calendar window opens and books haven't posted yet), and in-progress (started, not yet `completed`) games rendering a play recommendation in Current Matches despite already being underway — the pipeline only distinguishes `completed` vs not, with no third "live" state.

**Why it happens:**
The `upcoming` pipeline (Phase 5) was built and tested entirely against `cfbd_module`-injected fixtures (`tests/test_upcoming.py`) for a network-free test suite — this is correct test design, but it means the calendar-row shape, field casing, and null-handling around a truly in-progress season have literally never been exercised against the real CFBD API before 2026-08-29.

**How to avoid:**
- Before the season starts, run `python -m cfb_system_maker upcoming` (or equivalent) once against the *current, already-live* 2025 or a recent past date to force the live-calendar branch (not the offseason-fallback branch) and inspect `_to_dict(get_calendar(...))` row types directly — confirms whether the type-mismatch risk is real without waiting for 2026-08-29.
- Schedule the "season-to-date stats verification" deferred item for week 3+ of the season, not week 1 — verify week 1 instead with a pregame/metadata feature filter (e.g., `neutralSite`, `favorite`/`underdog`) that has no accumulation dependency.
- After the first live run, log/compare `meta.row_count` against the number of games CFBD's calendar reports for that week — a large gap flags either an unposted-lines situation (expected, informational) or a normalize/drop bug (needs investigation).

**Warning signs:**
`TypeError` or an exception trace inside `_resolve` on the very first live invocation; or Current Matches panel renders empty with `state: "populated"` and `rows: []` in week 1 for every system that has any season-to-date feature filter (expected, but must be distinguished from "pipeline broken").

**Phase to address:**
Live verification phase (item 2). Verification: pre-season dry run against a live-but-past calendar window to catch the type mismatch before 2026-08-29; explicit scheduling note that puts the season-to-date-stats check at week 3+, not week 1.

---

### Pitfall 6: New example system repeats the Phase 5 "matched zero games" incident, for two independent reasons this time

**What goes wrong:**
Phase 5 already hit this once (D-21, STATE.md: "registry-feature example uses matchup `conferenceGame` so it matches non-zero games in the resolved week" — implying an earlier draft used a feature that matched zero). The new neutral-site + indoor unders example (`neutralSite` + `gameIndoors` + `venue_dome`, 63.3% over 109 games historically) can recur for two independent reasons:
1. **`gameIndoors` sources from `raw_weather`**, and CLAUDE.md documents `weather` as a Patreon-gated/sometimes-unavailable endpoint (`scrapers.py` allows one endpoint to fail without aborting the run). If weather data is thin or absent for the resolved current week, `gameIndoors` resolves `None` for most/all games, which — like season-to-date nulls — fails closed as a filter, producing zero matches regardless of how many actual indoor games are on the slate.
2. **Neutral-site indoor games are rare and clustered**, concentrated in Week 0/1 kickoff games and bowl season. A typical mid-season week (which is what a live "resolved current week" example-system demo will usually show) has zero neutral-site indoor games — this is true even with perfectly correct data, not a bug.

Both reasons mean the *historical* backtest (109 games, non-zero, statistically real) and the *live resolved-week* match count (likely often zero) are two different numbers that must not be conflated in the UI or in verification — "the example system matched zero games this week" is not evidence the system is broken.

**Why it happens:**
Registry features that are individually well-populated historically can still be null or empty for the live current week if their underlying endpoint has different coverage for the still-in-progress current season than for completed historical seasons (this is the general shape of the D-21 incident, and CLAUDE.md's cfbd-coverage-gaps note flags exactly this class of risk).

**How to avoid:**
- After the first live `upcoming` run, explicitly count non-null values for `neutralSite`, `gameIndoors`, and `venue_dome` in the upcoming-games feature sidecar (not just "did the example match a game") — a feature that's 100% null for the live week is a data-availability bug; a feature that's populated but simply doesn't match any game this week is expected.
- Design the Example Systems tab / Current Matches row for this system to render a deliberate, calm empty state ("No games match this system this week") rather than an ambiguous blank table — distinguishing "correctly found nothing" from "broken."
- In the system's bundled `theory` text, state the historical sample size/p-value explicitly (109 games, p=0.014) so a zero-match week doesn't read as contradicting the claim — the claim is about the historical backtest, not a promise of weekly signal.
- This lead came out of a multi-angle statistical scan (per the milestone context, "the one surviving lead from a week of statistical analysis") — set `search_candidates_tested` on the `SavedSystem` if the search-run machinery was used, so the dashboard's overfitting-aware Grade computation sees the same correction context a user-run search would.

**Warning signs:**
The example system shows a "0 games matched" row in Current Matches during a normal (non-Week-0/bowl) week — expected on its own, but check the upcoming feature sidecar for null rates on `gameIndoors` specifically before assuming it's expected; a 100% null rate for `gameIndoors` in the live sidecar (vs. any non-zero rate in historical `features.json`) means the weather endpoint didn't populate for the current week, not that no games are indoor.

**Phase to address:**
Example system phase (item 5). Verification: sidecar null-rate check for all three features immediately after the first live `upcoming` run; UI review of the zero-match empty state.

## Integration Gotchas

| Integration | Common Mistake | Correct Approach |
|-------------|----------------|-------------------|
| CFBD `GamesApi.get_calendar()` (live, first use in `_resolve`'s primary branch) | Assuming fixture-shaped (`datetime`) calendar rows match live (possibly `str`) rows without checking `_to_dict` output | Dry-run against a live-but-past date before 2026-08-29 and inspect the raw field types directly |
| CFBD `weather` endpoint (backs `gameIndoors`) | Assuming a feature well-populated in `features.json` (historical) will be equally populated in the `upcoming` sidecar for the live current week | Check non-null rate in the upcoming sidecar specifically, not just historical coverage |
| `running_stats.py` season-to-date accumulation | Verifying a season-to-date filtered system in week 1, when `games_played=0` is by design | Schedule that verification for week 3+; use a pregame/metadata feature for week-1 checks |

## Security Mistakes

| Mistake | Risk | Prevention |
|---------|------|------------|
| Fallback sentence text rendered with `\|safe` "to preserve formatting" | Reintroduces XSS on a path the project has otherwise kept clean via Jinja auto-escape | Never use `\|safe` for the fallback; the existing "Unknown filter" branch already proves plain interpolation is safe and sufficient |
| Fallback sentence emits a `key` that doesn't match `_REMOVE_PARAM_MAP` or the `ff:` prefix convention | Renders a remove `×` link that does nothing or removes the wrong filter — user-visible but silently broken, worse than today's silent drop | Test that the fallback's key round-trips through `_query_href_removing` and actually removes the filter on click |

## "Looks Done But Isn't" Checklist

- [ ] **Merge complete:** Tests pass and app boots — but check `data/search_runs/*.json` for any total-bet-type system with team/conference/perspective filters; their persisted stats predate the semantics fix and won't self-correct.
- [ ] **Live `upcoming` run succeeds:** No exception, `state: "populated"` — but verify `meta.row_count` isn't suspiciously low/zero for reasons other than "lines not posted yet," and that the calendar-window branch (not silently the offseason-fallback branch) actually fired for a truly current week.
- [ ] **Hide Duplicates toggle renders and changes row counts:** — but verify `result.bets == len(result.bet_details)` still holds with it on, and that Grade/Wilson-CI/ROI move together with the toggle rather than one lagging the deduped display.
- [ ] **describe() fallback renders text for every filter:** — but verify each fallback sentence's remove link actually removes that filter (not just that text appears).
- [ ] **New example system backtest shows 109 games, 63.3%, p=0.014:** — but verify it separately against a live resolved-week run and confirm a zero-match week is a deliberate empty state, not an unhandled blank.

## Pitfall-to-Phase Mapping

| Pitfall | Prevention Phase | Verification |
|---------|-------------------|--------------|
| Scope mismatch: "two bets on one game_id" premise doesn't exist in `run_backtest` | Roadmapping (before Hide Duplicates phase is planned) | Roadmapper explicitly names which surface (filter-detail vs. Current Matches) the toggle targets |
| Stale `SearchRun` JSON survives merge with pre-fix statistics | Merge phase (item 1) | Script re-backtests every saved system + search run, diffs bet counts against persisted figures |
| `/filter-detail` double-counts either-perspective total bets | Hide Duplicates phase (item 3) | Test: sum of per-value `bets` equals system's total matched-game count for a shared-team fixture |
| Dedup vs. clustering double-correction | Hide Duplicates phase (item 3) | Test: `result.bets == len(result.bet_details)` and `effective_n <= result.bets` under the toggle |
| describe() fallback masks real registry gaps / breaks remove link | describe() fallback phase (item 4) | Test matrix over all `(op, control)` combos; fallback key round-trips through `_query_href_removing` |
| Live calendar type mismatch (`str` vs `datetime`) in `_resolve` | Live verification phase (item 2) | Pre-season dry run against a live-but-past date; inspect `_to_dict(get_calendar())` output types |
| Week-1 season-to-date verification looks broken by design | Live verification phase (item 2) | Schedule that specific check for week 3+; use a metadata feature for week-1 checks |
| Example system matches zero games (weather-null or naturally-rare week) | Example system phase (item 5) | Sidecar null-rate check for `neutralSite`/`gameIndoors`/`venue_dome`; deliberate empty-state UI |

## Sources

- Direct code inspection (HIGH confidence, primary source): `cfb_system_maker/web.py` (`_FIGURE_CACHE`, `_data_fingerprint`, `_current_matches_panel`, `aggregate_filter_value_rows`, `_query_href_removing`), `cfb_system_maker/backtest.py` (`matches_system`, `run_backtest`), `cfb_system_maker/describe.py`, `cfb_system_maker/features.py` (`effective_perspective`), `cfb_system_maker/upcoming.py` (`_resolve`, `_latest_completed_week`, `build_upcoming`), `cfb_system_maker/storage.py` (`SearchRun`/`SearchRunFinalist` persistence), `cfb_system_maker/templates/index.html` (Jinja auto-escape confirmed for `{{ row.text }}`), `cfb_system_maker/static/filter_modal.js` (`innerHTML` usage audit).
- `.planning/quick/20260826-total-filter-semantics-fixes/SUMMARY.md` — source of the either-side matching and tuple-bucket behavior this file traces through to the `/filter-detail` bug.
- `git log master..fix/web-app-review-2026-08-26` — 26-commit list confirming scope of the merge (semantics fixes, security/a11y fixes, memoization, modal state-cleanup fixes).
- `.planning/PROJECT.md`, `.planning/STATE.md` — milestone context, prior D-21 zero-match incident, deferred-item scheduling constraints, accepted-risk T-01-03 description.
- Project `CLAUDE.md` (both root and `.claude/`) — CFBD field-name inconsistency convention, `running_stats.py` no-lookahead/entering-game convention, storage backward-compatibility constraint, urlencode/Jinja-only escaping convention.

---
*Pitfalls research for: cfb_system_maker v1.1 Season Readiness*
*Researched: 2026-08-26*

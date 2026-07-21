---
phase: 05-dashboard-current-matches
plan: 06
subsystem: web
tags: [dashboard, current-matches, play-text, fade-inversion, offseason-fallback, jinja]
status: complete

requires:
  - "05-01 (upcoming.csv + upcoming_meta.json + storage.load_upcoming_games/load_upcoming_meta)"
  - "05-04 (upcoming_features.json + enrich.load_features_from/upcoming_features_path)"
  - "05-03 (dashboard shell, reserved right column, _saved_systems_newest_first, _system_type_label)"
  - "backtest.matches_system(require_played=False) (05-02, D-18)"
  - "backtest._side_spread / describe.describe"
provides:
  - "Current Matches panel on the dashboard (DASH-03)"
  - "web._current_matches_panel / _play_text / _parse_kickoff / _kickoff_label"
affects:
  - cfb_system_maker/web.py
  - cfb_system_maker/templates/dashboard.html
  - cfb_system_maker/static/styles.css
  - tests/test_web.py

tech-stack:
  added: []
  patterns:
    - "play text derived from the SAME normalization grade_bet applies, never from the declared side (D-08)"
    - "match-never-grade: matches_system(require_played=False), grade_bet never called in the request path (D-18)"
    - "describe() reused undecorated for matched-filter details (D-13)"
    - "missing/unparseable upcoming file degrades to a documented panel state, never a crash"

key-files:
  created: []
  modified:
    - cfb_system_maker/web.py
    - cfb_system_maker/templates/dashboard.html
    - cfb_system_maker/static/styles.css
    - tests/test_web.py

decisions:
  - "Panel computed per-request (not cached). Matching is a few hundred field comparisons with no permutation test; a fresh read IS the CLI-rerun invalidation the plan asked for. Deliberately did NOT add upcoming.csv to _data_fingerprint, which feeds the My Systems backtest cache that does not depend on upcoming files."
  - "Missing-upcoming-file degrades at the PANEL level (empty-state block naming the CLI command), not the whole page — games.csv exists so the systems table still renders."
  - "Each match renders as a stacked card (kickoff, play, matchup, system+type, details) at all widths; the panel is a 320-420px column that cannot hold a 6-column table, so this is both the desktop and the narrow-screen layout and the page never scrolls sideways."
  - "TBD kickoffs render date-only (departs from the UI-SPEC date-and-time form — a correctness fix, no fabricated clock time)."

metrics:
  duration: ~60 min
  completed: 2026-07-20
  tasks: 3
  tests_added: 15
---

# Phase 5 Plan 06: Current Matches Panel Summary

The dashboard now answers "what do I bet this week": for every saved system, the Current Matches panel lists each upcoming game it currently matches, with a play whose text mirrors exactly what would be graded — including fade inversion and the away-side sign flip — the fetch timestamp, the line-movement caveat, and the offseason backward-fallback state that is today's real path.

## What Was Built

**Task 1 — failing tests (commit `ba6147f`)**
14 end-to-end Flask-client tests covering: row emission for a matched system and omission for a non-matching one; spread play text for home and away sides; the discriminating fade assertion (a fade home-side system on a home favorite must name the AWAY team); total play text and its fade inversion; `describe()` details rendered undecorated; sort by kickoff then system name; the TBD date-only kickoff; all five panel states; and HTML escaping of a metacharacter-bearing team name and system name.

**Task 2 — data path and play-text derivation (commit `87fbf76`)**
`_current_matches_panel` reads only `upcoming.csv`, `upcoming_meta.json`, and `upcoming_features.json` through the storage/enrich loaders (D-02 — no fetch or CFBD module imported by the web layer). For each saved system × upcoming record it calls `matches_system(..., require_played=False)` (D-18) and never `grade_bet` — an upcoming game has no result. `_play_text` runs the same normalization `grade_bet` applies: it lowercases `side`, inverts it on `fade`, picks the team from the normalized side, and computes the line with `_side_spread` (which owns the away negation of the always-home spread); totals invert over/under on `fade`. `describe(system)` is called raw and only `row["text"]` is used (D-13).

**Task 3 — rendering and the five states (commit `484bbc1`)**
The reserved right column now carries the heading, the `Lines as of …` timestamp, and the `Matches change as lines move.` caveat (D-06), then the state-specific body. Each match is a stacked card. No new hex literal, no JavaScript, Jinja autoescaping throughout.

## Play-Text Derivation (D-08) — the load-bearing detail

Verified byte-for-byte against `grade_bet` (backtest.py:354-377) and `_grade_total_bet` (backtest.py:423-425). The fade case is the one a plausible-but-wrong implementation gets backwards: a fade home-side system matching a home favorite renders **"Play {away team} +N"**, not the favorite's name — confirmed by `test_current_matches_fade_home_side_names_the_away_team` and live (a home-favorite match rendered `Play Prairie View A&M -3` for the plain system; a fade of the same spot would name the away team). `describe()` still describes the *match* (e.g. "the team is a favorite"), which is intentionally distinct from the *bet* on a fade — D-13 by design, not reconciled.

## The five states

| State | Treatment |
|-------|-----------|
| Populated | Timestamp + caveat + rows |
| Offseason / fallback (meta `is_fallback`) | Amber `.stale-warning` notice AND the labelled fallback rows AND `Most recent week with data: Week N, season` — all three |
| Week present, no system matches | Neutral muted `No saved system matches a game this week.` (not amber) |
| No saved systems | Panel empty-state pointing at Example Systems (left column shows its own no-systems state — UI-SPEC: both columns) |
| Upcoming file missing/unparseable | Panel-level empty-state naming `python -m cfb_system_maker upcoming --data-dir data` (games.csv still renders the systems table) |

## Verification

| Check | Result |
|-------|--------|
| `.venv/Scripts/python.exe -m pytest` | **307 passed, 0 failed** (baseline 292; +15 tests) |
| Web module imports no fetch/CFBD/scrapers/graphql module | Confirmed by grep — panel is file-reads only (D-02) |
| Panel path calls `matches_system`, never `grade_bet` | Confirmed by grep over `_current_matches_panel` |
| No new hex literal in `styles.css` diff | Confirmed — all colors via `var()` tokens; amber reuses existing `.stale-warning` |
| `dashboard.html` script / `\|safe` count | 0 / 0 |
| **Live render against real CFBD data** | Generated `upcoming` into a scratch dir (games.csv/features.json copied from `data/`, `data/` untouched). Offseason backward fallback fired (2025 postseason week 1, 50 games). Panel rendered the amber notice, `Most recent week with data: Week 1, 2025`, real rows with real team names, `Play Over 53.5`, `Play Prairie View A&M -3`, local-time kickoffs, and `describe()` details. The real `start_date` serialization `'2025-12-13 17:00:00+00:00'` (space separator, `+00:00` offset) parses through `_parse_kickoff`; the real team name `Prairie View A&M` autoescaped to `A&amp;M`, confirming the XSS mitigation on live data. |

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] Scoped one pre-existing example-tab assertion to the left column**
- **Found during:** Task 3 full-suite run.
- **Issue:** `test_example_systems_tab_shows_figures_and_trend_column` asserted `"No saved systems yet" not in html` over the whole page. It was written when the panel was an empty placeholder; the panel now legitimately shows that copy when there are no saved systems (UI-SPEC: both columns show the no-systems state). The assertion's real intent is that the *left* column does not fall back to its empty state while examples render.
- **Fix:** Scoped the assertion to the `dash-main` section slice, preserving both the test's intent and the spec-faithful panel copy.
- **Files modified:** `tests/test_web.py`
- **Commit:** `484bbc1`

**2. [Rule 1 - Bug] Empty `describe()` details rendered a dangling "Matched on" label**
- **Found during:** post-implementation review.
- **Issue:** `describe()` keys off filter *flags*, so a bare `side="home"` system (the default new-system shape) returns `[]`, leaving the "Matched on" label over an empty `<ul>`. The Task-1 details test used `favorite=True` and never hit this common case.
- **Fix:** Wrapped the details block in `{% if row.details %}`; added `test_current_matches_bare_system_omits_the_matched_on_label`.
- **Files modified:** `cfb_system_maker/templates/dashboard.html`, `tests/test_web.py`
- **Commit:** `387890c` (recorded at commit time)

### Intentional Departures

**1. Panel computed per-request, not cached.** The plan said to "reuse the figure cache keying approach … extended to include the upcoming file's identity so a re-run of the CLI command invalidates panel results." Matching a handful of systems over ~50 upcoming games is a few hundred field comparisons with no permutation test — caching buys nothing, and a fresh per-request read *is* the invalidation the plan wants. Adding `upcoming.csv` to the existing `_data_fingerprint` would have wrongly coupled the My Systems backtest cache (which depends only on `games.csv`/`features.json`) to upcoming rebuilds. No cache was added; nothing to invalidate.

**2. TBD kickoffs render date-only** (as the plan's own `<interface_notes>`/`<action>` direct), departing from the UI-SPEC's date-and-time form. This is a deliberate correctness fix: fabricating a clock time on a page whose purpose is telling the user what to bet would be a factual error. **The UI-SPEC should be amended** to note the date-only variant for `startTimeTBD` games.

## Requirements Satisfied

| Decision | How |
|----------|-----|
| DASH-03 / D-12 | One panel, all saved systems' matches together |
| D-06 | `Lines as of …` timestamp + `Matches change as lines move.` caveat render unconditionally in the populated state |
| D-07 / D-20 | Offseason shows the amber notice AND the labelled backward-fallback rows |
| D-08 | Play text runs the same normalization `grade_bet` applies; fade inverts the play |
| D-13 | Matched-filter details reuse `describe()` undecorated |
| D-18 | `matches_system(require_played=False)`; `grade_bet` never called in the panel path |
| D-02 | Panel reads only local files; no fetch/CFBD import in the web layer |

## Threat Model Compliance

| Threat | Status |
|--------|--------|
| T-05-23 displayed play disagreeing with what would be graded | Play text runs `grade_bet`'s side/over-under normalization + `_side_spread`. The fade-names-away-team test fails if the declared side were used directly. |
| T-05-24 stored XSS via system/team names or sentences | Jinja autoescaping, never disabled. Metacharacter team + system names asserted escaped; confirmed on live CFBD data (`A&M` → `A&amp;M`). |
| T-05-25 missing/malformed upcoming file crashing the page | Reads wrapped; missing/unparseable → documented panel state naming the CLI command. Tested. |
| T-05-26 CFBD call inside a request | No fetch module imported; grep-confirmed file-reads only. |
| T-05-27 a second matching path in the web layer | Panel calls `matches_system` only; no filter logic reimplemented; grading never called. |
| T-05-28 stale lines presented as current | Timestamp + caveat unconditional; fallback state labelled with the week/season it came from, not presented as current. |
| T-05-SC package installs | None. |

## Known Stubs

None.

## Threat Flags

None — no new security-relevant surface beyond the plan's threat register.

## Self-Check: PASSED

- `.planning/phases/05-dashboard-current-matches/05-06-SUMMARY.md` — FOUND
- `cfb_system_maker/web.py` (modified) — FOUND
- `cfb_system_maker/templates/dashboard.html` (modified) — FOUND
- `cfb_system_maker/static/styles.css` (modified) — FOUND
- `tests/test_web.py` (modified) — FOUND
- Commits `ba6147f`, `87fbf76`, `484bbc1`, `387890c` — all FOUND in `git log`
- Full suite: 307 passed, 0 failed

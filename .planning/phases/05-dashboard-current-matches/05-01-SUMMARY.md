---
phase: 05-dashboard-current-matches
plan: 01
subsystem: data-pipeline
tags: [cfbd, upcoming-games, cli, storage, offseason-fallback]
status: complete

requires: []
provides:
  - "cfb_system_maker.upcoming.resolve_target_week / build_upcoming"
  - "storage.save_upcoming_games / load_upcoming_games / save_upcoming_meta / load_upcoming_meta"
  - "`upcoming` CLI subcommand"
  - "data/processed/upcoming.csv + upcoming_meta.json (runtime)"
  - "full-season data/raw/games_{season}.json + lines_{season}.json for the resolved season"
affects:
  - "Plan 05-04 (running-stats accumulation base rebuilt from the raw dumps)"
  - "Plan 05-06 (renders upcoming.csv + upcoming_meta.json)"

tech-stack:
  added: []
  patterns:
    - "injectable cfbd_module seam (mirrors scrapers.scrape) for network-free tests"
    - "reuse normalize_games / _select_line unchanged; _select_line returning None IS the D-04 exclusion"
    - "json.dumps(default=str) for every writer touching a CFBD datetime"

key-files:
  created:
    - cfb_system_maker/upcoming.py
    - tests/test_upcoming.py
  modified:
    - cfb_system_maker/storage.py
    - cfb_system_maker/cli.py
    - tests/test_cli.py

decisions:
  - "Fetch games and lines with season_type='both' rather than threading the resolved type into the fetch — a superset that keeps postseason weeks reachable in one round trip"
  - "save_upcoming_games takes (games, kickoffs) rather than a single pre-merged rows list, mirroring save_processed_games"
  - "Season derivation: January belongs to the previous season; every other month maps to now.year"

metrics:
  duration: ~35 min
  completed: 2026-07-20
  tasks: 3
  tests_added: 16
---

# Phase 5 Plan 01: Upcoming-Games Data Path Summary

Adds an `upcoming` CLI command that resolves the current CFB week from `GamesApi.get_calendar` — or falls back backward to the most recent week with completed games, across a season boundary if needed — fetches the full resolved season's games and lines, normalizes the target week through the existing join, and persists `upcoming.csv` + `upcoming_meta.json` without ever touching `games.csv`.

## What Was Built

**`cfb_system_maker/upcoming.py`** (new)

- `resolve_target_week(now, *, cfbd_module=None, token=None) -> WeekResolution` — season, week, season_type, is_fallback.
- `build_upcoming(data_dir, *, now=None, cfbd_module=None, token=None) -> UpcomingBuild` — records, kickoffs, meta; persists all of it.
- Resolution order: calendar window containing `now` → most recent completed week in that season → step back up to two seasons. Completed weeks are grouped by `(season_type, week)` and ranked by **latest start date, never by week number** — postseason weeks restart numbering, so a January bowl (postseason week 1) correctly beats a September regular week 2.
- Both entry points construct the client through the injected `cfbd_module`, so the entire test file runs with no network.

**`cfb_system_maker/storage.py`** — `save_upcoming_games` / `load_upcoming_games` (GameRecord field order plus trailing `start_date` and `start_time_tbd` columns; blank-to-None parsing preserved so unplayed rows read back as `None`, not `0`), and `save_upcoming_meta` / `load_upcoming_meta`.

**`cfb_system_maker/cli.py`** — `upcoming --data-dir` subcommand printing the resolved week and, on a fallback, a line naming the week used instead. Exits 0 in the offseason and in the terminal no-resolution case.

## Verification

**Full suite: 263 passed, 1 failed.** The single failure is `tests/test_web.py::test_dashboard_zero_bet_system_shows_em_dash_not_a_flat_line`, owned by the parallel Plan 05-03 and in flight at the time of this run. Zero failures in any file this plan touches.

Baseline note: the "214 passing" figure in the execution brief was stale. The suite measured **189 passed / 46 failed** at the start of this plan (Phase-5 tests for the not-yet-executed dashboard route move were already committed and red). Those web failures resolved as 05-03 landed during this execution. This plan added 16 tests and introduced zero failures.

**Live CFBD verification** (read-only, run against a scratch directory — `data/` untouched):

```
Resolved 2025 postseason week 1 (50 game(s)).
No current week had data; fell back to the most recent week with games (2025 postseason week 1).
```

This is the real cross-season offseason fallback firing on today's date, landing on a postseason week — the exact path the feature will be demoed on for weeks. Confirmed in the raw dumps: `games_2025.json` carries 3,831 rows across 19 `(season_type, week)` groups with 3,745 completed regular-season games, and `lines_2025.json` carries 1,597 rows covering 1,547 of them including week 1. Plan 05-04 can rebuild its accumulation base from disk alone.

`data/processed/games.csv` verified byte-identical (md5) before and after.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] CFBD `SeasonType` enum leaked its repr into persisted output**

- **Found during:** live verification after Task 3
- **Issue:** `upcoming_meta.json` recorded `"season_type": "SeasonType.POSTSEASON"` and the CLI printed the same. The vendored client returns an `aenum` `SeasonType` for `seasonType`; because it is a `str` mixin it round-trips correctly through `json.dumps`, but `str()` on it yields the qualified name, not the wire value. Fakes using plain strings could never surface this — a green suite alone would have shipped it into Plan 05-06's render.
- **Fix:** `_season_type` now reads `getattr(value, "value", value)`. Added `test_season_type_enum_is_normalized_to_its_value` with a fake whose `str()` and `.value` diverge, so the regression is locked.
- **Files modified:** `cfb_system_maker/upcoming.py`, `tests/test_upcoming.py`
- **Commit:** 3edd09a

### Intentional Departures

**1. Fetch uses `season_type="both"` instead of threading the resolved type into the fetch call**

The plan's Task 2 action says `get_games(year=season, season_type=...)` with the resolved type. `SeasonType.BOTH` is a documented enum value (`cfbd-python/cfbd/models/season_type.py`) and was verified live. Using it is a strict superset: it lets the backward fallback discover a postseason week in one round trip instead of two, and it makes the raw dumps carry regular **and** postseason games for Plan 05-04. The resolved `season_type` is still threaded — into the target-week slice and into the meta — so D-19 is honored; only the fetch is broadened. Verified live: the postseason fallback resolves and fetches correctly.

**2. `save_upcoming_games(data_dir, games, kickoffs)` instead of `save_upcoming_games(data_dir, rows)`**

The literal single-`rows` signature would have forced `upcoming.py` to pre-merge `GameRecord` dataclasses with kickoff dicts into anonymous dicts. Taking the two arguments separately mirrors `save_processed_games(data_dir, games)` more closely and keeps the merge inside the writer. `load_upcoming_games` returns the symmetric `(records, kickoffs)` tuple.

## Requirements Satisfied

| Decision | How |
|----------|-----|
| D-01 | Separate `upcoming.csv`; no `games.csv` literal in `upcoming.py`/`storage.py`'s new code; CLI test asserts it is not created; md5 verified unchanged |
| D-02 | Produced by the CLI only; no Flask surface added |
| D-03 | Target week only in the output rows |
| D-04 | `_select_line` returning `None` is the whole exclusion — no new logic; tested for both "no line row" and "line row with no usable spread or total" |
| D-06 | `fetched_at` in meta |
| D-07 / D-20 | Backward fallback, same-season and cross-season, both tested and exercised live |
| D-19 | `season_type` threaded through resolution, slicing, and meta; postseason resolves via calendar window and via fallback |

## Threat Model Compliance

| Threat | Status |
|--------|--------|
| T-05-01 token disclosure | Token passed only into `Configuration`; never printed, never written to CSV/JSON. CLI test asserts the token string is absent from stdout. |
| T-05-02 payload tampering | All numeric fields flow through `normalize_games` and the existing optional-parse conventions. |
| T-05-03 offseason DoS | Bounded to two seasons back; no-resolution branch writes a valid header-only CSV and meta with `row_count: 0`, exits 0. Tested. |
| T-05-05 accidental `games.csv` write | Structurally enforced; asserted in two tests and verified by md5 on the real file. |

No new threat surface beyond the register.

## Known Stubs

None.

## Self-Check: PASSED

- `cfb_system_maker/upcoming.py` — FOUND
- `tests/test_upcoming.py` — FOUND
- `cfb_system_maker/storage.py` (modified) — FOUND
- `cfb_system_maker/cli.py` (modified) — FOUND
- Commits 3494521, 6bbc153, 3edd09a, 743e69d — all FOUND in `git log`

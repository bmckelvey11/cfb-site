---
task: line-movement-registry-features
date: 2026-08-27
mode: quick
status: complete
---

# Quick Task 260827-b9w — Summary

Four new registry features shipped: `spread_open`, `spread_move`, `total_open`, `total_move`
— book-matched line movement, computed in `enrich.py` and surfaced via `features.json`.
No `GameRecord`/CSV change.

## What landed

- **`cfb_system_maker/enrich.py`** — new `computed_line_move` source kind and
  `_build_line_move_index(data_dir, seasons, games)`. Per season, re-selects the close
  provider's row via `normalize._select_line`/`_select_total` (never the flattened
  `_index_raw_lines` used by legacy `spreadOpen`/`overUnderOpen`), so an open is only
  read off the SAME book row that supplied the built close. `spread_move = game.spread
  - spread_open`; `total_move = game.total - total_open`; missing open -> all four
  `None` (fail closed, no zero defaults).
- **`cfb_system_maker/features.py`** — `"computed_line_move"` added to the
  `SourceKind` Literal; four `FeatureDef`s registered in the `betting_lines` group
  (`join="game_id"`, `team_scoped=False`, `control="numeric"`). Descriptions state the
  home-perspective sign (matching `GameRecord.spread`), the close-provider-match
  coverage caveat, and that `total_open`/`total_move` may come from a different book
  than the spread's (per existing `_select_total` fallback).
- **`cfb_system_maker/search.py`** — new `_LOW_COVERAGE_KEYS` frozenset
  (`spread_open`, `spread_move`, `total_open`, `total_move`) subtracted from
  `_CANDIDATE_FEATURES`. These are genuine pregame values, not lookahead, but populated
  on only ~18% of games (2023-2025 subsample of book-matched closes) — a non-random
  slice that would let automated search report a small-subsample finalist through the
  same statistical pipeline as a full 13k-game backtest. Excluded from automated
  candidate generation; fully available for manual system building. Reversible: delete
  a key from the frozenset to opt back in.
- **Tests** — `tests/test_enrich.py`: three new cases covering (1) the open read from
  the close provider's row when a sibling provider carries a different open, with a
  home-favorite-lengthening fixture (`open -3.0` -> `close -7.0`, `spread_move ==
  -4.0`) so the sign is load-bearing; (2) all four `None` when the close provider's row
  has no open but a different provider does (the cross-book guard, and the shape that
  actually happens in production: consensus close, Bovada open); (3) all four `None`
  when no open values exist anywhere. `tests/test_search.py`: one new case asserting
  `expand_candidates` never emits a `FeatureFilter` on any of the four low-coverage
  keys.

## Verification

- Targeted: `tests/test_enrich.py tests/test_features.py tests/test_search.py` — 68
  passed.
- Full suite: 555 passed, 1 skipped, 3 deselected (`.venv/Scripts/python.exe -m
  pytest`, run from the shared repo venv since the worktree has no local `.venv`).
- Reran `enrich --data-dir data` against the project's real data directory (the
  worktree itself has no `data/` — it's gitignored — so this ran against the main
  repo's `data/` on disk, the only copy that exists) and measured coverage against the
  plan's pre-computed baseline:

  | season | games | spread_open | total_open |
  |---|---|---|---|
  | 2013-2020 | 6,301 | 0 (0%) | 0 (0%) |
  | 2021 | 849 | 7 (1%) | 7 (1%) |
  | 2022 | 1,413 | 17 (1%) | 17 (1%) |
  | 2023 | 1,347 | 659 (49%) | 605 (45%) |
  | 2024 | 1,507 | 772 (51%) | 342 (23%) |
  | 2025 | 1,597 | 862 (54%) | 408 (26%) |
  | **total** | **13,014** | **2,317 (17.8%)** | **1,379 (10.6%)** |

  Exact match to the plan's measured baseline. Confirmed the regenerated sidecar's
  `_meta.registry_version` matches the current code's `registry_version()` (stale-
  sidecar warning cleared).
- Confirmed `web.py`'s `_feature_options` iterates `FEATURE_REGISTRY` and groups by
  `feature.group`, with `"betting_lines"` already in the sidebar ordering tuple — the
  four new features appear automatically with no endpoint change; `/filter-detail` is
  registry-generic. Not manually clicked through the running UI (no server launched
  for this quick task).
- **Row-selection invariant, independently re-checked against the current on-disk
  data** (not just the count match, which only proves this implementation reproduces
  the planner's simulation): for every one of the 2,317 games with a non-null
  `spread_open`, re-ran `_select_line(lines, game.provider)` and asserted
  `selected["spread"] == game.spread` — 0 mismatches. For every one of the 1,379 games
  with a non-null `total_open`, re-ran `_select_total` and asserted the resolved total
  equals `game.total` — 0 mismatches. This matters because `data/raw/` was
  re-scraped (2026-08-27 07:09) after `data/processed/games.csv` was built
  (2026-08-26 20:21); a stale raw/build pairing could have silently reselected a
  different provider's row than the one that produced the build, reintroducing exactly
  the cross-book basis difference the plan's findings section rejects. It didn't —
  both legs check out clean on the data as it stands today.

## Deviations from Plan

None — plan executed exactly as written, including the design decisions (sign
convention kept per the plan's correction, `betting_lines` group reused, legacy
`spreadOpen`/`overUnderOpen` untouched, `spread_move_band` skipped as out of scope).

## Notes

- Registry version hash changed (new `ba927d337b76`) — any other `features.json`
  sidecar on disk that hasn't been through this `enrich` rerun will show the stale-
  registry warning in the web UI until it is regenerated.
- `data/processed/features.json` in the main repo (`C:\Users\mckel\dev\cfb-site\data`)
  was regenerated as part of Task 2's verification. This file is gitignored and lives
  outside the worktree filesystem; the worktree has no local copy of `data/`.

## Self-Check: PASSED

All created/modified files present on disk; commit `3f1d9aa` found in git log.

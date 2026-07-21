---
phase: 05-dashboard-current-matches
plan: 04
subsystem: data-pipeline
tags: [enrichment, running-stats, no-lookahead, features-sidecar, upcoming-games]
status: complete

requires:
  - "05-01 (full-season raw games/lines dumps on disk)"
provides:
  - "cfb_system_maker.upcoming.enrich_upcoming"
  - "enrich.save_features_to / load_features_from / upcoming_features_path"
  - "data/processed/upcoming_features.json (runtime)"
affects:
  - "Plan 05-06 (may read upcoming_features.json through load_features_from)"
  - "any saved system with season-to-date filters evaluated against upcoming games"

tech-stack:
  added: []
  patterns:
    - "accumulation base rebuilt from disk, not shared in memory across plans"
    - "explicit-path sibling writer instead of reusing a fixed-path writer"
    - "empty-list guard on enrich_games, whose `games or load_processed_games` fallback is a silent trap"

key-files:
  created: []
  modified:
    - cfb_system_maker/upcoming.py
    - cfb_system_maker/enrich.py
    - tests/test_upcoming.py
    - tests/test_enrich.py

decisions:
  - "Pass the UNION to enrich_games and post-filter the output to target-week ids, rather than adding an only_ids parameter — keeps enrich_games' signature untouched (surgical-changes rule)"
  - "Target-week ids are excluded from the accumulation base, because in the offseason fallback the target games are themselves completed and would otherwise be folded in twice"
  - "The no-resolution path writes an empty-but-valid sidecar so all three output files always exist together"

metrics:
  duration: ~25 min
  completed: 2026-07-20
  tasks: 2
  tests_added: 11
---

# Phase 5 Plan 04: Upcoming-Games Feature Enrichment Summary

Rebuilds the running-stats accumulation base from the full-season raw dumps on disk and unions it with the target week before enrichment, so an unplayed game receives real entering-game season-to-date values instead of the nulls that would make every season-to-date filter silently match nothing (D-05).

## What Was Built

**`cfb_system_maker/upcoming.py`**

- `enrich_upcoming(data_dir, season, records) -> dict` — the whole D-05 guarantee. Loads `raw/games_{season}.json` + `raw/lines_{season}.json`, selects completed rows, runs them through `normalize_games` against the **full-season** line set, unions the result with the target-week records, calls `enrich_games` over that union, then emits feature rows for the target-week ids only. Writes `processed/upcoming_features.json`.
- `_accumulation_base(...)` — the completed half. Two things it deliberately does: excludes the target-week ids (in the offseason fallback the target games *are* completed, so they would be folded in twice), and returns `[]` rather than raising when the raw dumps are absent.
- Wired into `build_upcoming` on both branches, so one CLI run produces `upcoming.csv`, `upcoming_meta.json`, and `upcoming_features.json` together.

**`cfb_system_maker/enrich.py`**

- `save_features_to(path, features)` — the sibling writer taking an explicit path; `save_features` now delegates to it. Same `{_meta, games}` envelope.
- `load_features_from(path)` — symmetric reader; `load_features(data_dir)` delegates. Both refactors are behavior-preserving.
- `upcoming_features_path(data_dir)`.

`cfb_system_maker/running_stats.py` was **not modified** — `git diff` on it is empty. Its snapshot-before-accumulation and null-score-skip behavior already gives the entering-game guarantee for unplayed games; no special-casing was added.

## Verification

**Full suite: 292 passed, 0 failed.** (Baseline was 264; this plan added 11 tests, 05-05 added the rest during the same wave.)

**Real-command verification** — `python -m cfb_system_maker upcoming --data-dir <scratch>` against live CFBD, `data/` untouched:

```
Resolved 2025 postseason week 1 (50 game(s)).
processed/: upcoming.csv  upcoming_features.json  upcoming_meta.json

meta: {'game_count': 50, 'registry_version': 'd8c8e1540160'}
('401769070', 13, 13, 0.9231, 0.8333)   # id, home GP, away GP, home win%, home ATS%
('401769072', 13, 14, 1.0,    0.6154)
('401769074', 14, 14, 1.0,    0.6429)
non-zero home games_played: 50 of 50
null home games_played: 0
```

Every one of the 50 bowl-week games carries 13–14 prior games with real win and ATS percentages. This is the assertion that matters: had the accumulation base been built from the target week alone — or silently emptied by a target-week-only lines dump — every one of these would read `0` / `None`, with no error anywhere.

`data/processed/features.json` md5 `8f311d747842e142883b78a10876da5c` — identical before and after the run.

## Deviations from Plan

### Intentional Departures

**1. `enrich_games` is called with the UNION, not with the upcoming records alone**

The plan's Task 2 prose says "reuse `enrich_games` with the upcoming records", which contradicts its own concrete load path four paragraphs earlier. `enrich_games` → `_build_indexes` → `_build_running_index` calls `compute_running_stats` over *exactly* the list it is handed, so passing only the target records reproduces the precise null-feature failure this plan exists to prevent. The union is passed and the output is filtered to target-week ids, which satisfies both "emit target-week ids only" and the accumulation requirement.

**2. Output filtered post-hoc rather than adding an `only_ids` parameter**

Both were viable. Post-filtering leaves `enrich_games`' signature untouched, per the surgical-changes rule in CLAUDE.md. The cost is computing throwaway feature rows for the season's completed games — bounded to one season, run from the CLI, and consistent with T-05-17's accepted disposition.

**3. Empty-union guard added (not in the plan)**

`enrich_games` opens with `games = games or load_processed_games(data_dir)`. Handed an empty list it would silently load the 13k-row historical `games.csv` and write those features into the upcoming sidecar. `enrich_upcoming` skips the call and writes an empty-but-valid sidecar instead. This is a Rule 2 correctness requirement, not a feature — the failure would have been silent and would have shipped wrong data to the dashboard.

### Test-Fixture Note

The plan asked that the fixture "be able to express the broken shape". The end-to-end fake cannot: `build_upcoming` always writes full-season lines. So `enrich_upcoming` was made independently callable, and `tests/test_enrich.py` writes the raw files directly — once with a full-season lines dump (asserting `games_played == 4`) and once with a target-week-only dump (asserting `0` / `None`). Without that paired contrast, the non-null assertion would not prove the failure was reachable.

## Requirements Satisfied

| Decision | How |
|----------|-----|
| D-05 | Upcoming games run through `enrich_games` — the same feature path historical games use — over an accumulation base that includes the season's completed weeks |
| No-lookahead | `compute_running_stats` reused unchanged; an unplayed game has null scores and is skipped during accumulation, so it contributes to no other game's state. Asserted directly: Alpha appears in two unplayed week-5 games and reads `games_played == 4` in both |

## Threat Model Compliance

| Threat | Status |
|--------|--------|
| T-05-14 historical sidecar overwritten | `save_features`' fixed path is never reused. `save_features_to` takes an explicit path. A test records `features.json` bytes before the run and asserts them unchanged after; the real file's md5 was verified identical across the live run. |
| T-05-15 lookahead contamination | `running_stats.py` diff is empty. Two unplayed games sharing a team assert equal, uncontaminated entering-game values. |
| T-05-16 placeholder values for null features | No fallbacks or defaults added. Week-1 nulls are asserted as *correct*, and the unlined-completed-game drop is asserted rather than papered over. |
| T-05-17 full-season enrichment cost | Accepted as planned; bounded to one season, CLI-only. |
| T-05-SC package installs | None. |

## Known Stubs

None.

## Self-Check: PASSED

- `cfb_system_maker/upcoming.py` (modified) — FOUND
- `cfb_system_maker/enrich.py` (modified) — FOUND
- `tests/test_upcoming.py` (modified) — FOUND
- `tests/test_enrich.py` (modified) — FOUND
- `data/processed/upcoming_features.json` written at runtime — verified in scratch dir
- Commits e06c82d, c00bb76 — both FOUND in `git log`

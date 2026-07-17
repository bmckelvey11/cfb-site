---
phase: 03-data-depth-breadth
plan: 04
subsystem: data
tags: [feature-registry, player-aggregation, no-lookahead, cfbd, team-preseason]

# Dependency graph
requires:
  - phase: 03-data-depth-breadth
    provides: feature registry, enrich pipeline, team_season join path (03-01)
provides:
  - New prior_off_wepa team_preseason feature (raw prior-season team offensive wEPA)
  - New raw_player_agg SourceKind + prior-season player-aggregation index builder
  - Prior-season keying ((team, S) populated from adjusted_player_passing_{S-1}.json) as the no-lookahead guarantee
affects: [ui-filter-popups, feature-registry, enrich, bet-labs-parity]

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "Prior-season player-to-team aggregation keyed (team, S) from the S-1 file — no-lookahead preseason signal"
    - "Numeric-safe sum with team stored only when >=1 valid numeric wepa, so absent/empty file or missing team fails closed to None (no pre-seeded 0.0)"

key-files:
  created: []
  modified:
    - cfb_system_maker/enrich.py
    - cfb_system_maker/features.py
    - tests/test_enrich.py
    - tests/test_features.py

key-decisions:
  - "Passing wEPA only — rushing wEPA (adjusted_player_rushing) deferred as an optional later extension (Simplicity First); the distinct-signal contract is already satisfied by prior-season team offensive wEPA"
  - "Dedicated raw_player_agg index (not reused raw_team_season shared bucket), so no source_file needed and the lookup reads record.get(field) directly"
  - "Fail-closed emerges from the data structure: only teams with a valid numeric wepa get a key, so team-absent and empty-file both yield None for free (no try/except, matching _index_* house style)"

patterns-established:
  - "Prior-season-as-preseason aggregation: the sole no-lookahead surface for a season-total player metric is the prior season rolled to the current team-season"

requirements-completed: [DATA-02]

coverage:
  - id: D1
    description: "prior_off_wepa for a 2023 game equals the sum of 2022 player wEPA only; the 2023 same-season sentinel (99.0) never leaks"
    requirement: DATA-02
    verification:
      - kind: integration
        ref: "tests/test_enrich.py#test_enrich_prior_off_wepa_uses_prior_season_only"
        status: pass
    human_judgment: false
  - id: D2
    description: "prior_off_wepa is None when the prior-season file is absent or the team is missing from it (fails closed)"
    requirement: DATA-02
    verification:
      - kind: integration
        ref: "tests/test_enrich.py#test_enrich_prior_off_wepa_none_when_prior_file_absent"
        status: pass
    human_judgment: false
  - id: D3
    description: "prior_off_wepa registered as a distinct team_preseason / raw_player_agg / team_scoped feature"
    requirement: DATA-02
    verification:
      - kind: unit
        ref: "tests/test_features.py#test_prior_off_wepa_is_team_preseason_player_agg"
        status: pass
    human_judgment: false

# Metrics
duration: 12min
completed: 2026-07-17
status: complete
---

# Phase 3 Plan 04: Prior-Season Player-Aggregated Offensive wEPA Summary

**A minimal, distinct, no-lookahead `prior_off_wepa` team_preseason feature — a team's season-S value is the raw sum of its players' wEPA from `adjusted_player_passing_{S-1}.json` only, sentinel-proven that the current season never leaks.**

## Performance

- **Duration:** ~12 min
- **Tasks:** 2 (TDD RED/GREEN)
- **Files modified:** 4

## Accomplishments
- New `raw_player_agg` `SourceKind` and `_index_prior_player_agg` builder that aggregates the PRIOR season's per-player passing wEPA into `(team, S)` team totals — the prior-season keying is the no-lookahead guarantee (season S reads S-1 players only, D-05/D-06).
- New `FeatureDef` `prior_off_wepa` (group `team_preseason`, source_kind `raw_player_agg`, join `team_season`, `team_scoped=True`) surfaced end-to-end as `home_/away_prior_off_wepa` via a new `_lookup_team_scoped` branch.
- Distinct from the existing `returning_ppa`/`returning_usage`: this is raw prior-season *team* offensive wEPA (not returning-player-weighted), so it is not redundant.
- Fails closed: numeric-safe sum, teams stored only when they have ≥1 valid numeric wepa, so an absent/empty prior file (e.g. the 2-byte `adjusted_player_passing_2012.json`) or a missing team yields `None`.

## Task Commits

TDD cycle, committed atomically:

1. **Task 1: RED — failing prior-season no-lookahead test for prior_off_wepa** - `e8ae76d` (test)
2. **Task 2: GREEN — wire prior_off_wepa end-to-end (SourceKind + prior-season index + lookup + registry row)** - `0c40710` (feat)

## Files Created/Modified
- `cfb_system_maker/features.py` - Added `"raw_player_agg"` to the `SourceKind` Literal; added the `prior_off_wepa` `FeatureDef`.
- `cfb_system_maker/enrich.py` - Added `"raw_player_agg": {}` to `_build_indexes`; populated it per-season from the `{S-1}` file; added the `_index_prior_player_agg` helper and a `raw_player_agg` branch in `_lookup_team_scoped`.
- `tests/test_enrich.py` - Prior-season no-lookahead test (2022→5.0, 2023 sentinel 99.0 never leaks, Beta absent→None) + absent-prior-file fails-closed test.
- `tests/test_features.py` - `test_prior_off_wepa_is_team_preseason_player_agg` registry-shape assertion.

## Decisions Made
- **Passing wEPA only** — rushing wEPA (`adjusted_player_rushing_{season}.json`) is a defensible later extension but is not needed to satisfy the distinct-signal contract; not built now (Simplicity First). Noted here per the plan.
- **Dedicated `raw_player_agg` index** rather than reusing the shared `raw_team_season` bucket — so the `FeatureDef` needs no `source_file` and the lookup returns `record.get(field)` directly.
- **Fail-closed from data structure, not extra code** — only teams with a valid numeric wepa get an index key, so team-absent and empty-file both return `None` without a try/except, matching the existing `_index_*` house style.

## Deviations from Plan

None - plan executed exactly as written.

## Issues Encountered
None.

## User Setup Required
None - no external service configuration required.

Note: `registry_version()` advanced to `d8c8e1540160` (from the 03-01 value `fd4965ea44f3`), so the web UI will show a stale-sidecar warning until `python -m cfb_system_maker enrich --data-dir data` is re-run to regenerate `data/processed/features.json` (D-07, expected; `data/` is gitignored — runtime regeneration, not a committed artifact). Many 2013-era games will have `null` `prior_off_wepa` because their prior-season player file (e.g. `adjusted_player_passing_2012.json`) is empty — fails closed as designed.

## Next Phase Readiness
- D-05 is closed with the minimal correct implementation; `prior_off_wepa` is a live, distinct, no-lookahead `team_preseason` filter ready for the downstream UI filter-popup work.
- Optional extension available if desired later: add rushing wEPA (`adjusted_player_rushing`) alongside passing for a combined prior-season offensive signal.

## Self-Check: PASSED

- SUMMARY.md: FOUND
- Commit e8ae76d (Task 1 test): FOUND
- Commit 0c40710 (Task 2 feat): FOUND
- Full test suite: 177 passed

---
*Phase: 03-data-depth-breadth*
*Completed: 2026-07-17*

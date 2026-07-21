---
phase: 03-data-depth-breadth
plan: 01
subsystem: data
tags: [feature-registry, running-stats, no-lookahead, cfbd, advanced-stats]

# Dependency graph
requires:
  - phase: 02-integrity-fade-grade
    provides: feature registry, computed_running PPA to-date path, enrich pipeline
provides:
  - Four new season_to_date computed_running features (Off/Def Success Rate, Off/Def Explosiveness) as entering-game to-date accumulations
  - compute_running_stats adv kwarg + adv_* output keys with write-before-fold no-lookahead guarantee
  - enrich adv index over advanced_game_stats_{season}.json with numeric fail-closed coercion
affects: [ui-filter-popups, feature-registry, enrich, bet-labs-parity]

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "Loop-driven adv accumulation in compute_running_stats keyed by _ADV_FIELDS map (output-key -> adv inner-key)"
    - "_coerce_numeric fail-closed guard: dict/bool/non-numeric CFBD field -> None, never raises inside enrich"

key-files:
  created: []
  modified:
    - cfb_system_maker/running_stats.py
    - cfb_system_maker/enrich.py
    - cfb_system_maker/features.py
    - tests/test_running_stats.py
    - tests/test_features.py
    - tests/test_enrich.py

key-decisions:
  - "Advanced stats accumulated as game-average (parity with PPA path, matches 9.99-sentinel test), not play-weighted (methodology decision A2)"
  - "Refactored adv accumulation to a loop over _ADV_FIELDS map rather than four repeated sum/count variable sets (DRY, identical logic)"
  - "adv-dict inner keys are unprefixed (success_off); output-dict keys and FeatureDef.field are prefixed (adv_success_off) — the enrich->compute seam"

patterns-established:
  - "Numeric fail-closed coercion for untrusted CFBD JSON fields (isinstance float/int and not bool, else None)"
  - "No-lookahead write-before-fold extended to a family of registry-driven fields via a shared field map"

requirements-completed: [DATA-02]

coverage:
  - id: D1
    description: "To-date Off Success Rate (running_success_off) computed from strictly-prior same-season games only, None on first game, no self-leak"
    requirement: DATA-02
    verification:
      - kind: unit
        ref: "tests/test_running_stats.py#test_running_adv_success_off_is_average_of_prior_games_only"
        status: pass
      - kind: integration
        ref: "tests/test_enrich.py#test_enrich_surfaces_running_success_off_from_prior_games"
        status: pass
    human_judgment: false
  - id: D2
    description: "To-date Def Success Rate + Off/Def Explosiveness (3 more computed_running features), season-reset and start_date-ordering respected"
    requirement: DATA-02
    verification:
      - kind: unit
        ref: "tests/test_running_stats.py#test_running_adv_explosiveness_respects_season_reset_and_start_date_order"
        status: pass
      - kind: unit
        ref: "tests/test_features.py#test_season_to_date_fields_match_running_stats_output"
        status: pass
    human_judgment: false
  - id: D3
    description: "enrich adv index fail-closed: dict-shaped/non-numeric successRate becomes None, enrich does not raise (T-03-01-01 mitigation)"
    requirement: DATA-02
    verification:
      - kind: integration
        ref: "tests/test_enrich.py#test_enrich_success_off_fails_closed_on_dict_shaped_field"
        status: pass
    human_judgment: false
  - id: D4
    description: "registry_version() advanced from phase-3 baseline 69084ed55504 (now fd4965ea44f3); web stale-sidecar warning expected until enrich re-runs (D-07)"
    requirement: DATA-02
    verification:
      - kind: unit
        ref: "tests/test_features.py#test_registry_version_changed_from_phase3_baseline"
        status: pass
    human_judgment: false

# Metrics
duration: 20min
completed: 2026-07-17
status: complete
---

# Phase 3 Plan 01: To-Date Advanced Team Stats Summary

**Four new entering-game (to-date) advanced features — Off/Def Success Rate and Off/Def Explosiveness — wired into FEATURE_REGISTRY via the existing PPA no-lookahead path, sourced from advanced_game_stats_{season}.json with fail-closed numeric coercion.**

## Performance

- **Duration:** ~20 min
- **Tasks:** 3
- **Files modified:** 6

## Accomplishments
- `compute_running_stats` gained an `adv` kwarg and four `adv_*` output keys, each a strictly-prior game-average with write-before-fold (no self-leak, season reset, start_date ordering).
- `enrich._build_running_index` builds a new `adv` index over `advanced_game_stats_{season}.json`, numeric-guarded so a dict-shaped or non-numeric `successRate` becomes `None` instead of crashing enrich.
- Four new `FeatureDef` rows (`running_success_off/def`, `running_explosiveness_off/def`) surfaced end-to-end via the unchanged `computed_running` `_lookup` branch as `home_/away_` variants.
- `registry_version()` advanced from the phase-3 baseline `69084ed55504` to `fd4965ea44f3` (D-07 contract).

## Task Commits

TDD cycle, committed atomically:

1. **Task 1: RED — failing no-lookahead test for to-date Off Success Rate** - `bc6aed7` (test)
2. **Task 2: GREEN — wire Off Success Rate to-date end-to-end** - `cf3dcbf` (feat)
3. **Task 3: Add Def Success Rate + Off/Def Explosiveness to-date** - `abd49c3` (feat)

## Files Created/Modified
- `cfb_system_maker/running_stats.py` - Added `adv` kwarg; `_ADV_FIELDS` map drives loop-based accumulation; write-before-fold for the 4 fields.
- `cfb_system_maker/enrich.py` - Built the `adv` index from `advanced_game_stats_{season}.json`; added `_coerce_numeric` fail-closed helper; passes `adv=` into `compute_running_stats`.
- `cfb_system_maker/features.py` - Added 4 `season_to_date` / `computed_running` `FeatureDef` rows.
- `tests/test_running_stats.py` - New Off-Success-Rate no-lookahead test + explosiveness season-reset/ordering test; updated 2 literal-dict asserts with the 4 new keys.
- `tests/test_features.py` - Extended `RUNNING_KEYS` and expected field set; added `test_registry_version_changed_from_phase3_baseline`.
- `tests/test_enrich.py` - Added a concrete-value enrich wiring test and a fail-closed dict-shaped-field test.

## Decisions Made
- **Game-average, not play-weighted** (methodology decision A2): parity with the PPA path and the existing `9.99`-sentinel leak test; `advanced_game_stats` does carry `plays`/`drives` but play-weighting was not adopted.
- **Loop over `_ADV_FIELDS`** instead of four repeated sum/count variable blocks — identical logic across the 4 fields, keeps write-before-fold semantics while staying DRY.

## Deviations from Plan

None - plan executed exactly as written. (The advisor-recommended concrete-value enrich assertion and the dict-shaped fail-closed test are both explicitly called for by the plan's Task 2 action and must_have #6 / threat T-03-01-01; no scope was added beyond the plan.)

## Issues Encountered
None.

## User Setup Required
None - no external service configuration required.

Note: `registry_version` changed, so the web UI will show a stale-sidecar warning until `python -m cfb_system_maker enrich --data-dir data` is re-run to regenerate `data/processed/features.json` (D-07, expected; `data/` is gitignored — runtime regeneration, not a committed artifact).

## Next Phase Readiness
- Four new filterable to-date advanced features are live end-to-end (compute -> enrich -> registry), satisfying SC-2 (new filter categories available).
- D-04 preseason talent/recruiting features confirmed already wired (features.py:79-133), untouched.
- Ready for downstream UI filter-popup work to expose the new features.

## Self-Check: PASSED

- SUMMARY.md: FOUND
- Commit bc6aed7 (Task 1 test): FOUND
- Commit cf3dcbf (Task 2 feat): FOUND
- Commit abd49c3 (Task 3 feat): FOUND
- Full test suite: 171 passed

---
*Phase: 03-data-depth-breadth*
*Completed: 2026-07-17*

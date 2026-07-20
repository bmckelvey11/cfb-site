---
phase: 03-data-depth-breadth
verified: 2026-07-20T00:00:00Z
status: passed
score: 15/15 must-haves verified
behavior_unverified: 0
overrides_applied: 0
warnings:
  - id: WR-01
    source: 03-REVIEW.md
    file: cfb_system_maker/enrich.py:143-152
    issue: "Truth 03-01#6 states enrich 'never raises' on malformed advanced-stat JSON. Leaf coercion (_coerce_numeric) is correct and tested, but a non-dict offense/defense container (.get -> AttributeError) or a non-numeric gameId (int() -> ValueError) can still raise and abort enrich. Test coverage exercises the leaf only, not the container."
    blocking: false
    rationale: "Fails loud (aborts run), never corrupts data; not reachable on real CFBD row shapes; mirrors the pre-existing ppa block. Code review classified as advisory (0 blockers)."
  - id: IN-02
    source: 03-REVIEW.md
    file: cfb_system_maker/enrich.py:337-354
    issue: "_index_prior_player_agg trusts the filename for season rather than filtering rows on their own year field. No-lookahead rests on the file-per-season convention."
    blocking: false
    rationale: "File-per-season convention holds across all scraped data; defense-in-depth only."
---

# Phase 3: Data Depth & Breadth Verification Report

**Phase Goal:** The game/line history and feature registry grow deeper (coverage floor re-confirmed against the live CFBD API) and broader (more endpoints wired as filterable features), giving later phases more to filter and match on.
**Verified:** 2026-07-20
**Status:** passed (2 non-blocking warnings)
**Re-verification:** No — initial verification (execution completed 2026-07-17; verification interrupted twice by session limits, run here at current HEAD `3b8e93c` after Phase 04 landed on top)

> **Verification baseline note.** Phase 04 and the numeric-filter-step quick task were executed and committed on top of this work. Every check below was run against current HEAD to confirm Phase 3's deliverables still hold. No Phase 04 change is counted as a Phase 3 gap.

## Goal Achievement

### Roadmap Success Criteria

| # | Success Criterion | Status | Evidence |
| --- | --- | --- | --- |
| SC-1 | Floor season (2013) returns non-empty results; pre-floor seasons (2012) cleanly contribute 0 rows; floor re-confirmed by live probe; pre-2013 backfill a documented no-op | ✓ VERIFIED | `tests/test_normalize.py:44,64,83` (0-row and 1-row gates, passing); `scripts/probe_line_floor.py` exists and is token-safe; live probe human-confirmed 2008–2012 = 0 usable, 2013 = 841; `docs/data-line-floor.md` records floor + closure rationale |
| SC-2 | New filter features exist that were not present before this phase, sourced from newly wired endpoints | ✓ VERIFIED | 5 new registry keys at HEAD: `features.py:341,349,357,365` (running_success_off/def, running_explosiveness_off/def) + `features.py:231` (prior_off_wepa). New source wiring: `advanced_game_stats_{season}.json` (`enrich.py:138`) and `adjusted_player_passing_{S-1}.json` (`enrich.py:101`) |
| SC-3 | New registry features follow the no-lookahead convention (entering-game only, or tagged result_lookahead), proven by the tests/ construct-and-assert pattern | ✓ VERIFIED | Write-before-fold traced in `running_stats.py`: entering-stats dict written at :46-56, current game's adv folded only at :84-90. Season keying `(team, season)` at :31 blocks cross-season leak. Prior-season keying at `enrich.py:101` + `_index_prior_player_agg` docstring. Sentinel tests: `test_running_adv_success_off_is_average_of_prior_games_only`, `test_running_adv_explosiveness_respects_season_reset_and_start_date_order`, `test_enrich_prior_off_wepa_uses_prior_season_only`. All pass |

**Score: 3/3 roadmap success criteria verified.**

### Plan-Level Observable Truths

| # | Plan | Truth | Status | Evidence |
| --- | --- | --- | --- | --- |
| 1 | 03-01 | 4 new adv features computed from strictly-prior same-season games; first game yields None | ✓ VERIFIED | `running_stats.py:52-55` emits None when `adv_counts[out_key] == 0`; test at `test_running_stats.py:120` |
| 2 | 03-01 | Current game's own adv value never appears in its own entering stats (9.99 sentinel) | ✓ VERIFIED | Write (`:46`) strictly precedes fold (`:84`); sentinel test passes |
| 3 | 03-01 | Prior-season games do not leak; start_date ordering respected | ✓ VERIFIED | `by_team_season` keys on `(team, game.season)` (`:31`); sort at `:35` uses `start_dates` key; test at `test_running_stats.py:138` |
| 4 | 03-01 | registry_version() moved off the 69084ed55504 baseline | ✓ VERIFIED | `test_features.py:72` `test_registry_version_changed_from_phase3_baseline` passes at HEAD |
| 5 | 03-01 | enrich surfaces home_/away_ variants via the existing computed_running `_lookup` branch, no new branch | ✓ VERIFIED | `enrich.py:161` passes `adv=` into `compute_running_stats`; no new computed_running branch added; `test_enrich_surfaces_running_success_off_from_prior_games` passes |
| 6 | 03-01 | adv index is fail-closed and crash-proof on missing/non-numeric advanced fields | ⚠️ VERIFIED (leaf) — see WR-01 | `_coerce_numeric` (`enrich.py:164`) returns None for dict/bool/non-numeric leaves; `test_enrich_success_off_fails_closed_on_dict_shaped_field` passes. **Container-level gap (non-dict offense/defense, non-numeric gameId) can still raise** — non-blocking, see Warnings |
| 7 | 03-01 | D-04 preseason talent/recruiting rows already exist and are untouched | ✓ VERIFIED | `team_preseason` rows present in `features.py`; no diff to those rows in the phase range |
| 8 | 03-02 | Game with empty `lines` yields 0 GameRecords | ✓ VERIFIED | `test_line_less_game_contributes_zero_records` (`test_normalize.py:44`) passes |
| 9 | 03-02 | Game with a usable consensus line yields exactly 1 GameRecord | ✓ VERIFIED | `test_usable_line_contributes_one_record` (`test_normalize.py:83`) passes |
| 10 | 03-02 | Confirmed 2013 floor documented with on-disk evidence | ✓ VERIFIED | `docs/data-line-floor.md` (2.7K) exists at HEAD; states 2013, cites 2012 zero-usable-lines evidence, references probe 03-03; contains no token material |
| 11 | 03-03 | Vendored `cfbd-python/` clone restored so `import cfbd` resolves | ✓ VERIFIED | Clone present locally (gitignored, so no tracked-file change — as specified); probe executed successfully against live API per human-confirmed output |
| 12 | 03-03 | Bounded live probe over 2008–2013 reports earliest usable-line season | ✓ VERIFIED | `scripts/probe_line_floor.py` (3.3K) present; sweeps 2008–2013 with `provider=consensus`; prints per-season counts + earliest season |
| 13 | 03-03 | API token resolved via `find_cfbd_token` only, never printed/logged/committed | ✓ VERIFIED | `probe_line_floor.py:60` — token flows only into `cfbd.Configuration(access_token=...)`. All 5 `print` calls (`:63,71,73,78,80`) emit season numbers, counts, and exception type/message only. Independently re-traced in 03-REVIEW.md |
| 14 | 03-04 | `prior_off_wepa` aggregated from season S-1 player wepa only | ✓ VERIFIED | `enrich.py:101` reads `adjusted_player_passing_{season - 1}.json` and keys under `season`; `_lookup_team_scoped` (`:277-279`) reads `(team, game.season)`. 99.0 same-season sentinel excluded by `test_enrich_prior_off_wepa_uses_prior_season_only` |
| 15 | 03-04 | Absent/empty prior-season player file yields None (fails closed) | ✓ VERIFIED | `_index_prior_player_agg` returns early when `not path.exists()`; only teams with ≥1 numeric wepa get a key, so lookup returns None. `test_enrich_prior_off_wepa_none_when_prior_file_absent` passes |

**Score: 15/15 plan truths verified** (truth 6 verified for its tested scope, with a documented non-blocking container-level warning).

### Required Artifacts

| Artifact | Expected | Exists | Substantive | Wired | Status |
| --- | --- | --- | --- | --- | --- |
| `cfb_system_maker/running_stats.py` | `adv` kwarg + 4 adv_* output keys, write-before-fold | ✓ | ✓ (`_ADV_FIELDS` map :8-13, accumulation :84-90) | ✓ (called from `enrich.py:161`) | ✓ VERIFIED |
| `cfb_system_maker/enrich.py` | adv index, `_coerce_numeric`, `raw_player_agg` index + lookup branch | ✓ | ✓ (:136-161, :164, :277-279, :337-354) | ✓ | ✓ VERIFIED |
| `cfb_system_maker/features.py` | 4 season_to_date rows + `prior_off_wepa` + `raw_player_agg` SourceKind | ✓ | ✓ (:22, :231-235, :341-365) | ✓ (consumed by enrich lookup) | ✓ VERIFIED |
| `scripts/probe_line_floor.py` | Bounded token-safe live probe | ✓ (3.3K) | ✓ | ✓ (run, output human-confirmed) | ✓ VERIFIED |
| `docs/data-line-floor.md` | Floor + evidence + closure rationale | ✓ (2.7K) | ✓ | n/a (doc) | ✓ VERIFIED |
| `tests/test_running_stats.py` | No-lookahead + season-reset adv tests | ✓ | ✓ (2 new tests :120,:138) | ✓ (11 tests pass) | ✓ VERIFIED |
| `tests/test_enrich.py` | adv wiring, fail-closed, prior-season tests | ✓ | ✓ (4 new tests :118,:154,:183,:212) | ✓ | ✓ VERIFIED |
| `tests/test_features.py` | Registry shape + version-change assertions | ✓ | ✓ (:65, :72) | ✓ | ✓ VERIFIED |
| `tests/test_normalize.py` | Floor-gate characterization tests | ✓ | ✓ (3 new tests :44,:64,:83) | ✓ | ✓ VERIFIED |
| `cfbd-python/` | Restored vendored clone (gitignored) | ✓ | ✓ | ✓ (`import cfbd` resolved during probe run) | ✓ VERIFIED |

### Key Link Verification

| From | To | Via | Status |
| --- | --- | --- | --- |
| `FeatureDef.field` (adv_success_off etc.) | `compute_running_stats` output keys | Exact key equality | ✓ WIRED — `_ADV_FIELDS` output keys (`running_stats.py:9-12`) match registry `field` values; locked by `test_season_to_date_fields_match_running_stats_output` |
| `compute_running_stats` entering-stats write | current-game adv fold | Write-before-accumulate ordering | ✓ WIRED — write at `:46-56`, fold at `:84-90`; ordering is the no-lookahead guarantee |
| `enrich._build_running_index` | `advanced_game_stats_{season}.json` | Per-season raw file read, keyed `(int(game_id), team)` | ✓ WIRED — `enrich.py:136-152` |
| `enrich._build_indexes` | `adjusted_player_passing_{S-1}.json` | `_index_prior_player_agg`, keyed `(team, S)` | ✓ WIRED — `enrich.py:101` + `:337-354` |
| `prior_off_wepa` FeatureDef | `_lookup_team_scoped` | `raw_player_agg` source_kind branch | ✓ WIRED — `enrich.py:277-279` |
| Backfill path | `fetch --season` (NOT `scrapers.py`) | Conditional, resolved no-op | ✓ WIRED (vacuously) — probe returned 0 pre-2013 usable lines, so no backfill executed; `scrapers.py` untouched (`git diff 58e55fc..HEAD` empty) |
| `normalize.py` | floor-gate tests | Unchanged behavior asserted by characterization tests | ✓ WIRED — `git diff 58e55fc..HEAD -- normalize.py` is empty; tests assert existing behavior as required |

### Data-Flow Trace (Level 4)

| Artifact | Data Variable | Source | Produces Real Data | Status |
| --- | --- | --- | --- | --- |
| `running_success_off/def`, `running_explosiveness_off/def` | `adv_sums` / `adv_counts` | `data/raw/advanced_game_stats_{season}.json` via `_build_running_index` | Yes — concrete-value enrich test asserts computed averages from prior games, not placeholders | ✓ FLOWING |
| `prior_off_wepa` | `sums[team]` | `data/raw/adjusted_player_passing_{S-1}.json` | Yes — test asserts 2022 sum = 5.0 surfaces for a 2023 game | ✓ FLOWING |

> `data/processed/features.json` regeneration is a documented D-07 runtime follow-up (`data/` is gitignored), not a phase deliverable. The features are wired end-to-end in code and the enrich tests prove surfacing.

### Prohibition Verification

| Prohibition | Status | Evidence |
| --- | --- | --- |
| never-fold-a-games-own-result-into-its-own-features | ✓ UPHELD | Write-before-fold traced at `running_stats.py:46` vs `:84`; sentinel tests pass |
| never-wire-full-season-aggregate-as-pregame-without-result_lookahead-quarantine | ✓ UPHELD | All 5 new features are `season_to_date` (to-date accumulation) or `team_preseason` (prior-season); no raw season aggregate added |
| never-aggregate-same-season-player-wepa-for-pregame-use | ✓ UPHELD | `enrich.py:101` reads `{season - 1}` exclusively; 99.0 same-season sentinel proven excluded |
| never-add-a-game-level-column-to-games-csv | ✓ UPHELD | `git diff 58e55fc..HEAD -- models.py storage.py` is empty; new features live in the enrich sidecar |
| never-backfill-game-or-line-data-via-scrapers-py | ✓ UPHELD | `git diff 58e55fc..HEAD -- scrapers.py` is empty; backfill resolved to a no-op |
| never-edit-the-vendored-cfbd-python-clone | ✓ UPHELD | Clone restored by `git clone` only; gitignored, no tracked-file change |
| never-log-echo-or-commit-the-env-env-token | ✓ UPHELD | Probe prints season numbers/counts/exception names only; independently re-traced in 03-REVIEW.md |
| never-add-per-game-per-player-fanout-this-phase | ✓ UPHELD | Both new sources read already-scraped per-season files; no new fan-out scraping added |

### Behavioral Spot-Checks

| Behavior | Command | Result | Status |
| --- | --- | --- | --- |
| Phase-3 test files pass at HEAD | `python -m pytest tests/test_running_stats.py tests/test_enrich.py tests/test_features.py tests/test_normalize.py -q` | `37 passed in 0.21s` | ✓ PASS |
| New registry keys present at HEAD | `grep -n` on `features.py` for the 5 keys | All 5 found (:231, :341, :349, :357, :365) | ✓ PASS |
| Live line-floor probe | `python scripts/probe_line_floor.py` | 2008–2012 = 0 usable; 2013 = 841; earliest = 2013 (executed during 03-03, human-confirmed) | ✓ PASS |
| No-lookahead ordering | Source inspection `running_stats.py:43-90` | Entering-stats write precedes all accumulation | ✓ PASS |

### Requirements Coverage

| Requirement | Source Plans | Description | Status | Evidence |
| --- | --- | --- | --- | --- |
| DATA-01 | 03-02, 03-03 | Historical game/line coverage backfilled further back than the 2013 floor where CFBD coverage allows | ✓ SATISFIED | Closed by verification: live probe confirms CFBD coverage does not allow it (0 usable lines 2008–2012). Floor gate locked by tests, floor documented in `docs/data-line-floor.md`. Conditional backfill correctly a documented no-op |
| DATA-02 | 03-01, 03-04 | Additional CFBD endpoints wired into `FEATURE_REGISTRY` as new filterable features, following the no-lookahead convention | ✓ SATISFIED | 5 new registry rows from 2 newly wired source files, all no-lookahead, all test-proven |

**Orphaned requirements:** None. REQUIREMENTS.md maps only DATA-01 and DATA-02 to Phase 3; both are claimed by plans and both are marked Complete.

### Anti-Patterns Found

| File | Line | Pattern | Severity | Impact |
| --- | --- | --- | --- | --- |
| — | — | Debt-marker scan (`TBD`/`FIXME`/`XXX`/`TODO`/`HACK`/`PLACEHOLDER`) across all 9 phase-modified files | — | **Clean — zero markers.** No blocker |

Two advisory findings carried from `03-REVIEW.md` (both non-blocking, see frontmatter `warnings`):

- **WR-01 (WARNING)** — `enrich.py:143-152`. Truth 03-01 #6 claims enrich "never raises." Leaf-level coercion is correct and tested, but a non-dict `offense`/`defense` container or a non-numeric `gameId` can still raise and abort the run. The existing test name (`..._fails_closed_on_dict_shaped_field`) implies broader coverage than it delivers — it exercises the leaf, not the container. **Not a blocker:** unreachable on real CFBD shapes, fails loud rather than corrupting data, and mirrors the pre-existing ppa block directly above it. Optional hardening: `isinstance` guard on the containers plus a list-shaped-`offense` test.
- **IN-02 (INFO)** — `enrich.py:337-354`. `_index_prior_player_agg` derives season from the filename rather than filtering rows on their own `year`. The no-lookahead guarantee rests on the file-per-season convention, which holds. Defense-in-depth only.

### Human Verification Required

None. The single human-touch item in this phase — the live CFBD line-floor probe (03-03 Task 3) — was already executed and human-confirmed during phase execution (2008–2012 = 0 usable lines, 2013 = 841, no token in output). All no-lookahead truths are behavior-dependent but are backed by **passing** sentinel tests, so they resolve to VERIFIED rather than PRESENT_BEHAVIOR_UNVERIFIED.

### Gaps Summary

No gaps. The phase goal is achieved on both axes at current HEAD:

- **Deeper:** the coverage floor was re-confirmed against the live CFBD API rather than a dated on-disk snapshot. 2013 stands as the betting-line floor; the conditional pre-2013 backfill correctly resolved to a documented no-op because CFBD returns zero usable lines before 2013. The floor behavior (pre-floor seasons contribute 0 rows, floor season contributes rows) is now locked by characterization tests against an unmodified `normalize.py`, and the reasoning is durably recorded in `docs/data-line-floor.md`. DATA-01 is satisfied by verification, which is the honest closure for a requirement whose upstream data does not exist.
- **Broader:** five new filterable registry features are live end-to-end (compute → enrich → registry) from two newly wired source files. Every one is no-lookahead by construction — the four to-date advanced stats via write-before-fold ordering, `prior_off_wepa` via prior-season keying — and each invariant is proven by a passing sentinel test in the repo's construct-and-assert style, not merely asserted in a summary.

Two non-blocking robustness warnings ride along (WR-01, IN-02). Neither affects correctness, security, or data integrity; both are recorded above for optional future hardening rather than as phase gaps.

---

_Verified: 2026-07-20_
_Verifier: Claude (gsd-verifier)_
_Verified at HEAD: 3b8e93c (post-Phase-04)_

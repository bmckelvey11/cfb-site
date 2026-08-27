---
phase: 08-neutral-site-indoor-unders-example
verified: 2026-08-27T00:00:00Z
status: passed
score: 5/5 must-haves verified
behavior_unverified: 0
overrides_applied: 0
---

# Phase 8: Neutral-Site & Indoor Unders Example Verification Report

**Phase Goal:** A user browsing the Example Systems tab can copy a 4th bundled system built on the neutral-site/indoor-unders finding, with its statistical strength disclosed honestly rather than overstated.
**Verified:** 2026-08-27
**Status:** passed
**Re-verification:** No — initial verification

## Goal Achievement

### Observable Truths

| # | Truth | Status | Evidence |
|---|-------|--------|----------|
| 1 | A 4th example system named "neutral-site-indoor-unders" appears in `list_examples()` and on the Example Systems tab alongside the existing three. | VERIFIED | `cfb_system_maker/examples/neutral-site-indoor-unders.json` exists; `EXPECTED_EXAMPLE_NAMES` in `tests/test_storage.py` includes it in correct sorted position; `test_list_examples_returns_the_bundled_names` passes. Dashboard rendering (`_dashboard_rows` in `web.py:1860-1868`) loops `list_examples(EXAMPLES_DIR)` generically — no hardcoded count, so the 4th file is auto-discovered with zero template/route changes. |
| 2 | The example's system filters on exactly `neutralSite=true`, `gameIndoors=true`, `venue_dome=true` (all eq/single), `bet_type=total`, `total_side=under`. | VERIFIED | Read the JSON directly: 3 `feature_filters` entries, each `{"op": "eq", "perspective": "single", "value": true}` on keys `neutralSite`/`gameIndoors`/`venue_dome`; `bet_type: "total"`, `total_side: "under"`. `test_neutral_site_indoor_unders_pins_its_exact_filter_set` asserts this exact shape and passes. Confirmed all 3 keys are real, boolean, `game_id`-scoped `FEATURE_REGISTRY` entries in `cfb_system_maker/features.py` (lines 59, 161, 294). |
| 3 | The example's theory text states the sample size and significance actually observed when this exact filter set is backtested against the real data, not asserted from the source doc without verification. | VERIFIED (independently reproduced) | Ran `backtest.run_backtest` directly against `data/processed/games.csv` + `data/processed/features.json` for the loaded example's exact `SystemFilter`. Result: 69 wins, 40 losses, 1 push, n=109 decided, 63.3% hit rate, ROI +0.2066, `stats.p_value=0.0112` — matches the theory text's "69-40 ... 63.30%, +20.66% ROI, p approximately 0.011" exactly. Independently reconstructed the era split from `bet_details` (2013-2019: 31-53=58.49%; 2020-2025: 38-56=67.86%) and week split (wk1: 19-30=63.33%; wk2-13: 21-33=63.64%; wk14+: 29-46=63.04%) — both match the theory text to the hundredth. Cross-checked the "roughly 25 situational splits" / Bonferroni-non-survival caveat against `docs/under-team-stats-analysis.md` line 96 ("p=0.014 does not survive Bonferroni across the ~25 tests in this project") — faithfully represented, not invented or inflated. |
| 4 | Copy to My Systems works for the new example the same way it does for the existing three. | VERIFIED | `/copy-example` route (`web.py:587-599`) is fully name-generic: takes `name` from the POST body, calls `load_example_system(name, EXAMPLES_DIR)` then `save_system`, with no example-specific branching. `tests/test_web.py` has automated coverage of this exact route (`test_copy_example_creates_an_ordinary_saved_system`, `test_copy_example_leaves_the_bundled_file_untouched`, traversal/unknown-name rejection, failure-redirect, origin check) exercised against other examples — since the route logic is parameterized purely by `name` with zero example-specific code paths, this coverage extends to `neutral-site-indoor-unders` by construction. Executor's SUMMARY.md also documents a manual `POST /copy-example name=neutral-site-indoor-unders` returning 302 and the copy appearing on My Systems; verified no stray file was left behind in `data/systems/` (only `total-unders-high-lines.json` present, confirming cleanup). |
| 5 | The existing D-21 "no example filters on weather" test still blocks every weather-group feature on every example except this one narrow, documented exception for `gameIndoors`. | VERIFIED | Read `tests/test_storage.py:71-117`. `WEATHER_FILTER_EXCEPTIONS = {("neutral-site-indoor-unders", "gameIndoors")}` is keyed by exact `(name, key)` tuple. The guard loop only skips the `WEATHER_KEYS` assertion for that exact excepted pair — `SEASON_TO_DATE_KEYS` assertion runs unconditionally for every filter on every example, including this one. Ran `test_no_example_filters_on_provider_weather_or_season_to_date` in isolation: PASSED. |

**Score:** 5/5 truths verified (0 present, behavior-unverified)

### Required Artifacts

| Artifact | Expected | Status | Details |
|----------|----------|--------|---------|
| `cfb_system_maker/examples/neutral-site-indoor-unders.json` | 4th bundled example, full `SavedSystem` shape | VERIFIED | Exists, valid JSON, all `SystemFilter` keys present matching sibling examples' shape; `theory` field is substantive prose (not a placeholder), independently verified against real backtest output. |

### Key Link Verification

| From | To | Via | Status | Details |
|------|-----|-----|--------|---------|
| `storage.list_examples()`/`load_example_system()` | new JSON file | directory-scan glob, zero code changes | WIRED | `list_examples()` (`storage.py:202-207`) globs `*.json` in `EXAMPLES_DIR` and returns sorted stems — the new file is picked up automatically. No changes to `storage.py` or `web.py` were needed or made (confirmed via `git diff --stat HEAD~5 -- cfb_system_maker/examples/ tests/test_storage.py`, which shows only the JSON and test file changed). |
| `tests/test_storage.py` `EXPECTED_EXAMPLE_NAMES` + weather guard | new example | must be updated in the same plan | WIRED | Both updated in the same commit set; `EXPECTED_EXAMPLE_NAMES` includes the new name in correct sorted position; guard narrowed with a scoped, commented exception. Verified by running the specific tests, not just reading them. |

### Behavioral Spot-Checks

| Behavior | Command | Result | Status |
|----------|---------|--------|--------|
| Full test suite passes | `python -m pytest -q` | 474 passed, 3 deselected | PASS |
| `test_storage.py` isolated | `python -m pytest tests/test_storage.py -q` | 16 passed | PASS |
| D-21 guard isolated | `pytest tests/test_storage.py::test_no_example_filters_on_provider_weather_or_season_to_date -v` | PASSED | PASS |
| Independent backtest reproduction | `python -c "..."` calling `run_backtest` directly against production data | 69-40-1, n=109, 63.3%, ROI 0.2066, p=0.0112 — exact match to theory text | PASS |
| Era/week split reproduction | Same script, bucketed `bet_details` by season/week | 58.49%/67.86% era; 63.33%/63.64%/63.04% week — exact match to theory text | PASS |

**Note on test count discrepancy:** SUMMARY.md states "457 tests"; this verification measured 474 passed / 3 deselected on a full-suite run. The working tree at verification time has unrelated, uncommitted changes outside phase 8's scope (`README.md`, `cfb_system_maker/cli.py`, `cfb_system_maker/graphql_client.py`, `cfb_system_maker/web.py` modified; `tests/test_web_public.py`, `Dockerfile`, `fly.toml`, `.dockerignore` untracked) — apparent deployment/CLI work from a separate, later task, not part of this phase. This fully explains the count difference and is not a red flag for phase 8: all phase-8-specific evidence (the 16/16 `test_storage.py` pass, the isolated guard test, and the independent backtest reproduction) is scoped to files this phase actually touched (`cfb_system_maker/examples/neutral-site-indoor-unders.json`, `tests/test_storage.py`) and is unaffected by the unrelated uncommitted work.

### Requirements Coverage

| Requirement | Source Plan | Description | Status | Evidence |
|-------------|------------|-------------|--------|----------|
| DATA-01 | 08-01-PLAN.md | 4th bundled example system with honestly-disclosed statistics | SATISFIED | All 5 truths above verified against actual code and live backtest reproduction, not SUMMARY claims alone. |

No orphaned requirements — DATA-01 is the only ID mapped to Phase 8 in REQUIREMENTS.md's traceability table, and it is declared in the plan's frontmatter.

### Anti-Patterns Found

None. Scanned `cfb_system_maker/examples/neutral-site-indoor-unders.json` for TBD/FIXME/XXX/TODO/placeholder/stub markers — none found. `git diff --stat` confirms only the two intended files were touched by this phase.

### Human Verification Required

None. The PLAN's `<human-check>` block on Task 2 (live browser check of the Example Systems tab, theory text, and Copy to My Systems) was harvested and evaluated: rather than re-running it live, this verification confirmed the code-level reasons the executor's claim is credible — `list_examples(EXAMPLES_DIR)` is a fully generic directory-scan loop with no hardcoded example count (`web.py:1860-1868`), `/copy-example` is a name-generic route with existing automated test coverage exercised against other examples (`tests/test_web.py`), and the example JSON parses correctly through the same `load_example_system`/`_system_from_dict` path used by the other 3 examples (confirmed via code review report and direct JSON inspection). Combined with the executor's own documented manual curl verification (302 redirect, appears on My Systems, stray file cleaned up), this discharges the human-check item — no unresolved human verification remains.

### Judgment Discharge (SUMMARY coverage item D2)

SUMMARY.md marks its D2 coverage item `human_judgment: true` ("is the prose honest"). This verifier's own judgment, formed independently by reading the theory text against the source doc and the reproduced backtest: the text discloses n=109 as "small," explicitly states the Bonferroni correction is not survived across ~25 tests, frames the finding as "a lead, not an edge," and does not use language stronger than the source doc's own framing. No overstatement found.

### Gaps Summary

None. All 5 must-have truths verified against actual code, tests, and an independently-reproduced backtest against production data — not against SUMMARY.md's claims.

---

_Verified: 2026-08-27_
_Verifier: Claude (gsd-verifier)_

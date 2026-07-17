---
phase: 02-integrity-fade-grade
verified: 2026-07-17T00:00:00Z
status: passed
score: 3/3 must-haves verified
behavior_unverified: 0
overrides_applied: 0
---

# Phase 2: Integrity — Fade & Grade Verification Report

**Phase Goal:** Users can invert a system to test the fade and see an at-a-glance composite grade of how trustworthy a system's edge is, both surfaced directly in the stat-chip header built in Phase 1.
**Verified:** 2026-07-17
**Status:** passed
**Re-verification:** No — initial verification

## Goal Achievement

### Observable Truths

| # | Truth | Status | Evidence |
|---|-------|--------|----------|
| 1 | User can toggle "Fade System" on a saved system; toggling flips the graded side and updates Record/Money Won/ROI chips to the opposite side's results. | ✓ VERIFIED | `cfb_system_maker/backtest.py:314-316` (`grade_bet`) and `:383-385` (`_grade_total_bet`) flip the graded side exclusively inside grading, proven mathematically equivalent to negating `cover_margin` (push-preserving). `templates/index.html:228-232` renders Record/Margin/Money Won/ROI/Grade directly from `result.*` fields, and `result = run_backtest(games, system, ...)` (`web.py:80`) threads `system.fade` straight through. Checkbox at `templates/index.html:225` (`name="fade" form="filters-form"`) parses via exact `== "on"` string comparison at all 6 enumeration sites in `web.py` (`_form_values:338`, `_form_values_from_post:364`, `_form_from_system:400`, `_system_from_form:487`, `_query_args_from_form:228`, `_empty_form:309`). Unit tests `test_fade_flips_spread_win_to_loss`, `test_fade_preserves_spread_push`, `test_fade_flips_total_bet_result`, `test_fade_does_not_change_matched_bet_count` (tests/test_backtest.py) and CLI test `test_backtest_command_fade_flag_flips_grading` all pass. `matches_system` (backtest.py:206-266) has zero references to `.fade`, confirmed by direct read. |
| 2 | User sees a System Grade letter rendered in the stat-chip header's Grade slot, computed from sample size vs significance, ROI z-score, season sign-consistency, permutation p-value, and filter/value-count overfitting penalties. | ✓ VERIFIED | `compute_grade` (`backtest.py:186-203`) combines `_sample_size_score` (Wilson low vs break-even), `_roi_significance_score` (z-score), `_consistency_score` (season sign-consistency), `_permutation_score` (permutation p-value), and `_overfit_score(count_overfit_filters(system))` via equal-weighted average bucketed through `_GRADE_BANDS` into A/B/C/D/F, or `None` for zero matched bets. Wired into `BacktestResult.grade` via `dataclasses.replace` in `run_backtest` (backtest.py:52). Grade chip renders at `templates/index.html:233` (`{% if result.grade %}{{ result.grade }}{% else %}&mdash;{% endif %}` — no `\|safe`, grep confirms zero occurrences in the file). `count_overfit_filters` (backtest.py:166-183) never references `system.fade`, confirmed by direct read and `test_count_overfit_filters_follows_d06_counting_rule`. 11 sub-score/composite tests in tests/test_backtest.py and 3 web-level render tests in tests/test_web.py all pass. |
| 3 | The Fade toggle state persists across save and reload of the system. | ✓ VERIFIED | `storage._system_to_dict` writes `"fade": system.fade` (storage.py:146); `_system_from_dict` reads `fade=bool(system.get("fade", False))` (storage.py:188) — backward-compatible with pre-phase JSON missing the key. Round-trip tests `test_save_load_system_round_trips_fade` and `test_load_saved_system_backward_compatible_with_missing_fade_key` pass. Web-level persistence tests `test_web_save_and_load_system_preserves_fade`, `test_web_tab_switch_preserves_load_system_and_round_trips_fade`, `test_web_loaded_system_remove_link_preserves_fade` pass, exercising the full save → reload → tab-switch → remove-filter-link path through a live Flask test client. |

**Score:** 3/3 truths verified (0 present, behavior-unverified)

### Required Artifacts

| Artifact | Expected | Status | Details |
|----------|----------|--------|---------|
| `cfb_system_maker/models.py` | `SystemFilter.fade: bool = False`, `BacktestResult.grade: str \| None = None` | ✓ VERIFIED | Line 43 (`fade: bool = False`), line 110 (`grade: str \| None = None`) — exactly one match each. |
| `cfb_system_maker/backtest.py` | fade flip in `grade_bet`/`_grade_total_bet`; `compute_grade` + 5 sub-score helpers + `count_overfit_filters` | ✓ VERIFIED | All present and substantive (not stubs); read in full, logic matches plan spec exactly (thresholds, negation math, zero-bet `None` short-circuit). |
| `cfb_system_maker/cli.py` | `--fade` flag on backtest subcommand | ✓ VERIFIED | Line 309: `backtest.add_argument("--fade", action="store_true")`. |
| `cfb_system_maker/storage.py` | fade round-trip in `_system_to_dict`/`_system_from_dict`; `_safe_system_name` path-traversal guard (CR-01) | ✓ VERIFIED | Fade round-trip present and backward-compatible. `_safe_system_name` (storage.py:16-19, regex `^[A-Za-z0-9_-]+$`) called at the top of `save_system`, `load_system`, `load_saved_system` (lines 89, 103, 110) before any path construction — CR-01 fix confirmed in place, not merely claimed. |
| `cfb_system_maker/web.py` | fade threaded through all 6 form/query enumeration sites; `ValueError` from `_safe_system_name` caught gracefully | ✓ VERIFIED | All 6 sites confirmed (lines 228, 309, 338, 364, 400, 487). `/save` catches `ValueError` (web.py:118) and redirects instead of 500ing; `/` catches `(FileNotFoundError, ValueError)` (web.py:71); `/compare` catches `(FileNotFoundError, ValueError)` (web.py:145). |
| `cfb_system_maker/templates/index.html` | Fade checkbox, Grade chip conditional render, `id="filters-form"` | ✓ VERIFIED | Line 20 (`id="filters-form"`), line 225 (Fade checkbox), line 233 (Grade chip, no `\|safe`). |

### Key Link Verification

| From | To | Via | Status | Details |
|------|-----|-----|--------|---------|
| `templates/index.html` Fade checkbox | `web.py` `_form_values`/`_form_values_from_post` | `request.args.get("fade") == "on"` / `request.form.get("fade") == "on"` | ✓ WIRED | Exact string-comparison pattern used (no truthy-`bool()` footgun), matching the existing favorite/underdog pattern. |
| `web.py` `_system_from_form`/`load_saved_system` | `backtest.grade_bet`/`_grade_total_bet` | `system.fade` field read | ✓ WIRED | `run_backtest` passes `system` straight through to `grade_bet`; fade is read only at the grading boundary, never in `matches_system`. |
| `backtest.run_backtest` | `templates/index.html` stat chips | `result.wins/losses/pushes/profit/roi/grade` rendered directly | ✓ WIRED | Confirmed by direct template read (lines 228-232) — no intermediate transform or stale-data path. |
| `storage.save_system`/`load_saved_system` | `_safe_system_name` | validation call before path construction | ✓ WIRED | CR-01 fix confirmed wired at all three call sites; `web.py` catches the resulting `ValueError` at every route that calls into storage. |

### Requirements Coverage

| Requirement | Source Plan | Description | Status | Evidence |
|-------------|-------------|--------------|--------|----------|
| INTG-01 | 02-01-PLAN.md | User can toggle "Fade System" on a system to grade the opposite side of every matched bet | ✓ SATISFIED | Truth 1 above; full vertical slice (models → backtest → cli → storage → web → template) verified. |
| INTG-02 | 02-02-PLAN.md | User sees a composite System Grade letter combining sample size vs significance, ROI z-score, season sign-consistency, permutation p-value, and filter/value-count overfitting penalties | ✓ SATISFIED | Truth 2 above; `compute_grade` combines exactly the 5 documented sub-scores. |

No orphaned requirements — REQUIREMENTS.md maps only INTG-01/INTG-02 to Phase 2, and both appear in plan frontmatter `requirements:` fields.

### Anti-Patterns Found

None. Grep for `TBD|FIXME|XXX|TODO|HACK|PLACEHOLDER` across all phase-modified source files (`models.py`, `backtest.py`, `cli.py`, `storage.py`, `web.py`, `templates/index.html`) returned zero debt markers. The only `placeholder` matches in `index.html` are legitimate HTML `placeholder=""` input attributes pre-dating this phase's scope on unrelated fields.

### Behavioral Spot-Checks

| Behavior | Command | Result | Status |
|----------|---------|--------|--------|
| Full test suite | `.venv/Scripts/python.exe -m pytest -q` | `166 passed in 18.40s` | ✓ PASS |
| Fade-specific tests | `pytest tests/test_backtest.py tests/test_cli.py tests/test_storage_systems.py tests/test_web.py -k fade` | 4 backtest + 1 CLI + 2 storage + 3 web tests, all pass | ✓ PASS |
| CR-01 regression tests | `pytest tests/test_storage_systems.py tests/test_web.py -k path_traversal` | `6 passed` | ✓ PASS |
| Push-negation math | Manual trace of `grade_bet`/`_grade_total_bet` fade branches | `cover_margin_fade == -cover_margin` algebraically (confirmed by inspection: swapping team/opponent/spread under fade is an exact sign flip), so `margin == 0` (push) is invariant under fade | ✓ PASS (proof by inspection + `test_fade_preserves_spread_push`) |

### Human Verification Required

None. All three success criteria are backed by both unit-level and Flask-test-client-level (rendered HTML) evidence — not just presence/wiring checks. The visual placement note carried in both SUMMARY.md files ("End-of-phase human-verify should include a visual/click check of the Fade checkbox placement and Grade chip rendering in a real browser") is a nice-to-have polish check, not something the success criteria require verifying beyond what the Flask test client's rendered-HTML assertions already cover (checkbox presence, `checked` state, form association, Grade letter/em-dash text). No `checkpoint:human-verify` blocks were found deferred from the PLAN files.

### Non-Blocking Findings Carried From Code Review (02-REVIEW.md)

- **CR-01 (critical, path traversal)** — confirmed FIXED in commit `433b040`; `_safe_system_name` guard verified in place at all three storage call sites, with `web.py` catching the resulting `ValueError` gracefully at `/save`, `/`, and `/compare`. Regression tests present and passing.
- **WR-01 (equal-weighted grade average lets sub-30-decided-bet systems reach "B")** — explicit, documented D-05 discretionary design choice in 02-02-PLAN.md (equal-weighted average, not worst-of). Not a bug; not blocking. Worth a follow-up design discussion per the review's own recommendation, but out of scope for this phase's success criteria.
- **WR-02 (malformed numeric query params 500)** — pre-existing code untouched by this phase's diff (`_parse_filter_value`, `_int_set`, `_optional_float` predate Phase 2). Correctly spun off as separate background work; not blocking.

### Gaps Summary

None. All 3 roadmap success criteria are verified with both unit-test and integration-test (rendered HTML via Flask test client) evidence. The one critical security finding from code review (CR-01) is confirmed fixed and regression-tested. The two remaining warnings are non-blocking per the task's explicit instruction (WR-01 is a documented discretionary design choice; WR-02 predates this phase's diff).

---

_Verified: 2026-07-17_
_Verifier: Claude (gsd-verifier)_

---
phase: 05-dashboard-current-matches
verified: 2026-07-20T00:00:00Z
status: human_needed
score: 3/3 must-haves verified
behavior_unverified: 0
overrides_applied: 0
human_verification:
  - test: "Load / in a live in-season week after running `python -m cfb_system_maker upcoming --data-dir data`; confirm the Current Matches panel shows the current week's populated rows with no amber fallback notice."
    expected: "Populated state (timestamp + caveat + real rows), not the offseason backward-fallback state."
    why_human: "Depends on books having posted lines for a week in progress; not reproducible before the season opens. Offseason fallback path is proven live and unit-tested with fakes, but the populated in-season path cannot be exercised now."
  - test: "In a live week >= 2, confirm a known upcoming game has non-null entering-game games-played for both teams in data/processed/upcoming_features.json."
    expected: "Non-null season-to-date entering-game feature values for a real mid-season upcoming game."
    why_human: "The 2026 season has no completed games until late August, so no fixture-free run can exercise the populated in-season feature path. Automated coverage uses an injected fake."
  - test: "Save a system with a very long name and one with six or more filters, load /, and confirm the System and Details cells wrap and the page does not scroll sideways."
    expected: "Long names and multi-sentence describe() details wrap (overflow-wrap: anywhere); page never grows horizontally."
    why_human: "Visual CSS wrapping/overflow behavior; the UI-SPEC marks this a backstop check and no automated test exercises it."
---

# Phase 5: Dashboard & Current Matches Verification Report

**Phase Goal:** The tool becomes something checked weekly — a My Systems dashboard is the new landing page, and each saved system is evaluated live against upcoming games with matched-filter details.
**Verified:** 2026-07-20
**Status:** human_needed (goal achieved in code; 3 visual/live-data confirmations outstanding)
**Re-verification:** No — initial verification

## Goal Achievement

All three ROADMAP success criteria are delivered in code and behaviorally verified. Status is `human_needed` (not `passed`) solely because the phase's own contracts (`05-UI-SPEC.md` backstop, `05-VALIDATION.md` Manual-Only Verifications) name three checks that grep and the test suite cannot exercise — one visual layout backstop and two live-in-season data confirmations. None of these falsifies goal achievement; they are confirmation items, not gaps.

### Observable Truths

| # | Truth (ROADMAP Success Criterion) | Status | Evidence |
|---|-----------------------------------|--------|----------|
| 1 | User lands on a My Systems dashboard (`/`) listing saved systems with Record/Money Won/ROI and a sparkline, with the editor moved to `/system`. | ✓ VERIFIED | `web.py:398` `@app.get("/")` → `dashboard()`; `web.py:455` `@app.get("/system")` → `index()` (editor). Dashboard rows built by `_dashboard_row` from a cached `run_backtest` (D-11); sparkline SVG rendered in `dashboard.html:84`. Filtered `/` requests 302-redirect to `/system` with query string verbatim (`web.py:400-402`). |
| 2 | A new/empty install ships with 2-3 bundled example systems visible on the dashboard. | ✓ VERIFIED | Three real `SavedSystem` JSON files in `cfb_system_maker/examples/` (spread-home-favorites, total-unders-high-lines, nonconference-away-dogs); each a full serializer-shaped system (verified nonconference-away-dogs.json). Example Systems tab (`dashboard.html:31`), `_example_rows` reuses `_dashboard_row`/`_cached_backtest` (no second grading path), `POST /copy-example` (`web.py:440`) copies read-only into the data dir. |
| 3 | User sees a Current Matches view listing upcoming (unplayed) games each saved system matches, with matched-filter details per game. | ✓ VERIFIED | `_current_matches_panel` (`web.py:1609`) reads only pre-built `upcoming.csv`/`upcoming_meta.json`/`upcoming_features.json`; matches via `matches_system(record, saved.system, feature_map, require_played=False)` (`web.py:1634`); `grade_bet` is never called in the panel path (it appears only at `web.py:261` in the editor). `describe()` reused undecorated for details (`web.py:1644`). All five panel states rendered (`dashboard.html:93-135`). Fade play-text invariant proven by a discriminating passing test. |

**Score:** 3/3 truths verified (0 present, behavior-unverified). Human items below are visual/live-data confirmations, not unverified truths.

### Required Artifacts

| Artifact | Expected | Status | Details |
|----------|----------|--------|---------|
| `cfb_system_maker/web.py` | dashboard route, `/system` editor, `_current_matches_panel`, `_play_text`, `_example_rows`, `copy_example` | ✓ VERIFIED | All present and wired; grade_bet isolated to editor path |
| `cfb_system_maker/templates/dashboard.html` | two-column shell, systems table, sparkline, both tab strips, Current Matches panel, five states | ✓ VERIFIED | Panel filled (05-03's reserved column no longer a stub); Example Systems tab branches on `tab` |
| `cfb_system_maker/examples/*.json` (×3) | one spread, one total, one registry-feature example, each with theory | ✓ VERIFIED | Three files, real system shapes, D-16/D-21 satisfied (conferenceGame matchup feature, not a season-to-date stat) |
| `cfb_system_maker/upcoming.py` | `upcoming` CLI, week resolution + backward offseason fallback, enrich_upcoming | ✓ VERIFIED | `resolve_target_week`/`build_upcoming`/`enrich_upcoming` present; separate `upcoming.csv`, `games.csv` never written |
| `cfb_system_maker/backtest.py` | `matches_system(..., require_played=False)` keyword-only flag | ✓ VERIFIED | `backtest.py:246,251` — only the score guard is conditional; spread/total-None guards stay unconditional |
| `cfb_system_maker/running_stats.py` | unmodified (no-lookahead invariant) | ✓ VERIFIED | Last commit `abd49c3` (03-01); no Phase-5 change — entering-game guarantee preserved |

### Key Link Verification

| From | To | Via | Status |
|------|----|----|--------|
| `dashboard()` | `_current_matches_panel` | `panel = _current_matches_panel(...)` (`web.py:429`), passed to template | ✓ WIRED |
| `_current_matches_panel` | `backtest.matches_system` | `require_played=False` (`web.py:1634`) — single authoritative matcher, no fork | ✓ WIRED |
| `_current_matches_panel` | upcoming data files | `load_upcoming_games`/`load_upcoming_meta`/`_try_load_upcoming_features` | ✓ WIRED |
| `_play_text` | `backtest._side_spread` | away-side negation + fade inversion mirror grade_bet normalization (D-08) | ✓ WIRED |
| dashboard rows | `run_backtest` (cached) | `_dashboard_row`/`_cached_backtest`; no figures persisted to JSON (D-11) | ✓ WIRED |
| `/copy-example` | `storage.save_system` | writes file stem, name-gated on read and write (T-05-18) | ✓ WIRED |

### Behavioral Spot-Checks

| Behavior | Command | Result | Status |
|----------|---------|--------|--------|
| Full suite green | `.venv/Scripts/python -m pytest` | 307 passed in 8.81s (baseline 214 → 307) | ✓ PASS |
| D-08 fade invariant (displayed play == graded play) | `pytest tests/test_web.py -k "fade or play_text or current_matches"` | 19 passed, incl. `test_current_matches_fade_home_side_names_the_away_team` (discriminating) | ✓ PASS |
| All five panel states + escaping | (same run) | offseason/fallback, no-match, missing-file, no-systems, TBD-kickoff, XSS-escape all pass | ✓ PASS |

### Requirements Coverage

| Requirement | Description | Status | Evidence |
|-------------|-------------|--------|----------|
| DASH-01 | My Systems dashboard, record/money/ROI/sparkline, separate from editor | ✓ SATISFIED | SC1 verified |
| DASH-02 | 2-3 bundled example systems | ✓ SATISFIED | SC2 verified |
| DASH-03 | Current Matches: upcoming games each system matches, matched-filter details | ✓ SATISFIED | SC3 verified |
| DASH-04 | Teaser / alternate-line records | ⏸ DEFERRED (correct) | Descoped 2026-07-20; absence is intended, not a gap |

### Anti-Patterns Found

None. No `TBD`/`FIXME`/`XXX` markers in phase-modified files. The two items 05-03 flagged as "reserved"/"placeholder" (empty right column, non-branching example tab) were filled by 05-06 and 05-05 respectively — confirmed in the current template. Every summary reports "Known Stubs: None" and the code agrees.

### Human Verification Required

The three success criteria are met and behaviorally tested via the offseason backward-fallback path (the real path today). The following are confirmation items named by the phase's own contracts; none blocks goal achievement:

1. **Live in-season populated Current Matches** — confirm real posted lines render populated rows (not the amber fallback) once books post a current week. Covered now by injected-fake tests. (`05-VALIDATION.md` Manual-Only.)
2. **Non-null entering-game season-to-date values for a real mid-season upcoming game** — reproducible only after ~week 2 of a live season. (`05-VALIDATION.md` Manual-Only.)
3. **Long-name / many-filter layout backstop** — visual wrapping of the System and Details cells; no automated test exercises CSS overflow. (`05-UI-SPEC.md` 🧪 backstop.)

### Gaps Summary

No gaps. All three ROADMAP success criteria are delivered in code, wired to real data paths, and exercised by a passing 307-test suite including a discriminating test for the D-08 fade play-text invariant. The route move to `/system` preserved the editor, save/load, compare, and filter-modal paths (their tests pass). The no-lookahead invariant holds — `running_stats.py` is unmodified. DASH-04's absence is the intended descope, not a gap. Status is `human_needed` only because three contract-named visual/live-data checks cannot be exercised programmatically — the phase goal itself is achieved.

---

_Verified: 2026-07-20_
_Verifier: Claude (gsd-verifier)_

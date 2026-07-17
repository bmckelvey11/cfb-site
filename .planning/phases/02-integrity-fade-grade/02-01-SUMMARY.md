---
phase: 02-integrity-fade-grade
plan: 01
subsystem: backtest-engine
tags: [python, flask, dataclasses, jinja2, cli]

# Dependency graph
requires:
  - phase: 01-editor
    provides: filters-form sidebar, favorite/underdog/home/away boolean-field pattern in models.py/storage.py/web.py/index.html to mirror
provides:
  - "SystemFilter.fade: bool = False field"
  - fade-aware grade_bet and _grade_total_bet (grading-only flip, matches_system untouched)
  - --fade CLI flag on the backtest subcommand
  - fade round-trip through storage.py save/load (backward compatible with pre-phase JSON)
  - fade threaded through all six web.py form/query enumeration sites
  - Fade System checkbox in templates/index.html, submits via filters-form
affects: [02-02 (Grade computation plan, shares SystemFilter and web.py)]

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "Fade is read exclusively at the grading boundary (grade_bet/_grade_total_bet), never inside matches_system -- keeps matched-game population identical regardless of fade state (D-03)."
    - "New SystemFilter boolean fields must be added to all six web.py form/query enumeration sites (_form_values, _form_values_from_post, _form_from_system, _system_from_form, _query_args_from_form, _empty_form) in the same change, or query-string round-trips silently drop the field."

key-files:
  created: []
  modified:
    - cfb_system_maker/models.py
    - cfb_system_maker/backtest.py
    - cfb_system_maker/cli.py
    - cfb_system_maker/storage.py
    - cfb_system_maker/web.py
    - cfb_system_maker/templates/index.html
    - tests/test_backtest.py
    - tests/test_cli.py
    - tests/test_storage_systems.py
    - tests/test_web.py

key-decisions:
  - "Fade toggle checkbox lives outside filters-form's DOM (inside .workspace-header per D-01/UI-SPEC) and associates via the HTML5 form=\"filters-form\" attribute -- same mechanism the plan specified, verified structurally (attribute present, id present) rather than via a live-browser click, consistent with existing favorite/theory test-client coverage."
  - "Did not add a 'fade' entry to _REMOVE_PARAM_MAP -- fade is a toggle with no describe() sentence, so it has no remove-filter link, per plan instruction."

patterns-established:
  - "Boolean flip fields belong exclusively in grading functions, never in matching functions, to preserve the matched-count invariant when adding future toggle-style filters."

requirements-completed: [INTG-01]

coverage:
  - id: D1
    description: "grade_bet flips the graded side under fade for spread bets, preserving pushes"
    requirement: "INTG-01"
    verification:
      - kind: unit
        ref: "tests/test_backtest.py#test_fade_flips_spread_win_to_loss"
        status: pass
      - kind: unit
        ref: "tests/test_backtest.py#test_fade_preserves_spread_push"
        status: pass
    human_judgment: false
  - id: D2
    description: "_grade_total_bet flips the graded side under fade for total bets without altering the winner computation"
    requirement: "INTG-01"
    verification:
      - kind: unit
        ref: "tests/test_backtest.py#test_fade_flips_total_bet_result"
        status: pass
    human_judgment: false
  - id: D3
    description: "fade never changes the matched-game population (matches_system has zero knowledge of fade)"
    requirement: "INTG-01"
    verification:
      - kind: unit
        ref: "tests/test_backtest.py#test_fade_does_not_change_matched_bet_count"
        status: pass
    human_judgment: false
  - id: D4
    description: "--fade CLI flag works and produces different graded output than the non-faded run on the same matched games"
    requirement: "INTG-01"
    verification:
      - kind: unit
        ref: "tests/test_cli.py#test_backtest_command_fade_flag_flips_grading"
        status: pass
    human_judgment: false
  - id: D5
    description: "fade persists through storage save/load, including backward compatibility with pre-phase saved JSON missing the fade key"
    requirement: "INTG-01"
    verification:
      - kind: unit
        ref: "tests/test_storage_systems.py#test_save_load_system_round_trips_fade"
        status: pass
      - kind: unit
        ref: "tests/test_storage_systems.py#test_load_saved_system_backward_compatible_with_missing_fade_key"
        status: pass
    human_judgment: false
  - id: D6
    description: "Fade toggle round-trips through GET filters form, POST /save, tab-switch links, and remove-filter links"
    requirement: "INTG-01"
    verification:
      - kind: integration
        ref: "tests/test_web.py#test_web_save_and_load_system_preserves_fade"
        status: pass
      - kind: integration
        ref: "tests/test_web.py#test_web_tab_switch_preserves_load_system_and_round_trips_fade"
        status: pass
      - kind: integration
        ref: "tests/test_web.py#test_web_loaded_system_remove_link_preserves_fade"
        status: pass
    human_judgment: false
  - id: D7
    description: "Fade System checkbox renders in the browser at the correct visual placement and is clickable/submittable end-to-end"
    human_judgment: true
    rationale: "Structural HTML assertions (form= attribute presence, checked-state string matching) prove the server-side contract, but visual placement inside .workspace-header and real browser form=\"\" attribute association across the DOM boundary is a UI-SPEC concern best confirmed by a human glance, per this phase's human_verify_mode: end-of-phase config."

duration: 25min
completed: 2026-07-17
status: complete
---

# Phase 2 Plan 1: Fade Toggle Summary

**SystemFilter.fade flips the graded side of matched bets (spread and total) without ever changing which games match, wired end-to-end through CLI, storage, and the web form.**

## Performance

- **Duration:** ~25 min
- **Completed:** 2026-07-17
- **Tasks:** 2
- **Files modified:** 10

## Accomplishments
- `SystemFilter.fade: bool = False` added alongside the existing favorite/underdog/home/away boolean fields, zero-impact on existing call sites
- `grade_bet` flips `normalized_side` under fade; `_grade_total_bet` flips `effective_total_side` under fade while leaving the `winner` computation untouched -- both proven to preserve pushes and leave `matches_system` completely unaware of fade (D-03)
- `--fade` CLI flag threaded into the backtest subcommand's `SystemFilter` construction
- `storage.py` round-trips `fade` through save/load, backward compatible with saved-system JSON written before this phase (no `fade` key -> loads as `False`, never `KeyError`)
- `fade` threaded through all six hand-enumerated `web.py` sites (`_form_values`, `_form_values_from_post`, `_form_from_system`, `_system_from_form`, `_query_args_from_form`, `_empty_form`) so it survives GET filter submission, POST /save, tab-switch links, and remove-filter links
- Fade System checkbox added to `templates/index.html`'s `.workspace-header`, associated with the sidebar form via `id="filters-form"` / `form="filters-form"`, reusing the `.check` class verbatim per UI-SPEC

## Task Commits

Each task was committed atomically:

1. **Task 1: Add SystemFilter.fade + fade-flip grading logic + CLI --fade flag** - `81b487f` (feat)
2. **Task 2: Persist fade through storage + wire web.py round-trip + render Fade toggle checkbox** - `666b7c6` (feat)

## Files Created/Modified
- `cfb_system_maker/models.py` - `SystemFilter.fade: bool = False`
- `cfb_system_maker/backtest.py` - fade flip in `grade_bet` (normalized_side) and `_grade_total_bet` (effective_total_side)
- `cfb_system_maker/cli.py` - `--fade` flag, threaded into non-`--load` `SystemFilter` construction
- `cfb_system_maker/storage.py` - `_system_to_dict`/`_system_from_dict` fade round-trip, `.get("fade", False)` for backward compat
- `cfb_system_maker/web.py` - fade in all six form/query enumeration sites
- `cfb_system_maker/templates/index.html` - `id="filters-form"`, Fade System checkbox in `.workspace-header`
- `tests/test_backtest.py` - spread flip, push survival, total flip, matched-count invariance
- `tests/test_cli.py` - CLI `--fade` produces different output at the same bet count
- `tests/test_storage_systems.py` - save/load round-trip, legacy-JSON backward compat
- `tests/test_web.py` - save/load, tab-switch, remove-filter-link persistence

## Decisions Made
- Fade toggle checkbox is physically outside `filters-form` (per D-01/UI-SPEC placement inside `.workspace-header`) and associates via the HTML5 `form="filters-form"` attribute rather than being nested inside the form element -- matches the plan's exact markup instruction.
- No `_REMOVE_PARAM_MAP` entry for `fade` -- it is a toggle, not a `describe()`-rendered active-filter sentence, so it has no remove-filter link (explicit plan instruction).

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] Corrected the web test assertion string for the checked Fade checkbox**
- **Found during:** Task 2 (writing `test_web_save_and_load_system_preserves_fade` and the tab-switch/remove-link fade tests)
- **Issue:** The plan's acceptance criteria specifies asserting `'name="fade" checked' in html`, but the plan's own markup instruction renders `<input type="checkbox" name="fade" form="filters-form" {% if form.fade %}checked{% endif %}>` -- the `form="filters-form"` attribute sits between `name="fade"` and `checked`, so the literal substring in the acceptance criteria never appears in real output. This is a self-inconsistency in the plan text (the acceptance criteria was written before the `form=` attribute was added to the markup instruction), not a bug in the implementation.
- **Fix:** Asserted `'name="fade" form="filters-form" checked' in html` instead, matching the markup the plan itself specifies. All three fade-persistence web tests (save/load, tab-switch, remove-filter-link) use this corrected string.
- **Files modified:** tests/test_web.py
- **Verification:** All three tests pass; the markup matches the UI-SPEC's exact `Interaction Contract -- Fade Toggle` snippet.
- **Committed in:** 666b7c6 (Task 2 commit)

**2. [Rule 1 - Bug] Removed an incorrect `fade=on in graph_href` assertion from the tab-switch test**
- **Found during:** Task 2 (writing `test_web_tab_switch_preserves_load_system_and_round_trips_fade`)
- **Issue:** Initially asserted the tab-switch link (`Results Graph` href) carries `fade=on` in its query string. In practice the tab-nav href is built from `query_href()`, which only carries the current URL's own query params (`load_system`, `tab`) -- identical to how the original (pre-fade) `test_web_tab_switch_preserves_load_system_and_round_trips` test behaves for `underdog`/`min_spread`. Fade round-trips correctly because `load_system=...` re-loads the full saved system (including fade) from storage on the second request, not because it's echoed into the intermediate href.
- **Fix:** Removed the incorrect assertion; kept the assertions that the second response (after following the tab-switch link) still renders the Fade checkbox as checked -- the actual persistence guarantee.
- **Files modified:** tests/test_web.py
- **Verification:** Test passes; matches the existing non-fade tab-switch test's assertion pattern exactly.
- **Committed in:** 666b7c6 (Task 2 commit)

---

**Total deviations:** 2 auto-fixed (both Rule 1 - test assertions corrected to match actual, correct implementation behavior; no production code changed as a result of either).
**Impact on plan:** No scope creep. Both deviations were test-authoring corrections discovered while mirroring existing test patterns; the implementation matches the plan's action/markup instructions exactly.

## Issues Encountered
None beyond the two test-assertion corrections documented above.

## User Setup Required
None - no external service configuration required.

## Next Phase Readiness
- `SystemFilter.fade` is a stable field that 02-02 (Grade computation) can read without further storage/web plumbing changes, since it already round-trips through every enumeration site.
- Full test suite (148 tests) passes; no regressions introduced.
- End-of-phase human-verify (per `human_verify_mode: end-of-phase` config) should include a visual/click check of the Fade System checkbox placement and Save-button submission in a real browser, since that surface (D7 above) was proven structurally, not via live browser interaction.

---
*Phase: 02-integrity-fade-grade*
*Completed: 2026-07-17*

## Self-Check: PASSED

All 10 modified source/test files and this SUMMARY.md verified present on disk. Both task commits (`81b487f`, `666b7c6`) verified present in git history.

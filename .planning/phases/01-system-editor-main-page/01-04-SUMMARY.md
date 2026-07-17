---
phase: 01-system-editor-main-page
plan: 04
subsystem: ui
tags: [flask, jinja, query-string, describe]

# Dependency graph
requires:
  - phase: 01-system-editor-main-page (Plan 02)
    provides: "_query_href(**overrides) request-scoped query-string-preserving href builder"
  - phase: 01-system-editor-main-page (Plan 03)
    provides: "describe(system) -> list[dict[text, key]] pure sentence-generation function"
provides:
  - "_query_args_from_form(form) -> MultiDict — materializes a loaded SavedSystem's canonical query state using real GET field names"
  - "_query_href_removing(key, base) -> str — builds a remove href for one describe() sentence, keeping the five ff_* parallel arrays aligned and always dropping load_system"
  - "_REMOVE_PARAM_MAP — maps describe() sentence keys to their real query-param name(s)"
  - "sentences render-context list (text/key/remove_href) consumed by templates/index.html's .active-filters-panel"
affects: [system-editor-main-page]

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "Remove-link construction always index-aligns ff_key/ff_op/ff_value/ff_perspective by position and treats ff_enable as a separate value-matched subset list, so the same removal logic is correct for both the full per-registry-feature query shape a real form submission produces and the compact active-rows-only shape _query_args_from_form produces for loaded systems."
    - "Loaded-system query state is materialized into ordinary filter params (bet_type/side/filter_seasons/ff_enable/etc.) before remove-link construction, rather than trying to strip filters from a bare ?load_system=name URL, so every remove link is always a real, followable query string."

key-files:
  created: []
  modified:
    - cfb_system_maker/web.py
    - cfb_system_maker/templates/index.html
    - cfb_system_maker/static/styles.css
    - tests/test_web.py

key-decisions:
  - "_query_href_removing() index-aligns the four ff_key/ff_op/ff_value/ff_perspective arrays by position but removes ff_enable by value match, not by index — ff_enable is a subset list (only enabled feature keys), never index-parallel to the other four arrays, so index-based removal on it would silently corrupt an unrelated row on real full-form submissions (all registered features present in ff_key, only some enabled)."
  - "Task 1 (backend wiring: _REMOVE_PARAM_MAP, _query_args_from_form, _query_href_removing, describe() wired into index()'s render context) was committed before Task 2 (template + CSS render of the sentence list) since the backend addition is purely additive — render_template gets an extra unused `sentences` kwarg until Task 2 lands — so the full pre-existing suite stays green at both commits."

requirements-completed: [EDIT-03]

coverage:
  - id: D1
    description: "describe(system) is wired into index()'s render context, and each sentence gets a working, correctly-scoped remove_href built via _query_href_removing / _REMOVE_PARAM_MAP"
    requirement: EDIT-03
    verification:
      - kind: integration
        ref: "tests/test_web.py#test_web_spread_range_remove_href_omits_both_bounds_and_preserves_other_params"
        status: pass
      - kind: integration
        ref: "tests/test_web.py#test_web_feature_filter_remove_href_keeps_five_arrays_aligned"
        status: pass
      - kind: integration
        ref: "tests/test_web.py#test_web_loaded_system_remove_link_materializes_and_drops_load_system"
        status: pass
    human_judgment: false
  - id: D2
    description: "The active-filter plain-English sentence list renders in the workspace directly after the stat-chip header, with a working per-row remove control, or the documented empty-state copy when no filters are active"
    requirement: EDIT-03
    verification:
      - kind: integration
        ref: "tests/test_web.py#test_web_no_active_filters_shows_empty_state_copy"
        status: pass
      - kind: integration
        ref: "tests/test_web.py#test_web_active_filter_sentence_renders_with_remove_control"
        status: pass
    human_judgment: true
    rationale: "Visual placement of .active-filters-panel relative to the stat-chip header and tabs nav, and the remove control's 36px interactive-target sizing/spacing per UI-SPEC.md, are design-contract properties best confirmed by looking at the rendered page. Confirmed via a live preview server render (GET /?side=home&favorite=on and GET /) showing correct copy, aria-label text, and DOM ordering (.metrics.stat-chips -> .active-filters-panel -> nav.tabs)."

# Metrics
duration: 10min
completed: 2026-07-17
status: complete
---

# Phase 1 Plan 4: Active-Filter Sentence List + Remove Links Summary

**Wired `describe(system)` into `index()`'s render context and rendered the active-filter plain-English sentence list in the workspace, with a per-row remove control built from a new `_query_href_removing()` helper that correctly materializes loaded-system state and keeps the five parallel `ff_*` arrays aligned.**

## Performance

- **Duration:** ~10 min
- **Completed:** 2026-07-17
- **Tasks:** 2 completed
- **Files modified:** 4 (web.py, index.html, styles.css, test_web.py)

## Accomplishments

- `_REMOVE_PARAM_MAP` maps all 11 core `describe()` sentence keys to their real query-param name(s) (`spread_range` -> `min_spread`+`max_spread`, `total_range` -> `min_total`+`max_total`, `seasons`/`weeks`/`teams`/`conferences`/`providers` -> their `filter_*` param names, the rest 1:1).
- `_query_args_from_form(form)` materializes a loaded `SavedSystem`'s canonical query state (bet_type/side/total_side always present, checked booleans as `on`, non-empty scalar fields, one aligned `ff_enable`/`ff_key`/`ff_op`/`ff_value`/`ff_perspective` row per active feature filter) so a bare `?load_system=name` URL becomes real, removable filter state.
- `_query_href_removing(key, base)` builds each sentence's remove href: preserves `tab=matches` when active, index-aligns removal across `ff_key`/`ff_op`/`ff_value`/`ff_perspective` for `ff:<feature_key>` rows while removing `ff_enable` by value match (not index, since it's a subset list), pops the mapped core param(s) for non-feature keys, and always drops `load_system`.
- `index()` now computes `sentences = describe(system)`, attaches `remove_href` per row (using the request's raw query args for query-built systems, or `_query_args_from_form(form)` for loaded systems), and passes `sentences` to the template.
- `templates/index.html` gained a `.active-filters-panel` section directly after the stat-chip header and before the tabs nav: one `<li>` per sentence with a `✕` remove control (`aria-label="Remove filter: {sentence text}"`), or the documented empty-state copy `"No filters applied yet — every game in the dataset is included."` when `sentences` is empty. `row.text`/`row.remove_href` render via Jinja's default auto-escaping (no `|safe`).
- `.active-filters-panel`, `.active-filters`, `.active-filters li`, `.remove-filter` (36px min interactive target, reusing the existing `.check`/`.segmented label` convention), and `.no-active-filters` CSS added.
- Full suite: 130 tests pass (117 pre-existing + 13 new).

## Task Commits

Each task was committed atomically:

1. **Task 1: Add canonical form-query serialization, remove-link construction, and describe() wiring** - `3e05e1a` (feat)
2. **Task 2: Render the active-filter sentence list with remove controls** - `610cf68` (feat)

**Plan metadata:** _(final docs commit follows this summary)_

## Files Created/Modified

- `cfb_system_maker/web.py` - Added `_REMOVE_PARAM_MAP`, `_query_args_from_form()`, `_query_href_removing()`; wired `describe(system)` into `index()`'s render context with per-sentence `remove_href`.
- `cfb_system_maker/templates/index.html` - Added `.active-filters-panel` section between the stat-chip header and the tabs nav.
- `cfb_system_maker/static/styles.css` - Added `.active-filters-panel`/`.active-filters`/`.active-filters li`/`.remove-filter`/`.no-active-filters`.
- `tests/test_web.py` - Added 8 integration tests: spread-range remove href (omits both bounds, preserves unrelated params), feature-filter remove href (proves all five `ff_*` arrays stay aligned on the surviving row via `urllib.parse.parse_qs`), a save -> load -> follow-remove-link -> assert-one-sentence-gone end-to-end regression test (also proving `load_system` is dropped and `save_name`/`tab` survive), the empty-state copy, and a basic sentence + remove-control render check.

## Decisions Made

- `_query_href_removing()` removes `ff_key`/`ff_op`/`ff_value`/`ff_perspective` by **position** (all four are always index-aligned, one row per feature, regardless of whether the query came from a real full-form submission or the compact loaded-system shape) but removes `ff_enable` by **value match** (it's a subset list of only-enabled feature keys, never index-parallel to the other four) — this is what keeps the five arrays correctly aligned for both query shapes described in the plan's read_first notes, not just the compact loaded-system one.
- Committed Task 1 (web.py backend wiring) before Task 2 (template rendering) even though several of Task 1's own acceptance-criteria tests assert on rendered HTML (`aria-label="Remove filter: ..."`) — those tests were added in the Task 2 commit alongside the template change they depend on, since Task 1's render-context addition (`sentences` kwarg) is inert without Task 2's template section. The full suite (including all pre-existing tests) stays green at both commits; only new behavior-dependent tests land with the commit that makes them observable.
- Verified visually via a local preview server run (`GET /?side=home&favorite=on` and `GET /`) confirming the empty-state copy, the sentence + `aria-label` text, and DOM ordering (`.metrics.stat-chips` -> `.active-filters-panel` -> `nav.tabs`) before committing Task 2.

## Deviations from Plan

None - plan executed exactly as written, including the review-incorporation notes (Codex finding #1: loaded-system materialization + always dropping `load_system`; finding #9: end-to-end save/load/remove-link test rather than a bare href-string check).

## Issues Encountered

One test-writing correction during development (not a plan deviation): an early draft of the loaded-system regression test asserted `value="two-filters"` would appear in the second page's rendered `save_name` input. That assertion was wrong — `_form_values()` (used for query-built, non-loaded requests) never reads `save_name` from GET params, only POST, which is pre-existing behavior outside this plan's scope. Fixed the test to instead verify `save_name=two-filters` survives as URL state via the rendered Results-Graph tab-nav href (which preserves the full query string through `_query_href`), matching what the plan's acceptance criteria actually requires ("save_name=name ... remain").

## User Setup Required

None - no external service configuration required.

## Next Phase Readiness

EDIT-03 is now fully complete (Plan 03's pure `describe()` logic + this plan's UI wiring and remove-links). `_query_href_removing()` and `_query_args_from_form()` are available for Plan 05 to extend when it adds the `theory` free-text field — `_query_args_from_form()` already has a documented, tested hook (`form.get("theory")`) to carry loaded theory text through remove actions once that field exists. No blockers for the next plan in this phase.

---
*Phase: 01-system-editor-main-page*
*Completed: 2026-07-17*

## Self-Check: PASSED

All modified files verified present on disk; both task commits (`3e05e1a`, `610cf68`) verified present in git log.

---
phase: 01-system-editor-main-page
plan: 05
subsystem: ui
tags: [flask, jinja, storage, theory]

# Dependency graph
requires:
  - phase: 01-system-editor-main-page (Plan 04)
    provides: ".active-filters-panel workspace section — theory panel inserted directly above it"
provides:
  - "SavedSystem.theory: str = '' — backward-compatible frozen-dataclass field"
  - "storage.load_saved_system(name, data_dir) -> SavedSystem — new read path exposing theory alongside SystemFilter"
  - "storage.save_system(name, system, data_dir, theory='') — persists theory into saved-system JSON"
  - "Sidebar editable theory textarea + read-only workspace theory-panel, both escaped via Jinja auto-escaping"
affects: [system-editor-main-page]

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "New storage read functions (load_saved_system) are added alongside existing ones (load_system) rather than changing existing signatures/return types, keeping pre-existing callers (cli.py, compare()) untouched."
    - "Free-text user input rendered via bare Jinja {{ }} expressions only (no |safe) at both edit and display locations, verified by an explicit grep in acceptance criteria and a behavioral stored-XSS test."

key-files:
  created: []
  modified:
    - cfb_system_maker/models.py
    - cfb_system_maker/storage.py
    - cfb_system_maker/web.py
    - cfb_system_maker/templates/index.html
    - cfb_system_maker/static/styles.css
    - tests/test_storage_systems.py
    - tests/test_web.py

key-decisions:
  - "load_system()/_system_from_dict() left completely unchanged (per 01-RESEARCH.md Pitfall 1); a new load_saved_system() function was added instead, reusing _system_from_dict() internally rather than duplicating its parsing logic."
  - "_query_args_from_form()'s theory handling was already present from Plan 04 (added proactively per its own SUMMARY note); this plan did not need to touch it, only rely on it."

requirements-completed: [EDIT-05]

coverage:
  - id: D1
    description: "SavedSystem.theory persists and loads backward-compatibly (defaults to '' for saves without theory and for pre-existing saved-system files with no theory key at all)"
    requirement: EDIT-05
    verification:
      - kind: unit
        ref: "tests/test_storage_systems.py#test_save_load_system_round_trips_theory"
        status: pass
      - kind: unit
        ref: "tests/test_storage_systems.py#test_save_system_defaults_theory_to_empty_string"
        status: pass
      - kind: unit
        ref: "tests/test_storage_systems.py#test_load_saved_system_backward_compatible_with_missing_theory_key"
        status: pass
      - kind: unit
        ref: "tests/test_storage_systems.py#test_save_load_list_system_round_trip"
        status: pass
    human_judgment: false
  - id: D2
    description: "Theory can be entered in the sidebar, saved via the existing Save System button, and reloads into both the sidebar textarea and a read-only workspace panel positioned directly above the active-filter sentence list; empty theory renders neither panel nor stray empty section"
    requirement: EDIT-05
    verification:
      - kind: integration
        ref: "tests/test_web.py#test_web_save_and_load_system_preserves_theory"
        status: pass
      - kind: integration
        ref: "tests/test_web.py#test_web_fresh_index_does_not_render_theory_panel"
        status: pass
      - kind: integration
        ref: "tests/test_web.py#test_web_theory_round_trips_through_get_form_submission"
        status: pass
      - kind: integration
        ref: "tests/test_web.py#test_web_loaded_system_remove_link_materializes_and_drops_load_system"
        status: pass
    human_judgment: true
    rationale: "Visual placement of .theory-panel directly above .active-filters-panel, and long-text wrapping (white-space: normal; overflow-wrap: anywhere) with no horizontal overflow, are design-contract properties best confirmed by looking at the rendered page. Backend round-trip through a live test-client run confirmed a 35-char unicode/emoji theory string and a 300-char theory string both survive save->load and render without truncation or mojibake (manual backstop check per plan's must_haves)."
  - id: D3
    description: "Theory text renders via Jinja auto-escaping only, never |safe, at both the sidebar textarea and workspace panel (stored-XSS mitigation, T-01-01)"
    requirement: EDIT-05
    verification:
      - kind: integration
        ref: "tests/test_web.py#test_web_theory_is_escaped_and_never_rendered_via_safe_filter"
        status: pass
      - kind: other
        ref: "grep -n \"|safe\" cfb_system_maker/templates/index.html (0 matches)"
        status: pass
    human_judgment: false

# Metrics
duration: 15min
completed: 2026-07-17
status: complete
---

# Phase 1 Plan 5: Theory Field (Sidebar Editor + Workspace Display) Summary

**Added `SavedSystem.theory` with backward-compatible JSON persistence, plus an editable sidebar textarea and an escaped, read-only workspace panel that appears directly above the active-filter sentence list only when theory is non-empty.**

## Performance

- **Duration:** ~15 min
- **Completed:** 2026-07-17
- **Tasks:** 2 completed
- **Files modified:** 7 (models.py, storage.py, web.py, index.html, styles.css, test_storage_systems.py, test_web.py)

## Accomplishments

- `SavedSystem.theory: str = ""` appended as a trailing default field — every pre-existing direct `SavedSystem(...)` construction site keeps working unmodified.
- `storage.save_system(name, system, data_dir, theory="")` threads theory into the saved JSON's top-level `"theory"` key; `_system_to_dict()` emits it alongside `"name"`/`"saved_at"`/`"system"`.
- New `storage.load_saved_system(name, data_dir) -> SavedSystem` reads the full saved-system payload including theory (`payload.get("theory", "")`, never a KeyError on legacy files with no `theory` key); `load_system()`/`_system_from_dict()` are completely untouched, so `cli.py` and the pre-existing `test_save_load_list_system_round_trip` test kept working unmodified.
- `web.py`'s `_form_values()`/`_form_values_from_post()` now read `theory` from `request.args`/`request.form`; `_form_values()` also now preserves `save_name` on GET (previously hardcoded to `""`), so a plain "Run System" GET submission no longer silently erases in-progress theory or the loaded-system name.
- `_form_from_system(system, loaded_name, theory="")` gained a `theory` parameter; `index()`'s loaded-system branch now calls `storage.load_saved_system()` (replacing `load_system()`) and threads `saved.theory` through.
- `save()` route persists `theory=form.get("theory", "")` via `save_system(...)`.
- Sidebar gained `<textarea name="theory">` (bundled into the existing filter form, saved via the existing `POST /save` — no new route, per CONTEXT.md D-02); workspace gained a `{% if form.theory %}` guarded `.theory-panel` section rendered directly above `.active-filters-panel` — omitted entirely (no empty `<section>`) when theory is `""`.
- Both render locations use bare `{{ form.theory }}` — Jinja's default auto-escaping only, no `|safe` anywhere in the file (verified by grep and a behavioral stored-XSS test).
- `.theory-field textarea` / `.theory-panel` / `.theory-panel h3` CSS added, matching existing `input`/`select`/`.range-chart h3` conventions; `.theory-panel` includes the long-text backstop (`white-space: normal; overflow-wrap: anywhere`).
- Manually verified the long-text/unicode backstop (must_haves backstop item): a 35-character theory string containing emoji, CJK, and accented characters, and a 300-character theory string, both round-tripped through save→load without truncation or mojibake.
- Full suite: 137 tests pass (130 pre-existing + 7 new: 3 in test_storage_systems.py, 4 in test_web.py, plus theory assertions added to the existing Plan 04 loaded-system remove-link test).

## Task Commits

Each task was committed atomically:

1. **Task 1: Add SavedSystem.theory + backward-compatible storage persistence** - `0928096` (feat)
2. **Task 2: Wire theory through web.py's form round-trip and render both the sidebar field and workspace panel** - `3342be5` (feat)

**Plan metadata:** _(final docs commit follows this summary)_

## Files Created/Modified

- `cfb_system_maker/models.py` - `SavedSystem.theory: str = ""` trailing field.
- `cfb_system_maker/storage.py` - `save_system()` gained `theory` kwarg; `_system_to_dict()` emits `"theory"`; new `load_saved_system()`.
- `cfb_system_maker/web.py` - `load_saved_system` import; theory plumbed through `_form_values()`, `_form_values_from_post()`, `_form_from_system()`, `index()`'s loaded-system branch, and `save()`.
- `cfb_system_maker/templates/index.html` - sidebar `<textarea name="theory">` before `.form-actions`; `.theory-panel` section before `.active-filters-panel`.
- `cfb_system_maker/static/styles.css` - `.theory-field textarea`, `.theory-panel`, `.theory-panel h3`.
- `tests/test_storage_systems.py` - 3 new tests: theory round-trip, theory default on save, backward compatibility with a legacy JSON file missing the `theory` key.
- `tests/test_web.py` - 4 new tests (save/load preserves theory, fresh GET has no `.theory-panel`, GET-form round-trip of unsaved theory + save_name, stored-XSS escaping) plus theory assertions added to the existing Plan 04 loaded-system remove-link regression test.

## Decisions Made

- Left `load_system()`/`_system_from_dict()` completely unchanged and added `load_saved_system()` as a new function instead — this was the plan's explicit approach (matching 01-RESEARCH.md Pitfall 1) to avoid touching `cli.py`'s existing `--load` contract or the pre-existing test's assertions.
- `_query_args_from_form()`'s theory serialization (`("theory", str(theory))` when non-empty) was already present, added proactively during Plan 04. This plan relied on it unchanged rather than re-adding it — confirmed via the extended loaded-system remove-link test, which now asserts `theory=` survives in the remove href and follows through to the second page.

## Deviations from Plan

None - plan executed exactly as written, including both review-incorporation notes (finding #7: `_form_values()` now reads `request.args.get("theory", "")` and also fixed `save_name` to read from GET args rather than hardcoding empty; finding #8: a behavioral stored-XSS test submitting `<script>`/quoted HTML asserts the rendered output is escaped, not just a `|safe` grep).

## Issues Encountered

None.

## User Setup Required

None - no external service configuration required.

## Next Phase Readiness

EDIT-05 is now complete — this was the last of the five EDIT-0x requirements for Phase 1 (system-editor-main-page). All 5 plans in this phase are done. No blockers for phase transition.

---
*Phase: 01-system-editor-main-page*
*Completed: 2026-07-17*

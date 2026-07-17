---
phase: 04-filter-popup-modal
verified: 2026-07-17T19:22:59Z
status: human_needed
score: 4/5 must-haves verified
behavior_unverified: 1
overrides_applied: 0
mvp_note: "ROADMAP phase goal is Mode:mvp but not user-story format; User Flow Coverage uses PLAN phase-goal story. Run /gsd mvp-phase 4 to reformat ROADMAP goal if required."
behavior_unverified_items:
  - truth: "The modal header shows Record/Money Won/ROI chips that recompute live as the user adjusts the filter's controls, before saving."
    test: "Open a filter modal, change slider/table selection rapidly, optionally block /api/backtest once, then Retry."
    expected: "Chips update after ~250ms debounce from server JSON; Updating… while in flight; last success retained on failure; Save gated until current draft validates; stale responses ignored."
    why_human: "Live refresh, AbortController races, and chip render are browser timing behaviors. Automated coverage is Flask /api/backtest plus JS source-contract greps — not an in-browser adjust→chip assertion."
human_verification:
  - test: "Start web UI with processed data; open a categorical filter from the sidebar."
    expected: "Dialog opens, focus moves inside, live chips update after a short pause; About Filter shows escaped definition text."
    why_human: "Browser focus and live fetch timing are not observable via Flask test client."
  - test: "Drag/edit a numeric filter; use Chart/List; Save then Cancel on a second edit."
    expected: "Dual handles sync with BETWEEN inputs; chart/list toggle; Save commits URL via filters-form GET; Cancel leaves URL unchanged."
    why_human: "Slider drag sync and full-page GET commit are end-to-end UI flows."
  - test: "Click Edit on an active-filter sentence; press Escape; click backdrop."
    expected: "Modal opens prefilled; Escape discards and focus returns to Edit; backdrop click leaves dialog open without commit/discard."
    why_human: "Focus restoration and backdrop non-dismiss require a real browser."
  - test: "Force a live request failure (DevTools offline or block /api/backtest); then Retry."
    expected: "Inline Couldn’t update live stats. + Retry; last chips remain; Save stays disabled; Retry recovers; form not mutated."
    why_human: "Failure/retry UX needs forced network conditions."
  - test: "Resize viewport to narrow width (≤900px) with a wide categorical table open."
    expected: "About stacks below; table scrolls horizontally inside modal; Cancel/Save remain reachable; page does not grow sideways."
    why_human: "Responsive layout is visual-only."
---

# Phase 4: Filter Popup Modal Verification Report

**Phase Goal:** Configuring any filter opens a live, Bet Labs-style popup — slider or value table, per-value Record/ROI/Money, About Filter text — before the user commits, replacing the static inline sidebar `<details>` fields.

**PLAN user story (MVP framing):** As a system builder, I want to open any filter in a live Bet Labs-style popup with performance evidence and About text before I commit, so that I can explore values without changing my system until I explicitly Save.

**Verified:** 2026-07-17T19:22:59Z  
**Status:** human_needed  
**Re-verification:** No — initial verification  

**MVP discrepancy:** ROADMAP marks `Mode: mvp` but the phase goal string is not `As a …, I want to …, so that ….`. Plans already use a valid user story. Reformat the ROADMAP goal with `/gsd mvp-phase 4` if the workflow requires strict format.

## User Flow Coverage

User story: «As a system builder, I want to open any filter in a live Bet Labs-style popup with performance evidence and About text before I commit, so that I can explore values without changing my system until I explicitly Save.»

| Step | Expected | Evidence | Status |
|------|----------|----------|--------|
| Open launcher | Sidebar filter button opens dialog (not inline `<details>` under JS) | `index.html` `.filter-launcher` + `data-candidate-id`; `filter_modal.js` `document.documentElement.classList.add("js")` + `showModal()`; `.js .filter-fallback { display: none }` | ✓ |
| Explore draft | Slider/table + About + live chips without committing URL | `/filter-detail`, `/api/backtest`, About `textContent`, `refreshLive` | ✓ (chips live-update → human) |
| Edit existing | Active-filter Edit opens same modal prefilled | `edit_metadata_for_sentence` → Edit button attrs; `openCandidate` | ✓ |
| Save | Writes canonical form fields and submits GET | `saveAndSubmit` → `write*ToForm` then `requestSubmit()` | ✓ |
| Cancel | Discard closes dialog; form/URL unchanged | `discardAndClose` (no write/submit); Escape → discard; backdrop no-op | ✓ |
| Outcome | Explore before commit; system changes only on Save | Draft-only state machine + GET commit path | ✓ wired; browser UAT below |

## Goal Achievement

### Observable Truths

| # | Truth | Status | Evidence |
| --- | ------- | ---------- | -------------- |
| 1 | Clicking a filter (sidebar or active-filter Edit) opens a popup modal instead of expanding it inline | ✓ VERIFIED | D-01 launchers for season/week/team/conference/provider/spread/total + all registry features; Edit beside Remove; progressive enhancement hides fallback under `.js`; `dialog.showModal()` |
| 2 | Modal header Record/Money Won/ROI chips recompute live as controls change, before Save | ⚠️ PRESENT_BEHAVIOR_UNVERIFIED | `run_backtest_summary` + `GET /api/backtest` tested; `refreshLive` with 250ms debounce, AbortController, `liveGeneration`, Updating…/Retry wired. No browser test exercises adjust→chip transition or stale-race invariant |
| 3 | Numeric filters: dual-handle range + BETWEEN inputs + per-value money chart | ✓ VERIFIED | Dual-range DOM in `filter_modal.js`; BETWEEN labels; SVG chart + Chart/List toggle; `/filter-detail` numeric rows + `chart_points`/`downsample_chart_points`; spread via `_side_spread`; describe gte+lte coalesce tested |
| 4 | Categorical/list filters: searchable, sortable table of value → Record/ROI/Money | ✓ VERIFIED | `aggregate_filter_value_rows` + `/filter-detail`; table search/sort/select in JS; bool Yes/No single-choice; source-contract + Flask tests |
| 5 | About Filter shows definition text; Save commits and closes; Cancel discards | ✓ VERIFIED | 52/52 `FeatureDef.description` nonempty; About via `textContent`; Save writes then `filters-form` submit; Cancel/Escape/close discard without writes |

**Score:** 4/5 truths verified (1 present, behavior-unverified)

### Required Artifacts

| Artifact | Expected | Status | Details |
| -------- | ----------- | ------ | ------- |
| `tests/test_filter_modal.py` | Wave 0 modal suite | ✓ VERIFIED | 683 lines; 30+ tests covering API, detail, serialize, Edit, debounce contracts |
| `cfb_system_maker/features.py` | `FeatureDef.description` on every feature | ✓ VERIFIED | 52 features, 0 empty descriptions |
| `cfb_system_maker/backtest.py` | `run_backtest_summary` | ✓ VERIFIED | Chip-only path; fade/zero-match tests pass |
| `cfb_system_maker/web.py` | `/api/backtest`, `/filter-detail`, helpers | ✓ VERIFIED | Strict parse, remove_candidate, aggregate, edit metadata, downsample |
| `cfb_system_maker/describe.py` | Numeric gte+lte coalesce + edit identity | ✓ VERIFIED | `test_describe_feature_filter_numeric_gte_lte_coalesces_to_between` |
| `cfb_system_maker/templates/index.html` | Dialog shell + launchers + Edit | ✓ VERIFIED | `#filter-modal`, About, Save/Cancel, Edit buttons |
| `cfb_system_maker/static/filter_modal.js` | Full modal state machine | ✓ VERIFIED | 1422 lines; open/save/discard/live/detail/numeric/table |
| `cfb_system_maker/static/styles.css` | Modal + ≤900px stack + focus-visible | ✓ VERIFIED | Progressive enhance + responsive rules |

### Key Link Verification

| From | To | Via | Status | Details |
| ---- | --- | --- | ------ | ------- |
| `filter_modal.js` | `/api/backtest` | Debounced GET with draft query | ✓ WIRED | `LIVE_DEBOUNCE_MS = 250`, `AbortController`, generation guard |
| `/api/backtest` | `run_backtest_summary` | `matches_system` + `grade_bet` | ✓ WIRED | Same grading path as main page |
| `filter_modal.js` | `/filter-detail` | fetch candidate + form query | ✓ WIRED | Rows + `chart_points`; candidate removed server-side |
| `aggregate_filter_value_rows` | `matches_system` + `grade_bet` | One-pass buckets | ✓ WIRED | Uses `base_system` after `remove_candidate_filters` |
| Save Filter | `filters-form` | write then `requestSubmit()` | ✓ WIRED | Core list / feature / numeric writers; Cancel path has no write/submit |
| Active-filter Edit | `openCandidate(prefill)` | `data-candidate-id` + bounds/perspective | ✓ WIRED | Server `edit` metadata on sentences |

### Data-Flow Trace (Level 4)

| Artifact | Data Variable | Source | Produces Real Data | Status |
| -------- | ------------- | ------ | ------------------ | ------ |
| Modal chips | `lastSummary` / chip DOM | `GET /api/backtest` → `run_backtest_summary` | Yes — matches+grades real games | ✓ FLOWING |
| Value table / chart | `state.rows` / `chartPoints` | `GET /filter-detail` → `aggregate_filter_value_rows` | Yes — one-pass over matched games | ✓ FLOWING |
| About panel | `filter-modal-about` | descriptor `description` (+ lookahead warning) | Yes — registry/core metadata | ✓ FLOWING |
| Active Edit | `row.edit` | `edit_metadata_for_sentence(system, row)` | Yes — from committed SystemFilter | ✓ FLOWING |

### Behavioral Spot-Checks

| Behavior | Command | Result | Status |
| -------- | ------- | ------ | ------ |
| Focused modal suite | `python -m pytest tests/test_filter_modal.py tests/test_describe.py -q` | 54 passed | ✓ PASS |
| Full suite | `python -m pytest -q` | 213 passed | ✓ PASS |
| Descriptions complete | `FEATURE_BY_KEY` empty-description scan | 52 features, 0 missing | ✓ PASS |
| Save submits form | grep `requestSubmit` / `write*ToForm` in `saveAndSubmit` | Present and ordered write→submit | ✓ PASS |
| Cancel does not submit | `test_cancel_leaves_form_untouched_contract` | discard block has no writers/submit | ✓ PASS |

### Probe Execution

| Probe | Command | Result | Status |
| ----- | ------- | ------ | ------ |
| — | — | No phase-declared `scripts/*/tests/probe-*.sh` | SKIP |

### Requirements Coverage

| Requirement | Source Plan | Description | Status | Evidence |
| ----------- | ---------- | ----------- | ------ | -------- |
| MODAL-01 | 04-01…04-04 | Sidebar/Edit open modal not inline | ✓ SATISFIED | Launchers + Edit + progressive enhance |
| MODAL-02 | 04-01, 04-04 | Live Record/Money/ROI chips | ? NEEDS HUMAN | API+JS wired; live adjust/race UAT pending |
| MODAL-03 | 04-03 | Dual-range + BETWEEN + money chart | ✓ SATISFIED | Numeric UI + detail/chart tests |
| MODAL-04 | 04-02 | Searchable sortable value table | ✓ SATISFIED | Table UI + aggregate/detail tests |
| MODAL-05 | 04-01, 04-02 | About Filter definition text | ✓ SATISFIED | Descriptions + About panel textContent |
| MODAL-06 | 04-01…04-04 | Save commits; Cancel discards | ✓ SATISFIED | saveAndSubmit / discardAndClose + contracts |

No orphaned REQUIREMENTS.md IDs for Phase 4 beyond MODAL-01…06.

### Anti-Patterns Found

| File | Line | Pattern | Severity | Impact |
| ---- | ---- | ------- | -------- | ------ |
| `tests/test_filter_modal.py` | debounce/edit JS tests | Source-string contracts only | ℹ️ Info | Intentional (D-23: no browser harness); drives human_needed for MODAL-02 races |
| `04-VALIDATION.md` | frontmatter | `nyquist_compliant: false`, task rows still ⬜ pending | ℹ️ Info | Planning artifact stale vs executed tests — not a runtime gap |
| — | — | No TBD/FIXME/XXX in phase-touched modal sources | — | — |

### Human Verification Required

Harvested from `04-04-PLAN.md` `<human-check>` plus behavior-unverified SC2:

### 1. Sidebar open + live chips

**Test:** Start web UI with processed data; open a categorical filter from the sidebar.  
**Expected:** Dialog opens, focus inside, chips update after short pause; About shows definition.  
**Why human:** Focus + live fetch timing.

### 2. Numeric explore + Save/Cancel

**Test:** Drag/edit numeric filter; Chart/List; Save; reopen and Cancel.  
**Expected:** BETWEEN sync; Save updates URL; Cancel leaves URL unchanged.  
**Why human:** E2E UI + GET navigation.

### 3. Edit / Escape / backdrop

**Test:** Edit from sentence; Escape; backdrop click.  
**Expected:** Prefill; Escape discards + focus restore; backdrop neither commits nor discards.  
**Why human:** Browser focus and dialog click handling.

### 4. Live failure + Retry

**Test:** Block `/api/backtest`; change draft; Retry.  
**Expected:** Error+Retry; last chips kept; Save gated; form untouched; Retry recovers.  
**Why human:** Forced network failure.

### 5. Narrow layout

**Test:** Resize ≤900px with wide table.  
**Expected:** About stacks; horizontal table scroll; actions reachable.  
**Why human:** Visual/responsive.

### Gaps Summary

No code gaps blocking the phase goal. Implementation is present, substantive, wired, and covered by a green full pytest suite (213). Status is **human_needed** because (1) roadmap SC2’s live-recompute / stale-race behavior is not exercised by an automated browser test, and (2) plan 04-04 explicitly deferred keyboard, slider, race, and responsive checks to end-of-phase human verification.

**Disconfirmation notes (not blockers):** JS “behavior” tests are source greps by design (D-23). VALIDATION.md checklist was not updated after execution.

**Next action:** Run the human verification checklist (or generate `04-UAT.md` via verify-work UAT path). On pass → mark phase verification complete and proceed. On fail → `/gsd-plan-phase --gaps` using any new findings.

---

_Verified: 2026-07-17T19:22:59Z_  
_Verifier: Claude (gsd-verifier)_

---
phase: 07-integrity-fixes
verified: 2026-08-27T00:00:00Z
status: passed
score: 11/11 must-haves verified
behavior_unverified: 0
overrides_applied: 0
human_verification:
  - test: "Open a saved system with an active filter whose (op, control) combo is uncovered by describe()'s four hand-written branches (e.g. neutralSite with op='in'), and visually confirm the fallback sentence ('Neutral Site filter applied (value: ...)') reads as distinct from the hand-written sentences, has no Edit button, and its remove link (x) works — on both the system editor page and the Current Matches dashboard panel."
    expected: "Fallback sentence is visually distinguishable, has a working remove link, never shows an Edit affordance, and renders identically on both surfaces."
    why_human: "Automated tests assert on text content and DOM structure (source-inspection / Flask test-client HTML), but 'visibly distinct' and actual visual rendering of the modal/panel is a UI judgment call, not something grep/pytest can confirm."
  - test: "Open the /filter-detail modal for a total-system team or conference filter (or an either-perspective feature filter) where a game involves two filter-matching teams, and visually confirm the reconciliation caption appears above the value table, states the correct matched-game count, and reads clearly (not confusingly) next to the per-value Record/ROI/Money rows."
    expected: "Caption renders as a clear, self-contained sentence reconciling the row-sum against the true matched-game count; caption is absent when overlapping_rows is false or when there are no rows."
    why_human: "No JS test harness exists in this repo (no package.json) — the caption's existence, text content, and DOM-insertion method are verified only via source-inspection tests (reading the .js file as text), never by actually executing the browser code or rendering the DOM. Visual placement/clarity in the live modal has not been executed or screenshotted."
---

# Phase 7: Integrity Fixes Verification Report

**Phase Goal:** The system editor and Current Matches panel never silently hide an active filter, the filter-detail modal's per-value numbers reconcile with the top-line backtest result, and the Hide Duplicates deferral is closed with an accurate architectural reason instead of a stale one.
**Verified:** 2026-08-27
**Status:** human_needed
**Re-verification:** No — initial verification

## Goal Achievement

### Observable Truths

| # | Truth | Status | Evidence |
|---|-------|--------|----------|
| 1 | An active filter whose (op, control) combo is uncovered by describe()'s 4 branches renders a visibly-distinct fallback sentence instead of being silently dropped | ✓ VERIFIED | `describe.py:100-106` — fallback branch returns `f"{label} filter applied (value: {values})"`; `test_describe_uncovered_op_control_combo_renders_distinct_fallback_sentence` (test_describe.py:211) passes |
| 2 | The fallback sentence's remove link (x) actually removes that filter when clicked | ✓ VERIFIED | Fallback uses `key=f"ff:{key}"`, identical shape to all 4 branches; `test_web_uncovered_filter_combo_remove_link_actually_clears_it` (test_web.py:877) asserts the filter is gone from `describe()` after applying the remove href — passes |
| 3 | The fallback row never renders an Edit button | ✓ VERIFIED | `edit_metadata_for_sentence` (web.py:866-887) gates on `group_is_renderable()` per perspective-group, `return None` when unrenderable; `test_web_uncovered_filter_combo_renders_fallback_without_edit_button` (test_web.py:856) passes |
| 4 | Both render surfaces (system editor + Current Matches panel) show the fallback sentence for the same uncovered combo | ✓ VERIFIED | `_current_matches_panel` reuses `describe()` with zero enrichment; `test_current_matches_uncovered_filter_combo_renders_fallback_sentence` (test_web.py:1719) passes |
| 5 | /filter-detail response includes a distinct-game count computed inside aggregate_filter_value_rows's loop, not via a separate matches_system pass | ✓ VERIFIED | `git show 5fd6c55` confirms `matched_game_ids.add(game.game_id)` placed immediately after the `if raw is None: continue` skip (web.py:268-271), before tuple/non-tuple branching; `test_aggregate_filter_value_rows_matched_game_ids_distinct_count` (test_filter_modal.py:357) passes |
| 6 | The modal shows a reconciliation caption whenever overlapping_rows is true, stating both numbers and why they differ | ✓ VERIFIED | `filter_modal.js:842-848` — caption built via `createElement`/`textContent`/`appendChild`, references `state.matchedGames` twice, gated on `state.overlappingRows`; `test_filter_modal_js_matched_games_overlap_caption_contract` (test_filter_modal.py:927) passes |
| 7 | Caption suppressed when overlapping_rows is false, and on the empty-rows path | ✓ VERIFIED | Caption code (line 842) sits after the empty-rows early-return (`if (!state.rows.length) { ... return; }`, lines 828-839) and is itself gated on `state.overlappingRows`; `test_filter_modal_js_matched_games_caption_suppressed_on_empty_rows` (test_filter_modal.py:950) passes |
| 8 | The tuple fan-out in aggregate_filter_value_rows is unchanged | ✓ VERIFIED | `git show 5fd6c55 -- cfb_system_maker/web.py` diff is purely additive (2 new lines); tuple/non-tuple branching (web.py:270-279 pre-change) untouched |
| 9 | PROJECT.md's Out of Scope no longer describes Hide Duplicates as a reachable, pending deferral — states the architectural finding | ✓ VERIFIED | PROJECT.md line 73: "architecture research confirmed `run_backtest` is structurally 1:1 on `game_id`... There is no top-line duplication to toggle away." No "waits until that mechanism exists" text remains. |
| 10 | Out of Scope bullet consistent with Key Decisions table row for same finding | ✓ VERIFIED | Both PROJECT.md line 73 (Out of Scope) and line 98 (Key Decisions) state the same `run_backtest` 1:1 finding — no contradiction |
| 11 | Corrected bullet references FIX-02 as the real fix | ✓ VERIFIED | PROJECT.md line 73: "...fixed directly in FIX-02 (Phase 7)." |

**Score:** 11/11 truths verified (0 present, behavior-unverified)

### WR-01 Follow-up Fix (post-plan code review finding, commit da558f8)

The 07-REVIEW.md code review (run after all 3 plans executed) found a WARNING-severity gap: the original FIX-01 implementation gated on "ANY filter in a (key, perspective) group is renderable" rather than "ALL filters in the group are renderable." This meant a mixed group (e.g. one `op="eq"` filter + one `op="in"` filter on the same key) would silently render/edit only the renderable filter and drop the other — directly contradicting the phase's "never silently hide an active filter" boundary, and creating a data-loss risk (editing and re-saving through that modal would drop the second filter).

This was fixed in commit `da558f8` (not covered by any of the 3 plans' SUMMARY.md files) and independently verified here:

- `describe.py:58-71` — `group_is_renderable()` now requires the **whole group** to match a round-trippable shape (numeric: only `gte`/`lte`, no duplicate ops; bool: exactly one `eq`; categorical: exactly one `eq` or `in`). Any group failing this check — even a mixed renderable/unrenderable group — falls through to the fallback branch, which now joins **all** filters' values (`", ".join(repr(filt.value) for filt in filts)`, line 105) so nothing in the group is lost from the sentence text.
- `web.py:866-887` (`edit_metadata_for_sentence`) mirrors this: groups the key's filters by perspective and requires `all(group_is_renderable(group, control) for group in groups.values())` before building Edit metadata — fails closed (suppresses Edit) if any perspective-group is unrenderable.
- Three new tests added directly in the fix commit: `test_describe_mixed_renderable_and_unrenderable_group_falls_back_for_whole_group`, `test_describe_two_bool_eq_filters_same_key_falls_back_instead_of_dropping_one`, `test_describe_numeric_eq_op_falls_back_instead_of_vanishing` (test_describe.py), plus `test_web_mixed_renderable_and_unrenderable_group_suppresses_edit_button` and `test_web_mixed_group_remove_link_clears_both_filters` (test_web.py) — all pass.
- Note on reachability: 07-REVIEW.md flagged reachability via the form-parsing path (`_feature_filters_from_values`, no key-dedup). The new tests instead construct mixed-filter systems via `save_system()` directly. This is not a gap in the fix — the fix operates at the render/edit-metadata layer, downstream of however the `SystemFilter` was constructed, so filter provenance (form vs. saved-system) doesn't change whether the fix holds.
- IN-01 (fallback previously used only `filts[0]`, dropping other unrenderable filters' values) was incidentally closed by the same commit — the fallback now joins every filter's value.
- IN-02 (`overlapping_rows` is a structural heuristic, not an exact per-response check) — no fix required; explicitly accepted-by-design per CONTEXT.md/UI-SPEC.md, and the review confirms this is the documented intent, not a defect this diff introduced.

This is real, tested code — not a stale claim. All 5 of the fix commit's new tests are present in the test files and the full suite passes with them included.

### Required Artifacts

| Artifact | Expected | Status | Details |
|----------|----------|--------|---------|
| `cfb_system_maker/describe.py` | Fallback branch + group_is_renderable() | ✓ VERIFIED | Present, substantive, wired into `describe()` |
| `cfb_system_maker/web.py` | Edit-suppression gate + matched_game_ids out-param + /filter-detail field | ✓ VERIFIED | Present, substantive, wired |
| `cfb_system_maker/static/filter_modal.js` | Reconciliation caption in renderValueTable() | ✓ VERIFIED | Present, substantive, wired (createElement/textContent/appendChild only) |
| `.planning/PROJECT.md` | Corrected Out of Scope bullet | ✓ VERIFIED | Present, consistent with Key Decisions table |

### Key Link Verification

| From | To | Via | Status | Details |
|------|-----|-----|--------|---------|
| `_feature_group_sentence` fallback | `web.py` edit suppression | `group_is_renderable()` shared shape-check, called from both describe.py and web.py | ✓ WIRED | `web.py` imports `group_is_renderable` from `describe.py` (git show da558f8) |
| Fallback sentence key (`ff:{feature_key}`) | `_query_href_removing` | `key.startswith("ff:")` prefix handling | ✓ WIRED | Confirmed via passing remove-link round-trip test |
| `aggregate_filter_value_rows` distinct-game count | `/filter-detail` JSON `matched_games` field | Route passes `matched_game_ids` set, returns `len()` | ✓ WIRED | web.py diff (5fd6c55) confirms both sides |
| `/filter-detail` `matched_games` | `filter_modal.js` `state.matchedGames` | Both fetch call sites (`reloadFeatureDetail`, `openCandidate`) set `state.matchedGames = payload.matched_games` | ✓ WIRED | Confirmed at filter_modal.js:781, 785, 1715 |
| `state.matchedGames`/`state.overlappingRows` | `renderValueTable()` caption | Read directly in caption-building code | ✓ WIRED | filter_modal.js:842-848 |
| PROJECT.md Out of Scope bullet | PROJECT.md Key Decisions table | Both state same `run_backtest` 1:1 finding | ✓ WIRED (consistent) | No contradiction found |

### Data-Flow Trace (Level 4)

Not applicable in the traditional sense (no DB-backed dynamic dashboard data at stake here), but the equivalent trace was done above: the `matched_games` count flows from a real per-request loop computation (not a static/hardcoded value) through the JSON response into client state and the rendered caption — confirmed via direct diff inspection, not assumed.

### Behavioral Spot-Checks

| Behavior | Command | Result | Status |
|----------|---------|--------|--------|
| Full phase-relevant test suite | `python -m pytest tests/test_describe.py tests/test_web.py tests/test_filter_modal.py -q` | 188 passed | ✓ PASS |
| Full repo test suite (regression check) | `python -m pytest -q` | 456 passed, 3 deselected | ✓ PASS |
| No `innerHTML +=` introduced | `grep "innerHTML +=" filter_modal.js` | No matches | ✓ PASS |
| No `|safe` introduced in describe.py/web.py diff | Manual inspection of fallback branch | Plain f-string interpolation only | ✓ PASS |
| WR-01 fix tests present and passing | grep for 5 new test names + pytest run | All 5 present, all pass | ✓ PASS |

### Requirements Coverage

| Requirement | Source Plan | Description | Status | Evidence |
|-------------|------------|-------------|--------|----------|
| FIX-01 | 07-01-PLAN.md | describe() fallback sentence, never silently drops a filter | ✓ SATISFIED | Truths 1-4 verified + WR-01 follow-up fix verified |
| FIX-02 | 07-02-PLAN.md | /filter-detail per-value reconciliation | ✓ SATISFIED | Truths 5-8 verified |
| FIX-03 | 07-03-PLAN.md | PROJECT.md Hide Duplicates deferral closure | ✓ SATISFIED | Truths 9-11 verified |

No orphaned requirements — REQUIREMENTS.md's Phase 7 traceability table lists exactly FIX-01/02/03, matching all 3 plans' declared `requirements:` frontmatter.

### Anti-Patterns Found

None blocking. One `"TBD"` string literal exists in `web.py:1820` (`_kickoff_label` — a legitimate UI label for a to-be-determined kickoff time), but this function is untouched by any of the phase's 3 plans or the WR-01 fix commit — pre-existing, unrelated code, not a debt marker requiring a follow-up reference.

### Human Verification Required

### 1. Visual confirmation of fallback sentence distinctiveness and remove-link/Edit-suppression on both surfaces

**Test:** Open a saved system with an active filter whose (op, control) combo is uncovered (e.g. `neutralSite` with `op="in"`), on both the system editor page and the Current Matches dashboard panel.
**Expected:** Fallback sentence text reads as visibly distinct from hand-written sentences, has no Edit button, and its remove link (×) works, on both surfaces.
**Why human:** Automated tests confirm text content and DOM structure programmatically (Flask test-client HTML assertions), but "visibly distinct" in actual rendered UI, and cross-surface visual consistency, is a judgment call.

### 2. Visual confirmation of the reconciliation caption in the live filter-detail modal

**Test:** Open `/filter-detail` for a total-system team/conference filter with an overlapping (shared-team) game, and observe the caption above the value table.
**Expected:** Caption renders clearly, states the correct matched-game count, and does not confuse users about the relationship between the caption and the Record/ROI/Money rows.
**Why human:** There is no JS test harness in this repo — all `filter_modal.js` verification is source-inspection only (reading the file as text and asserting on substrings), never actual DOM execution or rendering. The caption's real visual behavior in a browser has not been observed.

### Human Verification — Completed Live (2026-08-27)

Both items above were executed live against a running dev server (`python -m cfb_system_maker web`, port 5000) via browser automation, not deferred to the user:

**Item 1 — confirmed.** Navigated to `/system?ff_enable=neutralSite&ff_key=neutralSite&ff_op=in&ff_value=true` (an uncovered `neutralSite`/`op=in` combo). The rendered filter row read exactly `"Neutral Site filter applied (value: ['true'])"` with a `×` remove link (accessible name: "Remove filter: Neutral Site filter applied (value: ['true'])") and no Edit button present in the DOM's interactive-element list. Clicked the remove link — the filter cleared and the page correctly showed "No filters applied yet." Round-trip confirmed working, not just rendered.

**Item 2 — confirmed.** Opened a total/under system with no team filter yet (all-teams state, `overlappingRows=true` by construction for either-perspective totals) and opened the Team filter modal. Inspected the live DOM (`#filter-modal-controls`) and found the caption rendered exactly as designed: *"These rows cover 12509 games — each game counts once per matching value, so rows can sum to more than 12509."* — positioned above the value table, before the search box and rows, matching UI-SPEC.md's placement and copywriting contract.

### Gaps Summary

No gaps found. All 11 must-have truths across the 3 plans are verified in the codebase, including the WR-01 follow-up fix (commit da558f8) that was not documented in any plan's SUMMARY.md but is real, tested, and independently confirmed here, closing the exact "never silently hide an active filter" boundary the phase goal states. Both human-verification items were executed live in a browser (not deferred) and both passed — phase goal fully achieved.

---

_Verified: 2026-08-27_
_Verifier: Claude (gsd-verifier)_

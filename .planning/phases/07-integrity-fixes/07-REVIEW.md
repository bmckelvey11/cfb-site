---
phase: 07-integrity-fixes
reviewed: 2026-08-26T00:00:00Z
depth: standard
files_reviewed: 3
files_reviewed_list:
  - cfb_system_maker/describe.py
  - cfb_system_maker/web.py
  - cfb_system_maker/static/filter_modal.js
findings:
  critical: 0
  warning: 1
  info: 2
  total: 3
status: issues_found
---

# Phase 7: Code Review Report

**Reviewed:** 2026-08-26
**Depth:** standard
**Files Reviewed:** 3
**Status:** issues_found

## Summary

Reviewed the FIX-01 (`describe.py` fallback sentence + `web.py` Edit-suppression gate) and FIX-02 (`web.py` `matched_game_ids` out-param + `filter_modal.js` reconciliation caption) changes against `07-CONTEXT.md` and `07-UI-SPEC.md`'s locked decisions.

Both fixes are correctly implemented for the single-filter-per-key case that the added tests exercise: the fallback sentence uses the locked, deliberately-distinct wording and round-trips through `_query_href_removing`; the Edit-suppression gate correctly hides the Edit button for the exact uncovered-combo fixture tested (`op="in"` on a `bool` control); `matched_game_ids` is populated at the correct point in the loop (after the `resolve_candidate_value is None` skip, matching the documented "distinct games that reached a bucket" semantics); and the JS caption is built via `createElement`/`textContent` only, is suppressed on the empty-rows path, and is wired through both fetch call sites (`openCandidate`'s initial fetch and `reloadFeatureDetail`).

The one substantive issue found (WARNING) is a gap the phase's own stated goal doesn't actually close: when two `FeatureFilter`s share the same `(key, perspective)` — one with a renderable `(op, control)` shape and one without — both `_feature_group_sentence` and `edit_metadata_for_sentence`'s new gate silently ignore the unrenderable filter and render/edit only as if the renderable one were the only filter present, even though the backtest engine (`matches_system`/`feature_ok`) still applies both. This is reachable through the existing form-parsing path (no dedup-by-key exists anywhere in `_feature_filters_from_values` or `_validate_feature_filters_strict`), so it's a live rather than theoretical gap, and it directly contradicts CONTEXT.md's stated boundary ("must never silently hide an active filter").

## Warnings

### WR-01: A second filter on the same (key, perspective) with an unrenderable op is silently dropped from both the sentence and the Edit modal

**File:** `cfb_system_maker/describe.py:76-91`, `cfb_system_maker/web.py:866-897`

**Issue:** `_feature_group_sentence` groups `system.feature_filters` by `(key, perspective)` (`describe.py:128-130`) and, for bool/categorical controls, loops over all filters in the group but `return`s as soon as it finds *any* filter matching one of the four hand-written `(op, control)` branches (`describe.py:76-85`). If the group contains two filters for the same key — e.g. one `op="eq"` (renderable) and one `op="in"` (the exact uncovered-combo shape the FIX-01 tests use for a `bool` control) — the function renders only the `eq` sentence and never surfaces that a second, semantically-active filter exists on the same key.

`edit_metadata_for_sentence`'s new renderable-shape gate (`web.py:872-876`) mirrors this: `renderable` is `True` as soon as *any* filter in `filts` has a renderable op, so the Edit button appears and opens a modal built from `next((filt for filt in filts if filt.op == "eq"), None)` (`web.py:887-888`) — again silently discarding the `in` filter. Editing and re-saving through that modal would concretely drop the second filter's effect from the system (data loss on the next Save), not just from the display.

This state is reachable, not just theoretical: `_feature_filters_from_values` (`web.py:1231-1255`) and `_validate_feature_filters_strict` (`web.py:1108-1144`) both iterate `ff_key`/`ff_op`/`ff_value` by index with no dedup — `enabled = set(values.getlist("ff_enable"))` is checked by key membership, so repeating `ff_key=X` at two indices with the same `ff_enable=X` produces two `FeatureFilter`s for the same key, both of which pass strict validation and both of which `matches_system`/`feature_ok` will apply. No test in `test_describe.py` or `test_web.py` covers a mixed renderable+unrenderable-op group.

This directly contradicts `07-CONTEXT.md`'s stated phase boundary: "the system editor and Current Matches panel must never silently hide an active filter." FIX-01 closes this for a group where *every* filter is unrenderable, but not for a group where at least one filter is renderable and at least one isn't.

**Fix:** Either (a) extend the renderable-shape check in both `describe.py` and the `edit_metadata_for_sentence` gate to require that *all* filters in the group are covered by a hand-written branch before taking the "fully renderable" path — falling back to the distinct fallback sentence (and Edit-suppression) whenever any filter in the group is unrenderable — or (b) render one sentence per filter (not per group) so a partially-unrenderable group produces both the renderable sentence and a separate fallback sentence for the leftover filter(s), e.g.:

```python
# describe.py, bool/categorical branch
rendered_any = False
for filt in filts:
    text = ...
    if text is not None:
        sentences.append({"text": text, "key": f"ff:{key}"})
        rendered_any = True
    else:
        sentences.append({"text": f"{label} filter applied (value: {filt.value!r})", "key": f"ff:{key}"})
return sentences  # caller would need to extend() instead of append()
```

## Info

### IN-01: `describe.py` fallback uses only `filts[0]` even when multiple unrenderable filters exist in the group

**File:** `cfb_system_maker/describe.py:90-91`

**Issue:** When no filter in the group matches a hand-written branch, the fallback uses `filts[0]` only: `filt = filts[0]; return {"text": f"{label} filter applied (value: {filt.value!r})", ...}`. If the group has two or more filters, all unrenderable (e.g. two `in`-op filters on the same bool-control key with different values, or an `in` + a mismatched-perspective duplicate), only the first filter's value appears in the fallback text — the rest are silently dropped, same class of issue as WR-01 but confined entirely to the already-uncovered-combo case.

**Fix:** If groups can legitimately contain more than one unrenderable filter, either join all their values into the fallback text (`", ".join(repr(f.value) for f in filts)`) or emit one fallback sentence per filter rather than per group.

### IN-02: `overlapping_rows` is a structural heuristic, not an exact per-response check

**File:** `cfb_system_maker/web.py:771-773`

**Issue:** `overlapping_rows` (and therefore whether the FIX-02 reconciliation caption renders) is computed purely from `perspective == "either"` or `(candidate_id in ("core:team", "core:conference") and system.bet_type == "total")` — it does not check whether any row actually double-counts a game in the current response. For a data set where an either-perspective feature happens to have identical home/away values for every matched game, the caption will still render claiming rows "can sum to more than" the matched-game count, even though no row in that particular response actually does. This matches the documented intent (a structural upper-bound flag, not an exact per-response audit) and isn't something this diff introduces, but it's worth naming since it means the caption can appear in cases where the numbers it warns about don't actually diverge for that specific system.

**Fix:** No action required if the structural heuristic is the intended contract (it is, per `CONTEXT.md`/`UI-SPEC.md`). If a tighter guarantee is ever wanted, only set `overlapping_rows = True` when `sum(row_bet_counts) > matched_games` is actually observed in that response.

---

_Reviewed: 2026-08-26_
_Reviewer: Claude (gsd-code-reviewer)_
_Depth: standard_

---
phase: 08-neutral-site-indoor-unders-example
reviewed: 2026-08-27T00:00:00Z
depth: standard
files_reviewed: 2
files_reviewed_list:
  - cfb_system_maker/examples/neutral-site-indoor-unders.json
  - tests/test_storage.py
findings:
  critical: 0
  warning: 0
  info: 1
  total: 1
status: clean
---

# Phase 8: Code Review Report

**Reviewed:** 2026-08-27T00:00:00Z
**Depth:** standard
**Files Reviewed:** 2
**Status:** clean

## Summary

Reviewed the bundled 4th example system (`neutral-site-indoor-unders.json`) and the narrowed D-21 weather-filter guard in `tests/test_storage.py`. Both are sound.

**JSON schema correctness:** Verified the example file parses as valid JSON and its `system` dict contains exactly the `SystemFilter` field set (`storage._system_from_dict`/`_system_to_dict`), with no extra or missing keys. All three `feature_filters` entries (`neutralSite`, `gameIndoors`, `venue_dome`) reference real `FEATURE_REGISTRY` keys (confirmed at `cfb_system_maker/features.py:59`, `:161`, `:294`), each is `bool`-controlled and non-`team_scoped` (default `team_scoped=False`, `join="game_id"`), so `perspective: "single"` on all three is the correct shape — `single` passes through `effective_perspective()` unchanged regardless of `bet_type`, unlike `bet_side`/`opponent` which only apply to team-scoped features and get remapped to `"either"` on totals systems. `op: "eq"` / `value: true` is consistent with the boolean control type. `bet_type: "total"` + `total_side: "under"` matches a totals/unders system correctly.

**Guard scoping (`WEATHER_FILTER_EXCEPTIONS`):** Traced the exact exception logic at `tests/test_storage.py:108-117`. The exception set is keyed by `(example_name, feature_key)` tuples, and `example_name` is sourced from `list_examples()` which returns real bundled filenames — so a future example cannot silently inherit this exception unless it is literally named `neutral-site-indoor-unders` (i.e., it would overwrite this file, not add a new one). The `if not excepted` guard on line 113 only skips the `WEATHER_KEYS` assertion for the excepted pair; it does not skip the unconditional `SEASON_TO_DATE_KEYS` assertion on line 115, which runs for every filter on every example including this one — correctly matching the SUMMARY's stated intent that only the weather assertion, not season-to-date, is narrowed for the excepted pair. If this same example were to add a second weather-group filter (e.g. a hypothetical `windSpeed`), the loop would still fail it, since only the exact `(name, "gameIndoors")` tuple is excepted — confirming the guard cannot be silently widened by adding more filters to the one example that already has an exception.

**Theory text accuracy:** Cross-checked every number in the `theory` field against `08-01-SUMMARY.md`'s independently-verified backtest output: record 69-40/n=109, 63.30%, +20.66% ROI, p≈0.011, week splits (63.3%/63.6%/63.0%) and era splits (58.5%/67.9%) all match the SUMMARY's measured figures exactly. The theory correctly cites the app's own measured ROI/p-value (+20.66%/~0.011) rather than the source doc's figures for a different (2-filter) population (+20.85%/p=0.014) — this is a deliberate, documented divergence (SUMMARY line 30, 97, 121) since `venue_dome` is a no-op filter in this dataset (every indoor game is also domed) and the two record/rate/n figures are numerically identical to the doc's, only ROI/p differ due to per-bet rounding in a slightly different (but record-identical) filter combination. The Bonferroni caveat ("~25 situational splits," "does not survive correction") matches the source doc's own caveat. No overstatement found — the text explicitly frames this as "a lead, not an edge."

No Critical or Warning findings. One Info-level observation below.

## Info

### IN-01: `saved_at` timestamp is a fixed placeholder, consistent with existing examples but worth noting

**File:** `cfb_system_maker/examples/neutral-site-indoor-unders.json:3`
**Issue:** `"saved_at": "2026-08-26T00:00:00+00:00"` is a synthetic, round timestamp (midnight UTC) rather than the actual moment the file was authored (per the SUMMARY, work happened into 2026-08-27). This matches the pre-existing pattern in the other 3 bundled examples (e.g. `total-unders-high-lines.json` uses `"2026-07-20T00:00:00+00:00"`), so it is not a defect introduced by this phase — flagging only because a bundled example's `saved_at` is display-only cosmetic data (shown as "Copied" provenance) and not verified against any commit timestamp anywhere in the test suite.
**Fix:** No action needed; this is pre-existing convention, not a regression. If exactness of `saved_at` for bundled examples is ever desired, a test could assert it parses as a valid ISO-8601 datetime, but no such test exists for the other 3 examples either, so adding one here alone would be inconsistent.

---

_Reviewed: 2026-08-27T00:00:00Z_
_Reviewer: Claude (gsd-code-reviewer)_
_Depth: standard_

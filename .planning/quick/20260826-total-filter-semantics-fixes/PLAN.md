---
task: total-filter-semantics-fixes
date: 2026-08-26
mode: quick
status: in-progress
---

# Quick Task: Total-system filter semantics fixes (audit findings 1-3)

Source: in-session filter audit (2026-08-26). Three confirmed defects that make a
saved system mean something different than displayed.

## Fix 1 — team/conference filters on total systems match either side

- `backtest.py matches_system`: on `bet_type == "total"`, `teams`/`conferences`
  match if either the home or away side is in the set (spread behavior unchanged:
  bet-side only). Verified defect: Georgia team filter on totals matched 86 or 70
  of 156 Georgia games depending on the hidden spread-side radio.
- `web.py resolve_candidate_value`: `core:team` / `core:conference` on totals
  return the (home, away) tuple so the modal buckets per team on both sides.
- `web.py CORE_FILTER_META`: descriptions updated to state the split semantics.
- Tests: total + team on away side matches; spread unchanged; modal rows include
  away-side teams for totals.

## Fix 2 — bet_side/opponent perspectives on totals

- `features.py`: add `effective_perspective(bet_type, perspective)` — collapses
  bet_side/opponent to "either" when bet_type is total.
- `web.py _validate_feature_filters_strict`: reject bet_side/opponent when
  `bet_type == "total"` (StrictParseError invalid_perspective) — extends
  a1e6e19 from /filter-detail to /api/backtest.
- `web.py _system_from_form` + `storage.py _system_from_dict` /
  `_finalist_system_from_dict`: normalize via `effective_perspective` so the
  HTML path and legacy saved systems resolve as "either" (disclosed in
  describe() as "Either team's ..."), never the vestigial side field.
- Tests: /api/backtest 400 on total+bet_side; form parse normalizes; storage
  load normalizes; spread systems untouched.

## Fix 3 — modal Save clears feature bounds at domain edges

- `filter_modal.js writeNumericToForm`: feature-numeric branch mirrors the core
  range behavior — a bound sitting at the observed domain edge is written as ""
  (filter dropped server-side); both bounds at edges unchecks ff_enable.
  Prevents "open modal, click Save" from silently excluding games with missing
  feature values (verified: 261 games dropped for full-domain
  weather_temperature).
- Test: JS source contract test (same pattern as existing modal contract tests).

## Verify

`python -m pytest` green; one atomic commit per fix; push.

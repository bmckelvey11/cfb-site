---
type: quick
slug: numeric-filter-step-intervals
status: complete
created: 2026-07-20
completed: 2026-07-20
files_modified:
  - cfb_system_maker/static/filter_modal.js
---

# Summary: Numeric filter steps in 0.5 intervals, not continuous

## What changed

`cfb_system_maker/static/filter_modal.js` (+28 / -4):

- Added `stepForDomain(domainMin, domainMax)` next to the existing formatters —
  returns a step scaled to the feature's domain span.
- Numeric builder computes `rangeStep` once and applies it to all four controls
  (`minRange`, `maxRange`, `minNumber`, `maxNumber`), replacing `step = "any"`.

## Why not a flat 0.5

A blanket 0.5 would have regressed ~10 of 37 numeric features whose domain is
0-1 (win pct, ATS pct, success rates, win probabilities, havoc rates, returning
production) — their sliders would offer only 0, 0.5, and 1.0. The span-scaled
rule gives spread (~120) and total (~70) exactly the requested 0.5 while leaving
rate features usable. User chose this over the literal flat-0.5 option.

## Verification

`node --check` passes. Assertions were run against `stepForDomain` extracted
from the shipped file, so they test the real code path:

| Feature | Domain | Span | Step |
|---------|--------|------|------|
| spread | -60..60 | 120 | 0.5 |
| total | 20..90 | 70 | 0.5 |
| temperature | 0..110 | 110 | 0.5 |
| explosiveness | 0..3 | 3 | 0.1 |
| win pct / success rate / win prob | 0..1 | 1 | 0.01 |
| ppa | -1..1 | 2 | 0.01 |
| elo | 1000..2200 | 1200 | 1 |
| moneyline | -2000..2000 | 4000 | 1 |
| attendance | 0..110000 | 110000 | 1 |
| degenerate | 5..5 | 0 | any |

All 12 assertions pass. Served asset confirmed updated (`stepForDomain` present,
zero `step = "any"` remaining). Python suite: 213 passed (unaffected — no Python
changed).

## Notes / follow-ups

- No JS test runner exists in this project (Python + vanilla JS by design), so
  the check above is a one-shot assertion script rather than a committed JS test.
  Adding a JS test framework for this would be disproportionate.
- Initial `state.min` / `state.max` are left as-is rather than pre-rounded to the
  step; browsers snap slider positions on interaction. Revisit only if the
  unrounded initial readout looks wrong in practice.
- Not yet exercised through a real browser render — the preview pane reported a
  0x0 viewport this session, so the visual confirmation is deferred to Phase 04
  UAT Test 2.

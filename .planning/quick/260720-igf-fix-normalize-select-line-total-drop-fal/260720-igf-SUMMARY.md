---
task: 260720-igf
slug: fix-normalize-select-line-total-drop-fallback
type: quick
status: complete
files_modified:
  - tests/test_normalize.py
  - cfb_system_maker/normalize.py
completed: 2026-07-20
---

# Quick Task 260720-igf: Total falls back to sibling provider when preferred line lacks it

## One-liner

`normalize_games` now falls back to the first sibling provider's `overUnder`
when the spread-selected (e.g. `consensus`) line has a null total, fixing the
~93-97% total-null rate for 2013-2016 seasons.

## Problem

`_select_line` picks the preferred provider (`consensus`) for the spread.
`normalize_games` read `total` from that SAME selected line. For 2013-2016
seasons, `consensus` commonly has `spread` populated but `overUnder` null,
while sibling providers on the same game (`teamrankings`, `numberfire`) carry
`overUnder`. Because total was read only from the selected line, it was
dropped even when a sibling had it.

## Fix

Added `_select_total(lines, selected_line)` in `cfb_system_maker/normalize.py`,
mirroring `_select_line`'s structure:
- If the spread-selected line already has a non-null total, use it.
- Otherwise, return the FIRST line in `betting_game["lines"]` (original list
  order) with a non-null `overUnder`/`over_under`/`total`.
- Otherwise, fall back to the selected line itself (total stays `None`).

Wired into `GameRecord` construction — `total=` now reads from
`_select_total(...)` instead of only `selected_line`. `provider=` and
`spread=` are unchanged and still come from `selected_line` (spread's
provider is preserved, per plan constraint).

## Tasks completed

1. **TDD RED** — Added `test_total_falls_back_to_sibling_provider_when_preferred_line_lacks_it`
   in `tests/test_normalize.py`, pinning: `provider == "consensus"` (spread
   source preserved), `spread == -11.5` (from consensus), `total == 56`
   (first sibling — teamrankings — not 58 from numberfire). Confirmed it
   failed against unmodified `normalize.py` (`total` was `None`).
   Commit: bb9090d
2. **TDD GREEN** — Added `_select_total` helper and wired it into
   `normalize_games`. All 6 tests in `tests/test_normalize.py` pass,
   including the two guardrail tests named in the plan
   (`test_normalize_uses_first_usable_line_when_provider_missing` still
   yields `total is None`; `test_normalize_joins_games_to_consensus_lines`
   still yields `total == 52.5`).
   Commit: f33ec9e

## Deviations from Plan

None — plan executed exactly as written.

## Verification

- `python -m pytest tests/test_normalize.py` — 6/6 passed.
- `python -m pytest` (full suite) — 214/214 passed.
- No changes to `_select_line`, `models.py`, or `storage.py` (spread
  selection, `GameRecord.provider`, and CSV schema unchanged, as required).

## Self-Check: PASSED

- FOUND: cfb_system_maker/normalize.py (modified, contains `_select_total`)
- FOUND: tests/test_normalize.py (modified, contains new test)
- FOUND: bb9090d (test commit)
- FOUND: f33ec9e (fix commit)

---
phase: 03-data-depth-breadth
plan: 02
subsystem: data-pipeline
tags: [DATA-01, normalize, line-floor, docs]
requires: [normalize._select_line, tests/test_normalize.py]
provides: [line-floor-gate-test, docs/data-line-floor.md]
affects: []
tech-stack:
  added: []
  patterns: [characterization-test, construct-dict-and-assert]
key-files:
  created:
    - docs/data-line-floor.md
  modified:
    - tests/test_normalize.py
decisions:
  - "DATA-01 line floor confirmed as 2013; 'backfill earlier' closed by verification (live probe 03-03), not code change."
metrics:
  duration: 6min
  completed: 2026-07-17
status: complete
---

# Phase 3 Plan 2: DATA-01 Line-Floor Guard Summary

Locked the D-02 "require a usable line" floor gate with characterization tests (line-less seasons contribute 0 rows, floor season 2013 non-empty) and documented the confirmed 2013 CFBD betting-line floor with on-disk evidence, closing "backfill earlier than 2013" as verification-gated.

## What Was Built

- **Task 1** (`tests/test_normalize.py`): Three tests asserting the UNCHANGED `normalize._select_line` behavior:
  - `test_line_less_game_contributes_zero_records` — game with `lines: []` → 0 records (the pre-floor / 2012 clean behavior).
  - `test_all_unusable_lines_contribute_zero_records` — lines present but all lacking spread and overUnder → 0 records.
  - `test_usable_line_contributes_one_record` — floor season (2013) with a usable consensus line → exactly 1 record.
- **Task 2** (`docs/data-line-floor.md`): Reference doc recording the confirmed 2013 floor, the 2012-zero-usable-lines evidence, the line-vs-game coverage distinction, the D-02 rule, the fully-parameterized fetch/build path, and the closure mechanism (live re-confirmation probe 03-03).

## Verification

- `python -m pytest tests/test_normalize.py -x` → 5 passed.
- `cfb_system_maker/normalize.py` unchanged (git diff empty) — key_link honored.
- `docs/data-line-floor.md` present, states 2013, references probe 03-03, contains no token / `env.env` material (T-03-02-02 mitigation verified).

## Deviations from Plan

None — plan executed exactly as written. The positive-case test was added as a distinct `test_usable_line_contributes_one_record` (not a duplicate of the existing join test) to make the floor gate's 0-vs-1 semantics explicit, per the plan's allowance.

## TDD Gate Compliance

Task 1 is flagged `tdd="true"` but is by design a **characterization test** that locks existing behavior — the plan explicitly forbids modifying `normalize.py` (key_link) and the tests pass immediately because the behavior already exists. This is the intended outcome, not an unexpected RED-phase pass. No `feat` implementation commit exists or is expected; the RED/GREEN cycle does not apply to a behavior-lock test.

## Commits

- 9fd46ca: test(03-02): lock DATA-01 line-floor gate
- ee32bd4: docs(03-02): document confirmed 2013 CFBD betting-line floor

## Self-Check: PASSED

- FOUND: docs/data-line-floor.md
- FOUND: tests/test_normalize.py (3 new tests)
- FOUND: commit 9fd46ca
- FOUND: commit ee32bd4

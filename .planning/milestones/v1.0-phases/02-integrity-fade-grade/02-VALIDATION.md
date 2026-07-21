---
phase: 2
slug: integrity-fade-grade
status: draft
nyquist_compliant: true
wave_0_complete: false
created: 2026-07-17
---

# Phase 2 — Validation Strategy

> Per-phase validation contract for feedback sampling during execution.

---

## Test Infrastructure

| Property | Value |
|----------|-------|
| **Framework** | pytest (already vendored; `pytest.ini` sets `testpaths=tests`) |
| **Config file** | `pytest.ini` (repo root) |
| **Quick run command** | `.venv/Scripts/python.exe -m pytest tests/test_backtest.py tests/test_storage_systems.py tests/test_web.py -q` |
| **Full suite command** | `.venv/Scripts/python.exe -m pytest -q` |
| **Estimated runtime** | ~10 seconds |

---

## Sampling Rate

- **After every task commit:** Run `.venv/Scripts/python.exe -m pytest tests/test_backtest.py tests/test_storage_systems.py tests/test_web.py -q`
- **After every plan wave:** Run `.venv/Scripts/python.exe -m pytest -q`
- **Before `/gsd-verify-work`:** Full suite must be green
- **Max feedback latency:** 15 seconds

---

## Per-Task Verification Map

| Task ID | Plan | Wave | Requirement | Threat Ref | Secure Behavior | Test Type | Automated Command | File Exists | Status |
|---------|------|------|-------------|------------|-----------------|-----------|-------------------|-------------|--------|
| 02-01-01 | 01 | 1 | INTG-01 | T-02-02 | Fade flips graded side (spread + total) via `grade_bet`/`_grade_total_bet`; matched-game count unchanged; pushes stay pushes; `--fade` CLI flag works | unit | `.venv/Scripts/python.exe -m pytest tests/test_backtest.py tests/test_cli.py -k fade -x` | ✅ (test_backtest.py, test_cli.py pre-exist) | ⬜ pending |
| 02-01-02 | 01 | 1 | INTG-01 | T-02-01 | `fade` persists through save/load JSON round-trip, defaults False when key missing; Fade checkbox round-trips GET form, POST /save, tab-switch links, remove-filter links | integration | `.venv/Scripts/python.exe -m pytest tests/test_storage_systems.py tests/test_web.py -k fade -x` | ✅ (test_storage_systems.py, test_web.py pre-exist) | ⬜ pending |
| 02-02-01 | 02 | 2 | INTG-02 | — | Each of 5 sub-score helpers (sample-size score reads `stats.wilson_low`/`stats.break_even_rate` per D-04, floored by decided bet count -- not a raw bet count alone) returns documented value at/around threshold boundaries; `count_overfit_filters` follows D-06 exactly; `compute_grade` returns correct letter for representative composites, `None` for zero matched bets | unit | `.venv/Scripts/python.exe -m pytest tests/test_backtest.py -k "grade or overfit or compute_grade" -x` | ✅ (test_backtest.py pre-exists) | ⬜ pending |
| 02-02-02 | 02 | 2 | INTG-02 | T-02-03 | Grade chip renders computed letter/em-dash in `templates/index.html` through plain Jinja auto-escaping (no `\|safe`); the pre-revision em-dash assertion in `tests/test_web.py` is updated in the same task | integration | `.venv/Scripts/python.exe -m pytest tests/test_web.py -k grade -x` | ✅ (test_web.py pre-exists) | ⬜ pending |

*Status: ⬜ pending · ✅ green · ❌ red · ⚠️ flaky*

---

## Wave 0 Requirements

*None — every test file referenced above (`tests/test_backtest.py`, `tests/test_cli.py`, `tests/test_storage_systems.py`, `tests/test_web.py`) already exists in the repo (shipped in Phase 1 or earlier). Both plans' Task 1 is `tdd="true"` (RED-first: the failing test is written and run before the implementation, inside the task itself), so this phase has no separate pre-execution test-scaffolding wave. Nyquist compliance is satisfied because every task in both plans already carries a concrete `<automated>` command -- neither `02-01-PLAN.md` nor `02-02-PLAN.md` contains any `MISSING` placeholder -- not by a dedicated Wave 0 plan.*

---

## Manual-Only Verifications

*None: All phase behaviors have automated verification.*

---

## Validation Sign-Off

- [x] All tasks have `<automated>` verify or Wave 0 dependencies -- all 4 tasks across both plans carry a concrete `<automated>` command; zero `MISSING` placeholders.
- [x] Sampling continuity: no 3 consecutive tasks without automated verify -- all 4 tasks have automated verify.
- [x] Wave 0 covers all MISSING references -- vacuously true: there are no `MISSING` references in either plan.
- [x] No watch-mode flags -- all commands are one-shot `pytest ... -x` invocations, no `--watch`.
- [x] Feedback latency < 15s -- targeted `-k`-filtered runs against a ~10s full suite.
- [x] `nyquist_compliant: true` set in frontmatter

**Approval:** pending

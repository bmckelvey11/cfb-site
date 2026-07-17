---
phase: 2
slug: integrity-fade-grade
status: draft
nyquist_compliant: false
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
| **Quick run command** | `python -m pytest tests/test_backtest.py tests/test_storage.py tests/test_web.py -q` |
| **Full suite command** | `python -m pytest` |
| **Estimated runtime** | ~10 seconds |

---

## Sampling Rate

- **After every task commit:** Run `python -m pytest tests/test_backtest.py tests/test_storage.py tests/test_web.py -q`
- **After every plan wave:** Run `python -m pytest`
- **Before `/gsd-verify-work`:** Full suite must be green
- **Max feedback latency:** 15 seconds

---

## Per-Task Verification Map

| Task ID | Plan | Wave | Requirement | Threat Ref | Secure Behavior | Test Type | Automated Command | File Exists | Status |
|---------|------|------|-------------|------------|-----------------|-----------|-------------------|-------------|--------|
| 02-01-TBD | TBD | 0 | INTG-01 | — | Fade flips graded side; matched-game count unchanged; pushes stay pushes | unit | `python -m pytest tests/test_backtest.py -k fade -x` | ❌ W0 | ⬜ pending |
| 02-01-TBD | TBD | 0 | INTG-01 | — | `fade` persists through save/load JSON round-trip, defaults False when key missing | unit | `python -m pytest tests/test_storage.py -k fade -x` | ❌ W0 | ⬜ pending |
| 02-01-TBD | TBD | 0 | INTG-01 | — | Fade checkbox round-trips GET form, POST /save, tab-switch links, remove-filter links | integration | `python -m pytest tests/test_web.py -k fade -x` | ❌ W0 | ⬜ pending |
| 02-02-TBD | TBD | 0 | INTG-02 | T-02-01 | Each of 5 sub-score helpers returns documented value at/around threshold boundaries | unit | `python -m pytest tests/test_backtest.py -k grade -x` | ❌ W0 | ⬜ pending |
| 02-02-TBD | TBD | 0 | INTG-02 | T-02-01 | `compute_grade` returns correct letter for representative composites, `None` for zero matched bets | unit | `python -m pytest tests/test_backtest.py -k compute_grade -x` | ❌ W0 | ⬜ pending |
| 02-02-TBD | TBD | 0 | INTG-02 | — | `count_overfit_filters` follows D-06 counting rule exactly | unit | `python -m pytest tests/test_backtest.py -k overfit -x` | ❌ W0 | ⬜ pending |
| 02-02-TBD | TBD | 0 | INTG-02 | — | Grade chip renders computed letter/em-dash in `templates/index.html`; `test_web.py:134` assertion updated | integration | `python -m pytest tests/test_web.py -k grade -x` | ❌ W0 (modifies existing test) | ⬜ pending |

*Status: ⬜ pending · ✅ green · ❌ red · ⚠️ flaky*

---

## Wave 0 Requirements

- [ ] `tests/test_backtest.py` — add fade-flip tests (spread + total), 5 sub-score boundary tests, `compute_grade` composite tests, `count_overfit_filters` D-06 rule tests
- [ ] `tests/test_storage.py` — add fade JSON round-trip test, backward-compat "missing fade key defaults False" test
- [ ] `tests/test_web.py` — add fade checkbox round-trip tests (save/load, tab-switch, remove-filter-link preservation), update existing Grade em-dash assertion at line 134
- [ ] Framework install: none — pytest already present, no config changes needed

---

## Manual-Only Verifications

*None: All phase behaviors have automated verification.*

---

## Validation Sign-Off

- [ ] All tasks have `<automated>` verify or Wave 0 dependencies
- [ ] Sampling continuity: no 3 consecutive tasks without automated verify
- [ ] Wave 0 covers all MISSING references
- [ ] No watch-mode flags
- [ ] Feedback latency < 15s
- [ ] `nyquist_compliant: true` set in frontmatter

**Approval:** pending

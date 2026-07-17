---
phase: 04
slug: filter-popup-modal
status: draft
nyquist_compliant: false
wave_0_complete: false
created: 2026-07-17
---

# Phase 04 — Validation Strategy

> Per-phase validation contract for feedback sampling during execution.

---

## Test Infrastructure

| Property | Value |
|----------|-------|
| **Framework** | pytest 9.0.3 with Flask 3.1.3 test client |
| **Config file** | `pytest.ini` |
| **Quick run command** | `python -m pytest tests/test_filter_modal.py -x` |
| **Full suite command** | `python -m pytest` |
| **Estimated runtime** | Quick target under 10 seconds; full suite runtime measured during execution |

---

## Sampling Rate

- **After every task commit:** Run `python -m pytest tests/test_filter_modal.py -x`
- **After every plan wave:** Run `python -m pytest tests/test_web.py tests/test_web_features.py tests/test_filter_modal.py -x`
- **Before `/gsd-verify-work`:** Run `python -m pytest`; full suite must be green
- **Max feedback latency:** 10 seconds for the focused phase suite

---

## Per-Task Verification Map

| Task ID | Plan | Wave | Requirement | Threat Ref | Secure Behavior | Test Type | Automated Command | File Exists | Status |
|---------|------|------|-------------|------------|-----------------|-----------|-------------------|-------------|--------|
| 04-01-01 | 01 | 1 | MODAL-05 | T-04-XSS | Descriptions are non-empty plain text and escaped | unit | `python -m pytest tests/test_filter_modal.py -x -k "description or escaped"` | ❌ W0 | ⬜ pending |
| 04-01-02 | 01 | 1 | MODAL-02, MODAL-06 | T-04-INPUT | Strict parser rejects unknown/illegal candidate input and atomically replaces a candidate | unit | `python -m pytest tests/test_filter_modal.py -x -k "parser or serialize"` | ❌ W0 | ⬜ pending |
| 04-02-01 | 02 | 2 | MODAL-02 | T-04-TAMPER | `/api/backtest` computes authoritative spread/total/Fade metrics server-side | integration | `python -m pytest tests/test_filter_modal.py -x -k "api_backtest"` | ❌ W0 | ⬜ pending |
| 04-02-02 | 02 | 2 | MODAL-03, MODAL-04 | T-04-DOS | `/filter-detail` performs bounded one-pass distribution with deterministic rows | integration | `python -m pytest tests/test_filter_modal.py -x -k "filter_detail or numeric or categorical or boolean"` | ❌ W0 | ⬜ pending |
| 04-03-01 | 03 | 3 | MODAL-01, MODAL-05 | T-04-XSS | Rendered page has grouped launchers, one labelled dialog, escaped About text, and fallback controls | integration | `python -m pytest tests/test_filter_modal.py -x -k "launcher or dialog or fallback or lookahead"` | ❌ W0 | ⬜ pending |
| 04-03-02 | 03 | 3 | MODAL-06 | T-04-INTEGRITY | Commit hooks write canonical controls; cancel hooks do not mutate them | rendered contract | `python -m pytest tests/test_filter_modal.py -x -k "commit or cancel"` | ❌ W0 | ⬜ pending |
| 04-04-01 | 04 | 4 | MODAL-03 | T-04-INTEGRITY | Numeric shell exposes two handles, synchronized BETWEEN inputs, validation, and chart/list hooks | rendered contract | `python -m pytest tests/test_filter_modal.py -x -k "range or chart"` | ❌ W0 | ⬜ pending |
| 04-04-02 | 04 | 4 | MODAL-04 | T-04-XSS | Value table exposes safe search/sort and correct multi/single-selection semantics | rendered contract | `python -m pytest tests/test_filter_modal.py -x -k "table or categorical or boolean"` | ❌ W0 | ⬜ pending |
| 04-04-03 | 04 | 4 | MODAL-02, MODAL-06 | T-04-RACE | Script includes debounce, abort, generation guard, retry, and last-success behavior | source contract | `python -m pytest tests/test_filter_modal.py -x -k "debounce or stale or retry"` | ❌ W0 | ⬜ pending |

*Status: ⬜ pending · ✅ green · ❌ red · ⚠️ flaky*

---

## Wave 0 Requirements

- [ ] `tests/test_filter_modal.py` — focused metadata, parser, aggregation, endpoint, rendering, and serialization coverage for MODAL-01 through MODAL-06
- [ ] Deterministic `GameRecord`/feature fixtures in that file or existing shared fixtures
- [ ] No framework installation or test configuration change is required

---

## Manual-Only Verifications

| Behavior | Requirement | Why Manual | Test Instructions |
|----------|-------------|------------|-------------------|
| Keyboard-only dialog lifecycle and focus restoration | MODAL-01, MODAL-06 | Flask rendered tests cannot observe browser focus | Open from sidebar and active sentence; tab controls; sort table; press Escape; verify discard and launcher focus restoration |
| Slider dragging and synchronized exact inputs | MODAL-03 | No JavaScript/browser unit harness exists and adding one is out of scope | Drag each handle, edit each number input, verify no crossing and matching candidate metrics |
| Request race, loading, error, and Retry states | MODAL-02, MODAL-06 | Requires browser timing and forced endpoint failure | Trigger rapid changes, force one failed request, verify stale response is ignored, last success remains, Retry recovers |
| Narrow-screen layout and table overflow | MODAL-03, MODAL-04, MODAL-05 | Visual/responsive behavior is not provable through Flask test client | Resize to a narrow viewport; verify About stacks below controls, actions remain reachable, and table scrolls without page overflow |

---

## Validation Sign-Off

- [ ] All tasks have `<automated>` verify or Wave 0 dependencies
- [ ] Sampling continuity: no 3 consecutive tasks without automated verify
- [ ] Wave 0 covers all MISSING references
- [ ] No watch-mode flags
- [ ] Focused feedback latency is under 10 seconds
- [ ] `nyquist_compliant: true` set in frontmatter

**Approval:** pending

---
phase: 1
slug: system-editor-main-page
# status lifecycle: draft (seeded by plan-phase) → validated (set by validate-phase §6)
# audit-milestone §5.5 distinguishes NOT-VALIDATED (draft) from PARTIAL (validated + nyquist_compliant: false) (#2117)
status: draft
nyquist_compliant: false
wave_0_complete: false
created: 2026-07-16
---

# Phase 1 — Validation Strategy

> Per-phase validation contract for feedback sampling during execution.

---

## Test Infrastructure

| Property | Value |
|----------|-------|
| **Framework** | pytest (via project `.venv`; version not pinned in `requirements.txt`, already present and working — 94/94 passing) |
| **Config file** | `pytest.ini` (`testpaths = tests` — keeps collection out of vendored `cfbd-python/`) |
| **Quick run command** | `.venv/Scripts/python.exe -m pytest tests/test_web.py -q` |
| **Full suite command** | `.venv/Scripts/python.exe -m pytest -q` |
| **Estimated runtime** | ~2.3 seconds |

**Environment note:** always invoke via `.venv/Scripts/python.exe -m pytest` — bare `python -m pytest` resolves to a different global interpreter on this machine and fails on an unrelated package collision.

---

## Sampling Rate

- **After every task commit:** Run `.venv/Scripts/python.exe -m pytest tests/test_web.py -q` (or the more targeted file for the module just touched)
- **After every plan wave:** Run `.venv/Scripts/python.exe -m pytest -q`
- **Before `/gsd-verify-work`:** Full suite must be green
- **Max feedback latency:** ~3 seconds

---

## Per-Task Verification Map

| Task ID | Plan | Wave | Requirement | Threat Ref | Secure Behavior | Test Type | Automated Command | File Exists | Status |
|---------|------|------|-------------|------------|-----------------|-----------|-------------------|-------------|--------|
| 01-01-01 | 01 | 0 | EDIT-03 | — | N/A | unit | `.venv/Scripts/python.exe -m pytest tests/test_describe.py -q` | ❌ W0 | ⬜ pending |
| 01-0x-0x | TBD | 1+ | EDIT-01 | — | N/A | unit + integration | `.venv/Scripts/python.exe -m pytest tests/test_backtest.py tests/test_web.py -q` | ✅ | ⬜ pending |
| 01-0x-0x | TBD | 1+ | EDIT-02 | — | N/A | unit + integration | `.venv/Scripts/python.exe -m pytest tests/test_backtest.py tests/test_web.py -q` | ✅ | ⬜ pending |
| 01-0x-0x | TBD | 1+ | EDIT-04 | — | N/A | integration | `.venv/Scripts/python.exe -m pytest tests/test_web.py -q` | ✅ | ⬜ pending |
| 01-0x-0x | TBD | 1+ | EDIT-05 | T-01-01 | Theory text rendered via Jinja2 auto-escaping only — never `\|safe` | unit + integration | `.venv/Scripts/python.exe -m pytest tests/test_storage_systems.py tests/test_web.py -q` | ✅ | ⬜ pending |

*Status: ⬜ pending · ✅ green · ❌ red · ⚠️ flaky*

*Exact Task IDs/waves are assigned by the planner; this map will be refined once PLAN.md files exist.*

---

## Wave 0 Requirements

- [ ] `tests/test_describe.py` — new file, covers EDIT-03's `describe(system) -> list[dict]` pure function (mirrors the existing 1:1 module↔test-file pattern, e.g. `backtest.py` ↔ `test_backtest.py`)

*No new fixtures or framework install needed — existing `SAMPLE_GAMES_2023`/`SAMPLE_LINES_2023` (`sample_data.py`) and direct `GameRecord`/`SystemFilter` construction cover all new test needs; pytest is already present and passing.*

---

## Manual-Only Verifications

*None — all phase behaviors have automated verification. Visual/CSS restyling (chip layout, tab appearance) is verified via the standard browser-preview check during execution, not tracked here as a distinct manual gate.*

---

## Security Domain (ASVS L1)

### Applicable Categories

| ASVS Category | Applies | Standard Control |
|---------------|---------|-----------------|
| V2 Authentication | No | Single-user local tool, no auth layer anywhere in the app |
| V3 Session Management | No | No sessions/cookies; all state lives in the URL query string by design |
| V4 Access Control | No | No multi-user/role concept exists or is introduced |
| V5 Input Validation | **Yes** | New free-text `theory` field (EDIT-05): rely on Jinja2's default auto-escaping (ON by default; confirmed no `{% autoescape false %}` or `\|safe` anywhere in `templates/index.html`) to prevent stored-XSS via the theory textarea. Do not apply `\|safe` to rendered theory text. |
| V6 Cryptography | No | Not touched by this phase |

### Known Threat Patterns (T-01-xx)

| Ref | Pattern | STRIDE | Standard Mitigation |
|-----|---------|--------|---------------------|
| T-01-01 | Stored XSS via free-text `theory` field rendered later on the saved-system page | Tampering / Information Disclosure | Jinja2 auto-escaping (default, already relied upon everywhere else in `index.html`) — never bypass with `\|safe` for user-supplied text |
| T-01-02 | Query-string injection into remove/tab links (a crafted `?tab=<script>` or similar) | Tampering | Query-preserving href helper must build hrefs via `urllib.parse.urlencode`, which percent-encodes values — never string-interpolate raw `request.args` values into an href |

---

## Validation Sign-Off

- [ ] All tasks have `<automated>` verify or Wave 0 dependencies
- [ ] Sampling continuity: no 3 consecutive tasks without automated verify
- [ ] Wave 0 covers all MISSING references
- [ ] No watch-mode flags
- [ ] Feedback latency < 5s
- [ ] `nyquist_compliant: true` set in frontmatter

**Approval:** pending

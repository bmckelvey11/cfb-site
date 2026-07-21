---
phase: 5
slug: dashboard-current-matches
# status lifecycle: draft (seeded by plan-phase) → validated (set by validate-phase §6)
# audit-milestone §5.5 distinguishes NOT-VALIDATED (draft) from PARTIAL (validated + nyquist_compliant: false) (#2117)
status: draft
nyquist_compliant: false
wave_0_complete: false
created: 2026-07-20
---

# Phase 5 — Validation Strategy

> Per-phase validation contract for feedback sampling during execution.

---

## Test Infrastructure

| Property | Value |
|----------|-------|
| **Framework** | pytest (from `requirements.txt`) |
| **Config file** | `pytest.ini` (`testpaths=tests`, so the vendored client's own tests are excluded) |
| **Quick run command** | `.venv/Scripts/python.exe -m pytest tests/test_web.py tests/test_backtest.py -x` |
| **Full suite command** | `.venv/Scripts/python.exe -m pytest` |
| **Estimated runtime** | ~5 seconds |

**Interpreter constraint (hard):** the vendored `cfbd-python` client requires pydantic v1. System Python 3.14 carries pydantic 2.13.4 and fails to import `cfbd` with `PydanticUserError`. Every command and every pytest invocation in this phase must use `.venv/Scripts/python.exe`, never bare `python`.

---

## Sampling Rate

- **After every task commit:** Run `.venv/Scripts/python.exe -m pytest tests/test_web.py tests/test_backtest.py -x`
- **After every plan wave:** Run `.venv/Scripts/python.exe -m pytest`
- **Before `/gsd-verify-work`:** Full suite must be green
- **Max feedback latency:** 5 seconds

---

## Per-Task Verification Map

| Task ID | Plan | Wave | Requirement | Threat Ref | Secure Behavior | Test Type | Automated Command | File Exists | Status |
|---------|------|------|-------------|------------|-----------------|-----------|-------------------|-------------|--------|
| 5-01-01 | 01 | 1 | DASH-03 | T-05-03 | Offseason resolution terminates and writes a valid empty file instead of crashing or looping | unit | `.venv/Scripts/python.exe -m pytest tests/test_upcoming.py -x` | ❌ created by this task | ⬜ pending |
| 5-01-02 | 01 | 1 | DASH-03 | T-05-01 / T-05-05 | Token never persisted or printed; `games.csv` never written | unit | `.venv/Scripts/python.exe -m pytest tests/test_upcoming.py -x` | ✅ after 5-01-01 | ⬜ pending |
| 5-01-03 | 01 | 1 | DASH-03 | T-05-05 | CLI test asserts `games.csv` is not created by the upcoming command | unit | `.venv/Scripts/python.exe -m pytest tests/test_cli.py tests/test_upcoming.py -x` | ✅ exists | ⬜ pending |
| 5-02-01 | 02 | 1 | DASH-01 / DASH-03 | T-05-06 | No placeholder scores introduced; unplayed games never reach a grading function | unit | `.venv/Scripts/python.exe -m pytest tests/test_backtest.py -x` | ✅ exists | ⬜ pending |
| 5-02-02 | 02 | 1 | DASH-01 / DASH-03 | T-05-07 / T-05-08 | Default preserves all four call sites; complete existing suite passes with zero expectation edits | unit | `.venv/Scripts/python.exe -m pytest` | ✅ exists | ⬜ pending |
| 5-03-01 | 03 | 1 | DASH-01 | T-05-11 | `/?tab=examples` does not redirect; redirect target is a fixed internal endpoint | unit | `.venv/Scripts/python.exe -m pytest tests/test_web.py -x` | ✅ exists | ⬜ pending |
| 5-03-02 | 03 | 1 | DASH-01 | T-05-09 / T-05-10 / T-05-13 | Names and theory escaped; tab and timeframe normalized to a known set; missing `games.csv` degrades | unit | `.venv/Scripts/python.exe -m pytest tests/test_web.py tests/test_filter_modal.py tests/test_web_features.py tests/test_web_compare.py -x` | ✅ exists | ⬜ pending |
| 5-03-03 | 03 | 1 | DASH-01 | T-05-12 | One backtest per system; per-season figures derived, cache keyed on data-file identity | unit | `.venv/Scripts/python.exe -m pytest tests/test_web.py -x -k "sparkline or timeframe or dashboard"` | ✅ exists | ⬜ pending |
| 5-04-01 | 04 | 2 | DASH-03 | T-05-14 / T-05-15 | Historical `features.json` byte-identical; unplayed games do not contaminate each other | unit | `.venv/Scripts/python.exe -m pytest tests/test_upcoming.py tests/test_enrich.py -x` | ✅ exists | ⬜ pending |
| 5-04-02 | 04 | 2 | DASH-03 | T-05-16 | No placeholder or default substituted for a null feature value | unit | `.venv/Scripts/python.exe -m pytest tests/test_upcoming.py tests/test_enrich.py tests/test_running_stats.py -x` | ✅ exists | ⬜ pending |
| 5-05-01 | 05 | 2 | DASH-02 | T-05-18 / T-05-20 | Traversal-shaped name rejected on both loader and copy paths; bundled file bytes unchanged after copy | unit | `.venv/Scripts/python.exe -m pytest tests/test_storage.py tests/test_web.py -x -k example` | ✅ exists | ⬜ pending |
| 5-05-02 | 05 | 2 | DASH-02 | T-05-19 / T-05-21 / T-05-22 | Example names and theory escaped; no provider, weather, or season-to-date filter on any example | unit | `.venv/Scripts/python.exe -m pytest tests/test_storage.py tests/test_web.py -x` | ✅ exists | ⬜ pending |
| 5-06-01 | 06 | 3 | DASH-03 | T-05-23 / T-05-25 | Fade inversion asserted; missing upcoming file renders documented state without raising | unit | `.venv/Scripts/python.exe -m pytest tests/test_web.py -x -k "current_matches or play_text or offseason or missing_upcoming"` | ✅ exists | ⬜ pending |
| 5-06-02 | 06 | 3 | DASH-03 | T-05-23 / T-05-26 / T-05-27 | Play text matches grading normalization; no network call in a request; no second matcher | unit | `.venv/Scripts/python.exe -m pytest tests/test_web.py -x -k "current_matches or play_text"` | ✅ exists | ⬜ pending |
| 5-06-03 | 06 | 3 | DASH-03 | T-05-24 / T-05-28 | All values escaped; timestamp and fallback week label always rendered | unit | `.venv/Scripts/python.exe -m pytest tests/test_web.py -x` | ✅ exists | ⬜ pending |

*Status: ⬜ pending · ✅ green · ❌ red · ⚠️ flaky*

---

## Wave 0 Requirements

Wave 0 is folded into the first task of each plan (each plan opens with a RED test task) rather than run as a separate wave, because the test infrastructure already exists and only two new files are needed.

- [ ] `tests/test_upcoming.py` — new file; fake-CFBD fixture (calendar + games + lines, with `completed=False` rows and timezone-aware datetimes) and coverage for DASH-03 week resolution. Created by task 5-01-01.
- [ ] Re-point every root-path call site in `tests/test_web.py`, `tests/test_filter_modal.py`, and `tests/test_web_features.py` to `/system`. This MUST land in the same plan as the route move (5-03-01 then 5-03-02) — re-pointing in an earlier wave turns the suite red against a `/system` that does not yet exist. `tests/test_web_compare.py` only exercises `/compare` and needs no change; confirm with the enumerating grep in 5-03-01.
- [ ] No framework install needed — pytest and `pytest.ini` are already configured.

**Correction to 05-RESEARCH.md:** research stated 18 root-path call sites in `tests/`. The actual count is materially higher and spans three files. Use the enumerating grep in task 5-03-01 as the authority, not the research figure.

**Correction to 05-RESEARCH.md:** research listed `tests/test_running_stats.py` as a Wave 0 gap. That file already exists; extend it rather than creating it.

---

## Manual-Only Verifications

| Behavior | Requirement | Why Manual | Test Instructions |
|----------|-------------|------------|-------------------|
| Entering-game season-to-date values are non-null for a real mid-season upcoming game | DASH-03 | The 2026 season has no completed games until late August, so no fixture-free run can exercise the populated in-season path. Automated coverage uses the injected fake; this confirms it against live data once the season starts. | Run `.venv/Scripts/python.exe -m cfb_system_maker upcoming --data-dir data` in a real week ≥ 2, then confirm a known upcoming game has non-null entering-game games-played for both teams in `data/processed/upcoming_features.json`. |
| Live in-season Current Matches panel renders populated rows rather than the fallback state | DASH-03 | Depends on books having posted lines for a week in progress; not reproducible before the season opens. | Run the upcoming command in-season, load `/`, and confirm the panel shows the current week with no amber fallback notice. |
| Long system names and many-filter systems do not break dashboard layout | DASH-01 | Visual wrapping behavior; the UI contract marks this a backstop check. | Save a system with a very long name and one with six or more filters, then load `/` and confirm the System and Details cells wrap and the page does not scroll sideways. |

---

## Validation Sign-Off

- [ ] All tasks have `<automated>` verify or Wave 0 dependencies
- [ ] Sampling continuity: no 3 consecutive tasks without automated verify
- [ ] Wave 0 covers all MISSING references
- [ ] No watch-mode flags
- [ ] Feedback latency < 5s
- [ ] `nyquist_compliant: true` set in frontmatter

Every task across all six plans carries an `<automated>` verify command. No plan has three consecutive tasks without one. No watch-mode flags are used. All commands complete in roughly five seconds.

**Approval:** pending

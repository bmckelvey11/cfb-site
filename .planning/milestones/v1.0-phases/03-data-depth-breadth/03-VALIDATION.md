---
phase: 03
slug: data-depth-breadth
# status lifecycle: draft (seeded by plan-phase) → validated (set by validate-phase §6)
# audit-milestone §5.5 distinguishes NOT-VALIDATED (draft) from PARTIAL (validated + nyquist_compliant: false) (#2117)
status: draft
nyquist_compliant: false
wave_0_complete: false
created: 2026-07-17
---

# Phase 03 — Validation Strategy

> Per-phase validation contract for feedback sampling during execution.
> Substance derives from `03-RESEARCH.md` §"Validation Architecture" — the no-lookahead
> invariants are the load-bearing correctness properties for this phase.

---

## Test Infrastructure

| Property | Value |
|----------|-------|
| **Framework** | pytest (per `pytest.ini`, `testpaths=tests`) |
| **Config file** | `pytest.ini` |
| **Quick run command** | `python -m pytest tests/test_running_stats.py` |
| **Full suite command** | `python -m pytest` |
| **Estimated runtime** | ~15–30 seconds (network-free; existing suite) |

---

## Sampling Rate

- **After every task commit:** Run `python -m pytest tests/test_running_stats.py` (plus the task's own test file)
- **After every plan wave:** Run `python -m pytest`
- **Before `/gsd-verify-work`:** Full suite must be green
- **Max feedback latency:** 30 seconds

---

## Per-Task Verification Map

*Seeded by plan-phase; completed once PLAN.md task IDs exist. Every DATA-02 registry
feature MUST have a construct-`GameRecord`-and-assert test proving its entering-game /
no-lookahead behavior (mirror `tests/test_running_stats.py`).*

| Task ID | Plan | Wave | Requirement | Threat Ref | Secure Behavior | Test Type | Automated Command | File Exists | Status |
|---------|------|------|-------------|------------|-----------------|-----------|-------------------|-------------|--------|
| {N}-01-01 | 01 | 1 | DATA-{XX} | — | no-lookahead invariant holds | unit | `python -m pytest tests/...` | ✅ / ❌ W0 | ⬜ pending |

*Status: ⬜ pending · ✅ green · ❌ red · ⚠️ flaky*

---

## Key Correctness Properties (from RESEARCH §Validation Architecture)

- **No-lookahead invariant (highest risk):** every to-date feature (D-03) computed from
  *strictly-prior* same-season games only — first game of a season → `games_played=0`,
  averages/percentages `None`. Never fold a game's own result into its own features.
- **Preseason features (D-04):** talent/recruiting values are constant within a season
  (set before it) — assert they don't shift game-to-game.
- **Line-coverage floor (DATA-01):** 2012 (games, no usable lines) contributes **0** rows;
  the floor season (2013) contributes non-empty results.
- **`registry_version()` change (D-07):** adding registry rows changes the sidecar version;
  the stale-sidecar warning is expected until `enrich` re-runs.

---

## Wave 0 Requirements

- [ ] Test files for new DATA-02 features (one per feature group, mirroring `tests/test_running_stats.py`)

*Existing pytest infrastructure covers the framework; no install needed.*

---

## Manual-Only Verifications

| Behavior | Requirement | Why Manual | Test Instructions |
|----------|-------------|------------|-------------------|
| Live CFBD line-coverage probe result | DATA-01 | Requires network + `cfbd-python/` clone + API token | Run the probe sweep; confirm earliest usable-line season |

---

## Validation Sign-Off

- [ ] All tasks have `<automated>` verify or Wave 0 dependencies
- [ ] Sampling continuity: no 3 consecutive tasks without automated verify
- [ ] Wave 0 covers all MISSING references
- [ ] No watch-mode flags
- [ ] Feedback latency < 30s
- [ ] `nyquist_compliant: true` set in frontmatter

**Approval:** pending

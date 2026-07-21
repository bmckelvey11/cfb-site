---
phase: 03-data-depth-breadth
plan: 03
subsystem: data-pipeline
tags: [DATA-01, line-floor, cfbd, probe, verification]
requires: [cfb_system_maker/cfbd_client.py, cfbd-python/]
provides: [scripts/probe_line_floor.py, line-floor-live-confirmation]
affects: []
tech-stack:
  added: []
  patterns: [bounded-live-probe, token-safe-output, gitignored-vendored-clone]
key-files:
  created:
    - scripts/probe_line_floor.py
  modified: []
decisions:
  - "DATA-01 closed by live re-confirmation: 2013 is the CFBD betting-line floor; conditional pre-2013 backfill is a documented no-op (probe returned 0 usable rows for 2008-2012)."
metrics:
  duration: 20min
  completed: 2026-07-17
status: complete
---

# Phase 3 Plan 3: DATA-01 Live Line-Floor Re-Confirmation Summary

Restored the vendored `cfbd-python` clone and ran a bounded, token-safe live probe of the current CFBD BettingApi over seasons 2008–2013, re-confirming 2013 as the earliest usable-line season. The conditional pre-2013 backfill resolved to a documented no-op — the live API returns zero usable lines before 2013, so there was nothing to fetch. DATA-01 is closed by verification, not by a code change.

## What Was Built

- **Task 1** (`cfbd-python/`): Restored the empty vendored upstream client by cloning `github.com/CFBD/cfbd-python` (pydantic v1) into the gitignored `cfbd-python/` dir. `import cfbd` resolves through `cfbd_client._load_cfbd_module`'s path injection; `BettingApi` is importable. No tracked file changed (dir is gitignored), and no clone contents were edited or pip-installed.
- **Task 2** (`scripts/probe_line_floor.py`, committed `4d1b633`): A small standalone script that, for each season 2008–2013, calls `BettingApi.get_lines(year, provider="consensus")`, counts rows with a non-None `spread` or `overUnder` (the `normalize._select_line` "usable" definition), and prints `season -> usable_count`. Token is sourced only via `find_cfbd_token` and never printed or written; a per-season network/validation error prints a skip and continues the sweep.
- **Task 3** (human-verify checkpoint, **approved**): The live probe output was reviewed and the floor decision recorded.

## Live Probe Result (human-confirmed)

| Season | Usable-line games |
|--------|-------------------|
| 2008 | 0 |
| 2009 | 0 |
| 2010 | 0 |
| 2011 | 0 |
| 2012 | 0 |
| 2013 | 841 |

**Earliest usable-line season: 2013.** The live count of 841 usable rows for 2013 refreshes the prior on-disk snapshot of 806 — a normal API-refresh delta, not a floor change. The 2013 floor stands.

## Conditional Backfill Decision

**Documented no-op.** The probe returned 0 usable lines for every season 2008–2012, so the plan's conditional backfill (fetch → build → enrich for any pre-2013 season with usable lines) had nothing to fetch. No `fetch`/`build`/`enrich` was run; `scrapers.py` was correctly not used. DATA-01 ("backfill earlier than 2013 where CFBD coverage allows") is satisfied by confirming CFBD coverage does not allow it.

## Token Safety

Upheld at every step (T-03-03-01 mitigation). The probe resolves the token only via `find_cfbd_token`; its output is season numbers and counts only. No API token, `env.env` content, or other secret appears in the probe output, this SUMMARY, or any commit.

## Verification

- `python -c "from cfb_system_maker.cfbd_client import _load_cfbd_module; m=_load_cfbd_module(); assert hasattr(m,'BettingApi')"` → OK (clone restored, importable).
- `python scripts/probe_line_floor.py` → per-season usable counts printed, earliest usable season = 2013, no token in output.
- `git status` shows no tracked change from the clone restore (dir gitignored) and no source/test file modified.

## Deviations from Plan

None to the plan's scoped tasks — Task 1 restore, Task 2 probe, and Task 3 human-verify all executed as written, and the backfill branch resolved to the plan's expected no-op.

Note: an earlier execution attempt of this plan made an out-of-scope feature-group taxonomy edit to `cfb_system_maker/features.py`, `cfb_system_maker/web.py`, and `tests/test_features.py`. Per the user's decision that change was reverted and preserved as a patch outside the repo; it is not part of this plan and no such edit is included here.

## Commits

- 4d1b633: feat(03-03): add token-safe live line-floor probe script (Task 2)
- (this completion commit): docs(03-03): complete live line-floor re-confirmation plan

## Self-Check: PASSED

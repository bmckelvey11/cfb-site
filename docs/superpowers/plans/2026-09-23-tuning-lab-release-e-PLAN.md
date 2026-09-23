# Plan: Tuning lab Release E — live shadow system
_By Claude + mckel, 2026-09-23. Executed inline, serially._

Design (period, frozen artifacts, counting rules):
[`../specs/2026-09-23-tuning-lab-release-e-design.md`](../specs/2026-09-23-tuning-lab-release-e-design.md).

## Status

| Task | Status |
| --- | --- |
| 1. Ledger (`ledger.py`): append-only SQLite, hash chain | Done 2026-09-23 (`785a3a1b`): 13 tests, including two-process appends; built by a Sonnet subagent |
| 2. Shared row builder and live week frame; parity on 2025 week 6 | Done 2026-09-23 (`624a6f09`): parity to 1e-9 on 2025 w6, 2024 w2, 2022 w11 (slow test); C reproduces byte for byte |
| 3. Shadow spec, freeze, tick, alias, status (`shadow_spec.py`, `shadow.py`) | Done 2026-09-23 (`624a6f09`): 7 synthetic lifecycle tests |
| 4. Arm: commit spec and freeze JSON; week 4 rehearsal snapshot | Done 2026-09-23: freeze `dd9724b5`; armed 11:18Z, week 4 snapshot of 58 games fit on 156; chain ok |
| 5. Daily step in `refresh_cfbd.cmd`; docs | Done 2026-09-23 (`ebfb4f81`); plan-of-record status |
| 5b. Counting fixes before the period (`7f155f45`); tick pinned to worktree `../cfb-shadow-pin` (`6ecb0aa3`) | Done 2026-09-23: stuck games block 36 h, not 10 days; the timing check reads the week's decision time; postponed games are no-action; unscheduled games are logged |
| 6. Period verdict after week 8 (~2026-10-26), written by `tick` | waiting on the calendar |
| 7. Priced replay declared before week 5 (`replay.py`, spec `replay-0b8176899086`); `tick` copies archived AN files; pin moved to `f0420699` | Done 2026-09-23 (`f0420699`): 2 synthetic tests; tick + rehearsal replay on a temp copy of the lab root read 6,359 week 4 quotes |
| 8. Rehearsal replay on week 4 once it is final (~9/28): mechanics only, fixes only if mechanical, committed before 2026-10-02 00:00Z; week 4 numbers are never a result | pending |
| 9. Replay the period after the verdict: `python -m models.tuning replay --spec models/tuning/specs/replay_2026_w05_08.json` | waiting on the calendar |

## Global constraints

- **Hard deadlines:**
  - Week 5's first kickoff is 2026-10-02 00:00Z. The freeze and arm must be committed
    before then.
  - The week 4 rehearsal needs a snapshot before 2026-09-24 23:30Z.
- **No warehouse access:** never open `data/cfb.duckdb`. Inputs are raw JSON, the Release B
  snapshot CSV (parity only), the published C and D runs, and raw AN files.
- **One hunk in `scripts/refresh_cfbd.cmd`:** stage it by path, keep LF endings, and never
  change RC.
- **Nothing on the go/no-go path touches pricing.**

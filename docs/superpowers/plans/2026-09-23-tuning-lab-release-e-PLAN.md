# Plan: Tuning lab Release E — live shadow system
_By Claude + mckel, 2026-09-23. Executed inline, serially._

Design (period, frozen artifacts, counting rules):
[`../specs/2026-09-23-tuning-lab-release-e-design.md`](../specs/2026-09-23-tuning-lab-release-e-design.md).

## Status

| Task | Status |
| --- | --- |
| 1. Ledger (`ledger.py`): append-only SQLite, hash chain | pending |
| 2. Shared row builder and live week frame; parity on 2025 week 6 | pending |
| 3. Shadow spec, freeze, tick, alias, status (`shadow_spec.py`, `shadow.py`) | pending |
| 4. Arm: commit spec and freeze JSON; week 4 rehearsal snapshot | pending |
| 5. Daily step in `refresh_cfbd.cmd`; docs | pending |
| 6. Period verdict after week 8 (~2026-10-26), written by `tick` | waiting on the calendar |

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

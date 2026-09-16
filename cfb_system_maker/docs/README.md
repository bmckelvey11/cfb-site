# `cfb_system_maker/docs` index

App-side documentation for the system maker: the Flask app, the backtest CLI, the scrapers,
and the loader that fills the warehouse. Unit rules live in [`../CLAUDE.md`](../CLAUDE.md).

**The warehouse's own design docs are not here** — they are shared across units and live in
root [`docs/`](../../docs/README.md) (`duckdb-warehouse-plan.md`, `duckdb-core-ddl.md`,
`data-coverage.md`, the `pff-*` and `oddsapi-*` clusters, and the dated warehouse
investigations). This directory holds what is specific to *this* unit's code.

## Living reference

| Doc | What it is |
| --- | --- |
| [data-flow-guide.md](data-flow-guide.md) | **Read this before touching `data/` or the loader.** Sources → warehouse → consumers, end to end. Explicitly a living document: when a step stops matching the code, fix one or the other in the same commit. Last verified 2026-09-11. |

## Audits and incidents

| Doc | Question, and status |
| --- | --- |
| [data-audit-2026-09-11.md](data-audit-2026-09-11.md) | Data folder and warehouse audit. Reproduce with `python scripts/audit_data_hygiene.py --out <report.md> --json <findings.json>` (read-only; `--strict` exits 1 on any FAIL). |
| [refresh-break-2026-09-11.md](refresh-break-2026-09-11.md) | Why the daily refresh broke — `_merge_game_lines` hard-depended on an optional column. **Closed**; proximate cause fixed and verified in production, upstream OOM tracked separately. |
| [warehouse-catalog-regeneration-2026-09-16.md](warehouse-catalog-regeneration-2026-09-16.md) | What changed in the warehouse since the catalog was last hand-built on 2026-08-29, and whether it can be regenerated rather than re-written. |

## Shipped UI and feature work

| Doc | What it delivered |
| --- | --- |
| [editor-usability-2026-09-10.md](editor-usability-2026-09-10.md) | The five priority findings from the Impeccable review of the System Maker editor, plus accessibility and copy fixes. |
| [pregame-filter-migration-2026-09-10.md](pregame-filter-migration-2026-09-10.md) | Removing Attendance and replacing the Result Lookahead filters with pre-kickoff equivalents. Carries the definitions and limits for the replacements. |

## Note

`../CLAUDE.md` cites root `docs/` in nine places and this directory in one
(`pregame-filter-migration-2026-09-10.md`). Pointing it at this index instead of at
individual files is the obvious follow-up; not done here, because that file is the unit's
instruction surface and editing it is a separate decision.

Indexed 2026-09-16. See [root `docs/README.md`](../../docs/README.md) for the
repo-wide docs pass this belongs to.

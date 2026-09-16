# MotherDuck Dive: CFB Warehouse Explorer — 2026-09-16

## Question

Can the full `md:cfb` warehouse be browsed interactively — every schema, table,
row count and column — from a saved MotherDuck Dive, and what does the mirror
actually contain right now?

## Method

- Explored `md:cfb` through the MotherDuck MCP `query` tool against
  `duckdb_tables()`, `duckdb_columns()`, `core.fact_game` and
  `meta.warehouse_version`.
- Probed whether `duckdb_tables()` / `duckdb_columns()` resolve inside the Dive
  WASM runtime (they do — the probe returned all 249 tables with populated
  `estimated_size`). `information_schema` is **not** available on MotherDuck, so
  the `duckdb_*` catalog functions are the only metadata route.
- Built and iterated the component under a local Vite preview
  (`.dive-preview/`), then saved it.

Data: `md:cfb`, the MotherDuck mirror, as promoted **2026-09-01**
(`meta.warehouse_version.promoted_at`). Seasons 1992–2026 in `core.fact_game`.

## Numbers

| Measure | Value |
| --- | --- |
| Tables | 249 (`raw` 120, `stg` 119, `core` 8, `meta` 2) |
| Rows | 29,887,020 |
| Columns | 2,827 |
| Seasons in `core.fact_game` | 1992–2026, 54,264 games |
| Largest table | `stg.gamePlayerStat`, 5.54M rows |

Betting-line coverage in `core.fact_game` starts in 2013 (0 lined games before
that) and runs 52–57% of scheduled games from 2013 to 2025. The 2026 season in
the mirror has 3,676 scheduled games but only **126 completed** and 214 lined —
the mirror was promoted 2026-09-01, so it is ~2.5 weeks behind the live season.

`raw` by vendor: CFBD 116 tables / 14.6M rows, ActionNetwork 3 / 212K, PFF 1 / 1
row (a stub). Massey and Odds API tables are not in the mirror at all.

## What this does not support

- It is not a data-quality audit. Row counts come from DuckDB catalog
  `estimated_size`; nothing here validates content, joins, or null rates.
- The vendor split is a table-name heuristic on the `raw` schema, not a
  provenance ledger. "CFBD" is the fallback bucket.
- Nothing here describes the **local** `cfb.duckdb`, which is the source of
  truth. Mirror gaps (PFF, Massey, Odds API, 2026 results) mean the mirror is
  behind local, not that local lacks the data. Re-push with
  `scripts/refresh_cfbd.py` → MotherDuck promote before drawing conclusions from
  recent seasons.

## Reproduce

- Dive: **CFB Warehouse Explorer** —
  https://app.motherduck.com/dives/cfb-warehouse-explorer-20245169-a7de-4590-8e6e-b4fc97413d36
  (queries `md:cfb` live; the subtitle renders `promoted_at` so staleness is
  visible on every open).
- Source: [.dive-preview/src/dive.tsx](../.dive-preview/src/dive.tsx). Preview it
  with `npm --prefix .dive-preview run dev` (needs
  `.dive-preview/.env` → `VITE_MOTHERDUCK_TOKEN`, git-ignored), or via the
  "Dive Preview" entry in `.claude/launch.json`.

## Note for future dives

Stacked `<Bar stackId>` renders at the wrong scale under recharts 3.7 in this
runtime (segments drawn at ~28% of correct height while the axis domain is
right). Single-series bars and `ComposedChart` bar + line are correct. The dive
uses bar (games) + right-axis line (line coverage %) for that reason.

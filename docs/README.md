# Root `docs/` index

**Scope rule** (from [`repo-restructure-plan.md`](repo-restructure-plan.md), executed
2026-08-31): root `docs/` holds **shared only: warehouse, design-system, data-coverage**.
Unit-specific docs live in that unit's `docs/`:

| Unit | Docs home |
| --- | --- |
| System maker, Flask app, scrapers, warehouse *(app-side)* | [`cfb_system_maker/docs/`](../cfb_system_maker/docs/) |
| Over-zero models, floor-bias research | [`models/over_zero/docs/`](../models/over_zero/docs/) |
| Spread forecast research | [`research/spread/docs/`](../research/spread/docs/) |
| Totals research | [`research/totals/docs/`](../research/totals/docs/) |
| Bankroll, staking, combined-strategy projection | [`research/bankroll/docs/`](../research/bankroll/docs/) |
| Superseded, never cited as current | [`archive/`](../archive/README.md) |

Cross-unit reference: [`methods.md`](methods.md) holds the formulas and assumptions behind every record and projection; [`../CONTEXT.md`](../CONTEXT.md) holds the vocabulary and points here.

The warehouse/ingest cluster below is **correctly** at root: 33 files under `scripts/`,
`cfb_system_maker/`, and `tests/` cite a doc that lives here, 16 of them the warehouse
cluster specifically, and these docs describe the shared `cfb.duckdb` warehouse rather
than any one unit.

---

## Warehouse — design and contracts

| Doc | What it answers |
| --- | --- |
| [duckdb-warehouse-plan.md](duckdb-warehouse-plan.md) | The warehouse plan of record |
| [duckdb-rebuild-spec.md](duckdb-rebuild-spec.md) | Rebuild design spec |
| [duckdb-core-ddl.md](duckdb-core-ddl.md) | `core` DDL contract (Phase 1) |
| [data-coverage.md](data-coverage.md) | CFBD data coverage — what we have and don't |
| [raw-stg-classification.md](raw-stg-classification.md) | raw ↔ stg classification |
| [schema-audit.md](schema-audit.md) | REST ↔ GraphQL join map |
| [graphql-schema-draft.md](graphql-schema-draft.md) | Draft DB schema, REST + GraphQL |
| [adr/](adr/) | 3 ADRs: merges land in `core`; `stg_gql` separation; one `stg` schema |

## Warehouse — dated investigations (2026-09)

Each answers one question against the live warehouse; keep for provenance.

| Doc | Question |
| --- | --- |
| [duckdb-audit-remediation-plan.md](duckdb-audit-remediation-plan.md) | Remediation plan off the 2026-09-02 audit |
| [warehouse-round5-rereview-2026-09-09.md](warehouse-round5-rereview-2026-09-09.md) | The one open item from the Codex loop |
| [core-merge-bucket-c-2026-09-10.md](core-merge-bucket-c-2026-09-10.md) | Merging the last four GraphQL sources into `core` |
| [gql-relation-keys-2026-09-10.md](gql-relation-keys-2026-09-10.md) | Relation keys for `coachSeason` / `teamTalent` |
| [stg-gql-collapse-2026-09-10.md](stg-gql-collapse-2026-09-10.md) | Collapsing `stg_gql` into `stg` |
| [warehouse-containment-remeasure-2026-09-10.md](warehouse-containment-remeasure-2026-09-10.md) | Containment after the relation-key repair |
| [warehouse-drop-superseded-2026-09-10.md](warehouse-drop-superseded-2026-09-10.md) | Dropping Bucket A REST sides and 7 dead columns |
| [team-name-mapping-2026-09-10.md](team-name-mapping-2026-09-10.md) | Do the four vendor name maps need consolidating? |
| [graphql-dump-staleness-2026-09-11.md](graphql-dump-staleness-2026-09-11.md) | How stale are the GraphQL dumps? |
| [cfb-warehouse-dive-2026-09-16.md](cfb-warehouse-dive-2026-09-16.md) | Can `md:cfb` be browsed from a saved MotherDuck Dive, and what does the mirror hold? |

## Odds and lines ingest

| Doc | What it answers |
| --- | --- |
| [oddsapi-ingest.md](oddsapi-ingest.md) | the-odds-api.com ingest (the runbook) |
| [oddsapi-game-join-2026-09-10.md](oddsapi-game-join-2026-09-10.md) | Do events land on exactly one `stg.games` row? |
| [oddsapi-team-name-join-2026-09-10.md](oddsapi-team-name-join-2026-09-10.md) | Can the-odds-api names join the warehouse? |
| [oddspapi-security-check-2026-09-16.md](oddspapi-security-check-2026-09-16.md) | oddspapi.io integration security check |
| [odds-sources-an-vs-apis-2026-09-11.md](odds-sources-an-vs-apis-2026-09-11.md) | Do we still need the Action Network scrape? |
| [lines-provider-key-split-2026-09-10.md](lines-provider-key-split-2026-09-10.md) | One book, two names: the DraftKings key split |
| [lines-spread-sign-2026-09-10.md](lines-spread-sign-2026-09-10.md) | Does every book quote a home-relative spread? |
| [line-timing-collector.md](line-timing-collector.md) | Line-timing collector runbook |
| [data-line-floor.md](data-line-floor.md) | CFBD betting-line floor (earliest usable season) |
| [cfbd-lines-coverage-2026-09-17.md](cfbd-lines-coverage-2026-09-17.md) | How far back CFBD lines go (2013 is CFBD's floor) and which book posted each era |
| [pre-2013-lines-sources-2026-09-17.md](pre-2013-lines-sources-2026-09-17.md) | What fills lines before 2013: Prediction Tracker spreads already in-repo; totals still open |
| [sbr-ncaaf-lines-2026-09-17.md](sbr-ncaaf-lines-2026-09-17.md) | Pre-2013 totals and moneylines from the Sportsbook Reviews archive (2007–2012) |
| [ncaadata-csv-backfill-2026-09-17.md](ncaadata-csv-backfill-2026-09-17.md) | Can `NCAAData_1980-2020.csv` backfill lines? No — it has none |
| [median-line-2026-09-17.md](median-line-2026-09-17.md) | The system builder now grades against the median line across books, not one provider |

## PFF

| Doc | What it answers |
| --- | --- |
| [pff-cli.md](pff-cli.md) | PFF Developer API CLI — install, use, where it fits |
| [pff-endpoint-reference.md](pff-endpoint-reference.md) | PFF API endpoint reference (generated) |
| [pff-ingest-plan.md](pff-ingest-plan.md) | From scraped files to warehouse tables |
| [pff-warehouse-schema.md](pff-warehouse-schema.md) | 30 report shapes folded into 19 tables |
| [pff-methodology-research.md](pff-methodology-research.md) | What PFF's public methodology does and does not support |
| [research-prompts/pff-advanced-metrics.md](research-prompts/pff-advanced-metrics.md) | The prompt that produced the doc above |
| [pff-sample-schema.sql](pff-sample-schema.sql) | Sample DDL |
| [pff-scheme-inventory-2026-09-16.md](pff-scheme-inventory-2026-09-16.md) | Does PFF carry scheme labels? No — 21 scheme rates are computable instead |
| [pregame-feature-eligibility-2026-09-16.md](pregame-feature-eligibility-2026-09-16.md) | Which PFF and CFBD stats are usable pre-game (the grain decides, not the stat) |
| [pff-team-report-sample-georgia-2026.md](pff-team-report-sample-georgia-2026.md) | Sample rendered team report from the PFF API (Georgia, 2026) |

## CFBD source reference

| Doc | What it is |
| --- | --- |
| [cfbd-endpoint-field-reference.md](cfbd-endpoint-field-reference.md) | Generated by `scripts/gen_endpoint_field_reference.py` (+ `.pdf`) |
| [data-source-endpoint-inventory.csv](data-source-endpoint-inventory.csv) | Endpoint inventory |
| [data-fields.csv](data-fields.csv) | Field inventory |
| [cfb-warehouse-catalog.html](cfb-warehouse-catalog.html), [db-summary.html](db-summary.html) | Generated warehouse browsers |

## Betting analysis (cross-unit — no single owning model)

| Doc | What it answers |
| --- | --- |
| [bet-history-analysis-2023-2025.md](bet-history-analysis-2023-2025.md) | The 2023–2025 personal bet history |
| [clv-analysis.md](clv-analysis.md) | Do you beat the closing line? |
| [value-sources-beyond-the-close.md](value-sources-beyond-the-close.md) | Value other than beating the close |
| [under-bets-analysis.md](under-bets-analysis.md) | NCAAF unders — full analysis |
| [under-bets-summary.md](under-bets-summary.md) | NCAAF unders — summary |
| [under-team-stats-analysis.md](under-team-stats-analysis.md) | Team stats behind the unders |
| [stat-angles-retest.md](stat-angles-retest.md) | Pace, mismatch, and a full model |
| [coach-playstyle-analysis.md](coach-playstyle-analysis.md) | Coach playstyle clusters — and their limits |
| [seasonal-totals-backtest.md](seasonal-totals-backtest.md) | Seasonal totals effect, 13k games |
| [totals-model.md](totals-model.md), [totals-early-weeks.md](totals-early-weeks.md) | Totals model and early-season behaviour |
| [wind-orientation-totals.md](wind-orientation-totals.md) | Crosswind vs head/tail wind and scoring |
| [ppa-opponent-adjusted-ratings-2026-09-16.md](ppa-opponent-adjusted-ratings-2026-09-16.md) | Opponent-adjusted team PPA ratings early in the season (mixed-effects, v1.0) |
| [total-points-distribution-2026-09-17.md](total-points-distribution-2026-09-17.md) | How combined game totals are distributed and which exact totals spike (55, 41, 44); scoring is down ~5.7 pts since 2016 |
| [scoring-margin-distribution-2026-09-18.md](scoring-margin-distribution-2026-09-18.md) | How scoring margins are distributed; 3 and 7 take 18.5% of games between them; home-field advantage is flat at +4, not trending |
| [scoring-by-minute-2026-09-18.md](scoring-by-minute-2026-09-18.md) | When points land inside a quarter, split by game state and spread; Q4 min 15 ranges 0.37 (leading) to 3.00 (trailing), and the spread effect flips sign between Q1-Q3 and Q4 |

> **Caution on the unders docs:** per project memory, the 2023-25 `history.csv` unders are
> mostly Greenline flags, not independent picks. Pool them as prior evidence, never as a
> standalone baseline.

## App, product, and process

| Doc | What it is |
| --- | --- |
| [design-system.md](design-system.md) | Saturday Signal design system |
| [bet-labs-parity-plan.md](bet-labs-parity-plan.md) | Bet Labs parity plan |
| [betting-system-builder-implementation-plan.md](betting-system-builder-implementation-plan.md) | System builder implementation plan |
| [sports-insights-systems-combined-guide.md](sports-insights-systems-combined-guide.md) | Source material for the above two |
| [autostart-audit-2026-09-15.md](autostart-audit-2026-09-15.md) | Autostart / scheduled-task audit |
| [repo-restructure-plan.md](repo-restructure-plan.md) | The 2026-08-31 restructure (executed; sets this file's scope rule) |
| [methodology/todo-system.md](methodology/todo-system.md) | How `TODO.md` works |
| [intent/new-system-type-catalog.md](intent/new-system-type-catalog.md) | Intent: New System type catalog |
| [reminders.md](reminders.md) | Loose reminders (scratch-adjacent) |
| [models-organization-2026-09-16.md](models-organization-2026-09-16.md) | Plan for organizing `models/` and `research/`, and the safe sequence |
| [fetch-venv-2026-09-17.md](fetch-venv-2026-09-17.md) | Why CFBD fetches need `.venv-cfbd` (pydantic 2 breaks the vendored client) |
| [cfbdepth-scrape-2026-09-16.md](cfbdepth-scrape-2026-09-16.md) | What cfbdepth.com exposes and whether to scrape it (scope open) |
| [tv-grid-2026-09-17.md](tv-grid-2026-09-17.md) | Weekly TV grid (`scripts/tv_grid.py`): network rows × kickoff columns with median line, AP+Massey rank, forecast weather |
| [sql-course-perplexity-prompt-2026-09-16.md](sql-course-perplexity-prompt-2026-09-16.md) | The prompt that generated the SQL course on the warehouse |
| [sql-course-program-plan-2026-09-16.md](sql-course-program-plan-2026-09-16.md) | Plan to turn the SQL course into slides, a grading CLI, and progress tracking |
| [img/](img/) | Figures for the README and coach-playstyle doc |

## Not docs — tool state, do not treat as documentation

`superpowers/` (plans and specs written by the superpowers skill).

---

## Organization pass — 2026-09-16

**Question.** Root `docs/` had grown to 52 flat files with no index, and unit-owned docs
had re-accumulated there since the 2026-08-31 restructure. Which files are misfiled, and
which references are stale?

**Method.** Enumerated every `.md` outside vendored and tool trees (418 files), then
grepped every `docs/...` path literal out of `*.py`, `*.cmd`, `*.md`, `*.js`, `*.html` and
resolved each against the filesystem to separate live references from dangling ones. The
two counts in the header are: files under `scripts/`, `cfb_system_maker/`, and `tests/`
citing a path that resolves to a file in root `docs/` (33), and the subset of those citing
one of the 16 warehouse-cluster docs listed below (16 files). Unit-relative citations —
e.g. `docs/MODEL_GUIDE.md` from inside `models/over_zero/` — are excluded from both.

**What moved** (all were untracked, so plain `mv` then `git add`):

| From | To | Why |
| --- | --- | --- |
| `docs/FBS College Football Pregame Totals Betting System  Research Report.md` | `research/totals/docs/fbs-totals-system-research-report.md` | Totals-only; also had a double space in the filename |
| `docs/fbs-totals-frontier-models.md` / `.pdf` | `research/totals/docs/` | Totals-only |
| `docs/research-prompts/fbs-totals/` (16 files) | `research/totals/docs/research-prompts/fbs-totals/` | Totals-only |
| `docs/combined_cfbstats.md` | `docs/pff-methodology-research.md` | Stays at root (PFF is cross-cutting); the old name said nothing about the contents |
| `docs/figs/bias_bins.png` | *deleted* | Byte-identical duplicate of `models/over_zero/docs/figs/bias_bins.png`, written to root by `monitor/bias_bins.py` run from the wrong cwd |

Nothing cited any of the moved files.

**Stale references found and fixed.** The prior archive pass moved two docs into
`archive/docs/` and updated only some of their citations:

| File | Was | Now |
| --- | --- | --- |
| `tests/test_structure_inference.py:6` | `docs/duckdb-audit-2026-09-02.md` | `archive/docs/...` |
| `tests/test_catalog_resolution.py:4` | `docs/warehouse-schema-recommendation.md` | `archive/docs/...` |
| `cfb_system_maker/actionnetwork_client.py:40` | `research/spread/docs/prediction-tracker-model-eval.md` | `archive/spread-margin-era/...` |

These are provenance citations ("see §9 for why this number is what it is"), so pointing
at `archive/` is correct and matches the siblings that were already fixed
(`scripts/audit_duckdb.py`, `scripts/split_ingest_staging.py`,
`scripts/migrate_live_warehouse.py`).

**Known stale, deliberately not fixed.** `cfb_system_maker/duckdb_load.py` lines 1492 and
1810 carry the same two dead pointers, but that file has unrelated uncommitted work in it.
Fix those two comment lines the next time it is committed.

**Checked and found healthy.** Four paths look dangling to a naive grep but are not:
`docs/duckdb-audit-rerun.md` and `cfb_system_maker/docs/data-audit-rerun.md` are `--out`
targets the audit scripts write on demand; `research/totals/docs/x.md` is a placeholder
`--out` in a usage example; the `docs/MODEL_GUIDE.md` / `docs/ROI_HITRATE.md` /
`docs/backtest_bets.csv` family resolve correctly relative to `models/over_zero/`.

**One status question, raised here and since settled.** When this pass ran,
`research/totals/` was a docs-and-scripts tree with no unit `CLAUDE.md` and no row in root
`CLAUDE.md`'s units table, so the table above listed it as a docs home on navigational
grounds only. It was promoted to a real unit later the same day: it now has
[`research/totals/CLAUDE.md`](../research/totals/CLAUDE.md), an index at
[`research/totals/docs/README.md`](../research/totals/docs/README.md), and a units-table
row. Treat it as a unit.

**What this does *not* support.** No doc bodies were rewritten and no claims re-verified —
this was a move-and-index pass. The groupings above are navigational, not a statement that
any document is current. Dated investigation docs are provenance; where one contradicts a
later doc, the later one wins. Nothing was archived here: archiving requires evidence that
a doc is superseded, and that evidence was not gathered.

**Left alone on purpose.** `.planning/` (history, per root `CLAUDE.md`); root `PLAN.md` and
`PLAN-REVIEW-LOG.md` (owned by the claudex-loop); `AGENTS.md`, `CLAUDE.md`, `CONTEXT.md`,
`PRODUCT.md`, `README.md` (load-bearing at root); `models/over_zero/docs/cfbd-api/` (167
generated files); `superpowers/`, `.remember/`, `.solopreneur/`, `.impeccable/`,
`graphify-out/` (tool state); `SCRATCH.md`.

**Reproduce the reference scan:**

```bash
grep -rhoE 'docs/[A-Za-z0-9 _.-]+\.(md|csv|sql|pdf|html|png)' \
  --include=*.py --include=*.cmd --include=*.md \
  scripts cfb_system_maker tests research models \
  | sort -u | while read p; do [ -f "$p" ] || echo "MISSING: $p"; done
```

Paths printed as `MISSING` are either dangling or unit-relative — resolve them from the
citing file's unit root before concluding they are broken.

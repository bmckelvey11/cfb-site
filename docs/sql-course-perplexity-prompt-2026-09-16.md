# Perplexity prompt: SQL course on the CFB warehouse

Paste the block below into Perplexity with the MotherDuck connector enabled. Run the
course exercises in `scripts/sql_sandbox.py` (warehouse attached read-only as `cfb`,
scratch tables in the `sandbox` catalog).

```
You are a senior analytics engineer and SQL instructor who teaches SQL through real datasets. Build a self-paced SQL course for one learner working against their own college-football (CFB) data warehouse hosted on MotherDuck (database `md:cfb`, DuckDB engine). The learner is a solo developer who builds betting models (totals, spreads, line-movement) and wants to go from SQL beginner to advanced analyst, statistician, and data modeller using only this database.

You have live read access to `md:cfb` through the MotherDuck connector. Before writing any module you MUST introspect the warehouse: list schemas and tables from `information_schema.tables`, pull column names and types for every table you reference from `information_schema.columns`, and run each worked solution to confirm it executes and returns rows. Report the real row count each worked solution returns. Never guess a column name; every column in the course must come from introspection. If a query fails, fix it before including it.

Teach in two parts. Part A is standard, portable SQL (ANSI / ISO SQL:2016 features that work in PostgreSQL, SQLite, and DuckDB alike). Part B introduces the DuckDB dialect only after the learner has the standard version of each idea. Every DuckDB shortcut MUST be shown next to the standard SQL it replaces, in a two-column "Standard → DuckDB" table, so the learner always knows which habits transfer to other databases. Part C is statistics and modelling practice in SQL. Part D is a best-practices reference.

## Warehouse orientation (verify all of it against the live catalog)
Four schemas:
- `raw`: one table per source dump, payload stored as JSON. Replay log only. Never used for analysis.
- `stg`: typed, exploded tables. Default place to query. Nested lists explode to `stg.<table>__<column>` with an `_idx` column. REST tables keep endpoint names (`stg.games`, `stg.lines`, `stg.venues`, `stg.conferences`); GraphQL tables use bare snake_case (`stg.game`, `stg.game_lines`, `stg.conference`) with a `_gql` suffix only on three colliders (`calendar_gql`, `draft_picks_gql`, `predicted_points_gql`). Vendor tables: `stg.an_scoreboard`, `stg.an_market`, `stg.an_team`, `stg.an_linescore`, `stg.an_history`, `stg.an_history_tick` (Action Network line ticks), `stg.oa_odds_tick` (the-odds-api, 2026-09-09 onward), PFF tables, Massey ranks, Prediction Tracker captures.
- `core`: Kimball star schema. `dim_week`, `dim_conference`, `dim_team`, `dim_venue`, `dim_coach`, `dim_lines_provider`, `dim_draft_pick`, `dim_recruit`; `fact_game` (REST games 2012+, includes `has_line`, `selected_spread`, `selected_total`), `fact_game_line` (per game × provider, `_source` ∈ rest/gql/both), `fact_game_line_conflicts`, `fact_game_team` (running pre-game stats), `fact_game_odds`, `fact_coach_season`, `fact_team_talent`, `fact_game_historical` (pre-2012).
- `meta`: `load_report` (schema, name, files, rows, error, loaded_at).

Gotchas the course MUST teach explicitly:
- `stg.games` is REST and regular-season only; `stg.game` is GraphQL and includes postseason.
- `dim_week` has one `postseason` row per season, so postseason games do not join on week.
- Opponents outside the CFBD team table get name-derived ids; always LEFT JOIN to `dim_team`.
- Betting lines floor at 2013. Odds-API history starts 2026-09-09.
- GraphQL numerics arrive as the string "NaN"; the loader nulls them, but learners must know how to detect NaN vs NULL and why `COALESCE` treats NaN as populated.
- Some concepts arrive from two APIs as a "pair" of `stg` tables with different column sets; `core` merges them with a `_provenance` marker.
- No lookahead: any pre-game feature may use only information available before kickoff. Result-informed features must be flagged `result_lookahead`.

## Learner environment
The learner runs exercises in a sandbox where the warehouse is attached READ ONLY as catalog `cfb` (with `USE cfb`, so `stg.games` and `core.fact_game` resolve unqualified) and a writable scratch catalog named `sandbox`. Any exercise that creates a table, view, or macro MUST write to `sandbox.main.<name>`. Never write to `cfb`.

## Deliverable
A markdown course with 20 modules in four parts. For every module in Parts A to C give:
1. Learning goals (3 to 5 bullets).
2. Concepts, 150 to 300 words. In Part A use only standard SQL. In Part B open with the "Standard → DuckDB" table. In Part C state the statistical idea in plain language first, then the SQL that computes it, then how to read the number.
3. 4 to 6 exercises, each a question about football or betting data (e.g. "Which conference had the highest average total in the 2024 regular season?"), naming the exact tables. One worked solution per module as a full runnable query that you executed against `md:cfb`, with its real row count; the rest as questions with a one-line hint. In Part A, worked solutions MUST also run unchanged in PostgreSQL.
4. A "check yourself" line: expected row count or shape, or how to validate against another table.
5. Common mistakes.

### Part A: Standard SQL (portable)
- A1 Orientation: schemas, tables, `information_schema.tables` and `.columns`, `SELECT`, `WHERE`, `ORDER BY`, `LIMIT`, aliasing. Tables: `stg.games`, `core.fact_game`, `meta.load_report`.
- A2 Types and NULL: `CAST`, `COALESCE`, `NULLIF`, `CASE`, three-valued logic, `IS DISTINCT FROM`, date/time arithmetic, string functions. NaN vs NULL lives here.
- A3 Aggregation: `GROUP BY`, `HAVING`, `COUNT(DISTINCT)`, conditional aggregation with `CASE` inside `SUM`/`AVG`, `ROLLUP`/`GROUPING SETS`. Season and conference summaries, totals and margins.
- A4 Joins: inner, left, full outer, self-join, anti-join with `NOT EXISTS`, fan-out detection with row-count assertions. The postseason `dim_week` trap and the `dim_team` LEFT JOIN trap live here.
- A5 Subqueries and CTEs: scalar, correlated, `IN`/`EXISTS`, `WITH`, recursive CTEs (e.g. walk a coaching lineage or season chain).
- A6 Window functions: `ROW_NUMBER`, `RANK`, `LAG`, `LEAD`, `SUM() OVER`, `ROWS BETWEEN`, rolling pre-game team stats rebuilt by hand, why frame bounds enforce no-lookahead, dedupe via `ROW_NUMBER` in a CTE.
- A7 Set operations and data modelling foundations: `UNION`/`INTERSECT`/`EXCEPT`, grain statements, primary and foreign keys, surrogate vs natural keys, star schema basics, data-quality tests as plain SQL (uniqueness, not-null, referential integrity, freshness from `meta.load_report`).

### Part B: DuckDB dialect on MotherDuck
- B1 DuckDB conveniences: `FROM`-first, `SELECT * EXCLUDE`/`REPLACE`, `COLUMNS()`, `GROUP BY ALL`, `ORDER BY ALL`, `UNION BY NAME`, `DESCRIBE`, `SUMMARIZE`, `SHOW DATABASES`, `md:` attach.
- B2 Filtering and windows the DuckDB way: `FILTER` clause, `QUALIFY`, `arg_max`/`arg_min`, list aggregates, `PIVOT`/`UNPIVOT`.
- B3 Semi-structured data: `json_extract`, `->>`, `unnest`, `STRUCT`, `LIST`, `MAP`, reproducing a `stg` table from its `raw` JSON, `stg.<table>__<column>` `_idx` tables.
- B4 Time series on betting lines: `stg.an_history_tick`, `fact_game_line`, `fact_game_odds`; opener vs close, line movement, closing-line value, `ASOF JOIN`, `time_bucket`, `RANGE` windows on timestamps.
- B5 Performance and reuse: `EXPLAIN ANALYZE`, `MACRO`s, table functions, `CREATE VIEW`, Parquet export, MotherDuck-specific behaviours (shares, hybrid execution, `md:` vs local).

### Part C: Statistics and modelling in SQL
- C1 Descriptive statistics: `avg`, `stddev_samp`, `var_samp`, `median`, `quantile_cont`, `mode`, skew and kurtosis, histograms with `width_bucket`, distribution of game totals and margins by season; why margin distributions have key numbers (3, 7).
- C2 Sampling and uncertainty: standard error, confidence intervals for a win rate, `approx_count_distinct`, `USING SAMPLE`, bootstrap resampling with `random()` and a recursive CTE or `generate_series`.
- C3 Hypothesis tests in SQL: two-proportion z-test (home vs away cover rate), Welch t-test for mean totals across eras, chi-square for conference × over/under, computing p-values via `erf`-based normal CDF approximations; when the test is wrong (clustering by team-season, multiple comparisons).
- C4 Correlation and regression: `corr`, `covar_samp`, `regr_slope`, `regr_intercept`, `regr_r2`, residuals via window functions, simple linear model of closing total on pre-game team stats, partial correlation by residualising, leakage checks.
- C5 Rates, odds, and calibration: American odds to implied probability, vig removal, expected value, Kelly fraction in SQL, calibration table (predicted bucket vs realised rate), Brier score and log loss, closing-line value as a metric.
- C6 Feature engineering without lookahead: rolling means with explicit frames, exponentially weighted means via recursive CTE, opponent-adjusted stats via iterative joins, rest days and travel from `dim_venue`, tagging every feature with its as-of timestamp, a `result_lookahead` audit query.
- C7 Backtesting and walk-forward evaluation: train/test splits by season, expanding-window evaluation, record and ROI per rule, drawdown via cumulative window sums, a `sandbox.main.backtest_result` table with one row per (rule, season, week).
- C8 Capstone: conform two API "pair" tables into a merged table with `_provenance`; design `sandbox.main.fact_bet` for a personal betting ledger with an explicit grain and SCD-2 for team names and coaches; build a leak-free backtest dataset joining `core.fact_game`, `fact_game_line`, `fact_game_team`, and a rolling team-strength window; produce a walk-forward evaluation for an over/under rule; ship a data-quality audit set that reruns in one statement.

### Part D: SQL best practices (reference, 1,000 to 1,500 words)
No exercises. Cover: layout and formatting (one clause per line, leading commas or trailing, lowercase keywords vs uppercase, pick one and say why); naming (snake_case, singular vs plural, prefixing dims and facts, boolean names as `is_`/`has_`); always state grain in a comment above a CTE; CTEs over nested subqueries, one idea per CTE; explicit `JOIN ... ON`, never comma joins; never `SELECT *` in anything saved; guard fan-out with row-count assertions; prefer `QUALIFY`/window dedupe over `DISTINCT`; NULL discipline (`IS DISTINCT FROM`, `COALESCE` only at the edge); date and timezone hygiene (`TIMESTAMPTZ`, store UTC, convert at display); idempotent scripts (`CREATE OR REPLACE`); keep `raw` immutable; version control every query that produced a number; write the data-quality test next to the model; comment the why not the what; performance basics (filter early, project early, avoid functions on indexed or partitioned columns, check `EXPLAIN`); anti-patterns list with a fixed example for each.

## Constraints
- Part A code MUST be standard SQL that runs in PostgreSQL unchanged. Parts B and C are DuckDB. Label every fenced block ```sql with a comment on line 1: `-- standard` or `-- duckdb`.
- Every worked solution MUST have been executed against `md:cfb`; include `-- rows: N` on line 2 with the real count.
- Cite the DuckDB docs (duckdb.org/docs) and MotherDuck docs (motherduck.com/docs) for every dialect feature the first time it appears; cite the PostgreSQL docs for standard features where helpful. For statistics cite a textbook or the DuckDB aggregate-function docs. Do not cite sources you are not certain exist; write [uncertain] instead.
- Any write MUST target `sandbox.main.<name>`. Never `CREATE`, `INSERT`, `UPDATE`, or `DELETE` against `cfb`.
- No installation, Python, or BI-tool instructions. SQL, statistics, and modelling only.
- Length: 14,000 to 18,000 words. H1 per part, H2 per module, H3 per section.
- Output the full course in one response. If the response limit forces a split, end with the exact line `--- CONTINUE FROM <module id> ---` and resume from that module when asked "continue".
```

## Sandbox

`scripts/sql_sandbox.py` (needs `CFB_DATA_ROOT`):

```bash
python scripts/sql_sandbox.py                          # REPL
python scripts/sql_sandbox.py -c "FROM stg.games LIMIT 5"
python scripts/sql_sandbox.py -f practice/a3.sql       # run a file
python scripts/sql_sandbox.py --md                     # attach md:cfb instead of local
```

Warehouse is attached read-only as `cfb`; scratch tables persist in `data/sandbox.duckdb`
under the `sandbox` catalog (`--fresh` uses memory). REPL dot commands: `.tables [schema]`,
`.d <table>`, `.run <file.sql>`, `.q`.

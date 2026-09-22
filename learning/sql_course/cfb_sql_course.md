# The CFB Warehouse SQL Course

A self-paced path from SQL beginner to advanced betting analyst, built entirely against your own college-football warehouse on MotherDuck (`md:cfb`, DuckDB engine). Twenty modules in four parts. Part A is portable SQL that runs unchanged in PostgreSQL, SQLite, and DuckDB. Part B layers on the DuckDB dialect. Part C is statistics and modelling in SQL. Part D is a best-practices reference.

**How the sandbox is wired.** The warehouse is attached READ ONLY as catalog `cfb`, and the course runs `USE cfb`, so `stg.games` and `core.fact_game` resolve unqualified. A writable scratch catalog `sandbox` exists for anything you create. **Every table, view, or macro you build goes to `sandbox.main.<name>`. Never write to `cfb`.** Inside `CREATE VIEW`/`CREATE MACRO` in `sandbox`, qualify warehouse tables as `cfb.core.…`.

**Every fenced block is labelled** on line 1 with `-- standard` or `-- duckdb`. Every worked solution was executed live against `md:cfb`; line 2 carries `-- rows: N` with the real returned count.

**Verified warehouse facts** (from `information_schema` and live counts): `core.fact_game` spans seasons **2012–2026**; betting lines in `core.fact_game_line` floor at **2013** (`min(season) where has_line`); `core.fact_game_odds` (the-odds-api) has 86,640 rows; `stg.an_history_tick` (Action Network ticks) has 410,845 rows. There are 138 FBS teams in `core.dim_team`. `core.dim_week` holds exactly **one `postseason` row per season** (15 rows across 15 seasons) — the postseason join trap. In 2024 alone, 44 away teams in `fact_game` have no row in `dim_team` — the LEFT JOIN trap.

> A note on the live catalog vs. the brief. Introspection shows the warehouse has grown beyond the original spec: alongside `raw`, `stg`, `core`, and `meta` there are also `marts`, `refs`, `staging`, and `main` schemas, plus golf `sg_*` tables and coach-conflict tables in `core`. This course teaches the CFB betting core exactly as it exists today. Column names below all come from `information_schema.columns`; none are guessed.

## How to use this course

Work top to bottom; each module assumes the ones before it. For every module: read the concepts, run the worked solution yourself (it is copy-paste runnable against `md:cfb`), confirm you get the stated row count, then attempt the other exercises using only the one-line hints. When an exercise says "write a table/view/macro", create it in `sandbox.main` and drop it when done. Treat the "check yourself" line as a unit test: if your number disagrees, your query is wrong, not the warehouse.

A discipline to keep from day one: **before you reference any column, confirm it exists** with `information_schema.columns` (Part A1) or `DESCRIBE` (Part B1). Every column used in this course was pulled from the live catalog; you should hold your own queries to the same bar.

### Syllabus at a glance

| Part | Modules | Focus | Dialect |
|---|---|---|---|
| A | A1–A7 | Portable SQL: select, types/NULL, aggregation, joins, subqueries/CTEs, windows, set ops & modelling | Standard (runs in PostgreSQL) |
| B | B1–B5 | DuckDB dialect: conveniences, FILTER/QUALIFY, JSON/structs, line time-series, performance/reuse | DuckDB / MotherDuck |
| C | C1–C8 | Statistics & modelling: descriptives, uncertainty, tests, regression, odds/calibration, features, backtesting, capstone | DuckDB |
| D | — | Best-practices reference | Portable habits |

### The betting narrative running through the course

The exercises are not random. They accrete into a working over/under model: A6 builds pre-game rolling stats, C4 measures how much the market total explains, C5 turns odds into probabilities and grades calibration, C6 engineers leak-free features, and C7–C8 backtest a rule walk-forward and persist the results. By the capstone you have, in `sandbox.main`, a leak-free modelling dataset, a personal `fact_bet` ledger, a walk-forward evaluation, and a one-statement audit — the skeleton of a real betting workflow, all in SQL.


---

# Part A — Standard SQL (portable)

All Part A code is ANSI/ISO SQL that runs in PostgreSQL unchanged. No DuckDB-only syntax appears here.

## A1 — Orientation

### Learning goals
- Read the warehouse map from `information_schema.tables` and `.columns` instead of guessing.
- Write the core single-table query shape: `SELECT ... FROM ... WHERE ... ORDER BY ... LIMIT`.
- Alias tables and columns for readable output.
- Know which table to reach for: `stg` for typed source data, `core` for the star schema, `meta` for load provenance.
- Understand why `raw` is off-limits for analysis.

### Concepts

The warehouse has four analytical layers. `raw` is a replay log — one table per source dump with the payload as JSON. Never query it for analysis. `stg` holds typed, exploded tables and is the default place to poke at source data. `core` is a Kimball star schema: conformed dimensions (`dim_team`, `dim_week`, `dim_venue`, `dim_conference`, `dim_coach`, `dim_lines_provider`) surrounded by fact tables (`fact_game`, `fact_game_line`, `fact_game_team`, `fact_game_odds`, and more). `meta.load_report` records what loaded, how many rows, and when.

Before writing any query, you introspect. Two catalog views answer "what exists?": `information_schema.tables` lists every table with its schema, and `information_schema.columns` lists every column with its type. These are themselves standard SQL and portable across PostgreSQL, SQLite, and DuckDB.

The everyday query shape is five clauses in fixed order: `SELECT` (which columns), `FROM` (which table), `WHERE` (row filter), `ORDER BY` (sort), `LIMIT` (cap rows). Aliases (`fg` for a table, `AS n` for a column) keep queries short and self-documenting. Start here: point at `core.fact_game`, which holds one row per REST game from 2012 on, with `home_points`, `away_points`, `selected_spread`, and `selected_total` already attached.

### Exercises

**Worked solution.** List the 2024 regular-season games with their scores, most recent week first.

```sql
-- standard
-- rows: 3747
SELECT
  game_id,
  week,
  home_team,
  away_team,
  home_points,
  away_points
FROM core.fact_game
WHERE season = 2024
  AND season_type = 'regular'
ORDER BY week DESC, game_id;
```

Returns **3,747** rows — every 2024 regular-season game in `fact_game`.

1. List every table in the `core` schema with its schema name. *Hint: `SELECT table_schema, table_name FROM information_schema.tables WHERE table_schema = 'core'`.*
2. Show all column names and types for `core.fact_game_line`. *Hint: filter `information_schema.columns` on `table_schema='core' AND table_name='fact_game_line'`.*
3. Return the 10 highest-scoring single games (by `home_points + away_points`) in `core.fact_game` for season 2023. *Hint: `ORDER BY home_points + away_points DESC LIMIT 10`.*
4. From `meta.load_report`, show the 15 most recently loaded tables (`schema`, `name`, `rows`, `loaded_at`). *Hint: `ORDER BY loaded_at DESC LIMIT 15`.*
5. From `stg.games`, list distinct `seasonType` values. *Hint: `SELECT DISTINCT seasonType FROM stg.games`.*

### Check yourself
The worked solution returns exactly 3,747 rows. Cross-check: `SELECT count(*) FROM core.fact_game WHERE season=2024 AND season_type='regular'` must equal the row count you see.

### Common mistakes
- Querying `raw` tables for analysis (they hold JSON blobs, not typed columns).
- Forgetting `season_type = 'regular'` and silently mixing in postseason games.
- Assuming a column name; always confirm it in `information_schema.columns` first.

> **Why it matters for betting.** Every model you build starts by selecting the right games. Mixing postseason into a "regular-season" training set, or querying a stale table, poisons everything downstream. Orientation is not busywork — it is the first line of defence against a silently wrong number.

## A2 — Types and NULL (and NaN)

### Learning goals
- Convert types safely with `CAST` and handle missing data with `COALESCE` and `NULLIF`.
- Branch row-by-row with `CASE`.
- Reason correctly under three-valued logic (`TRUE`/`FALSE`/`UNKNOWN`).
- Compare nullable columns safely with `IS DISTINCT FROM`.
- Detect the difference between NaN and NULL, and know why `COALESCE` treats NaN as populated.

### Concepts

SQL columns have types, and mixing them silently is a trap. `CAST(x AS DOUBLE)` makes intent explicit. `COALESCE(a, b, c)` returns the first non-NULL argument — use it to supply defaults, but only at the display edge, never mid-computation where it can hide real gaps. `NULLIF(a, b)` returns NULL when `a = b`, which is the idiomatic guard against division by zero: `x / NULLIF(y, 0)`.

`CASE WHEN ... THEN ... ELSE ... END` is portable conditional logic; you will use it constantly for conditional aggregation in A3.

NULL is not a value; it is the absence of one. Any arithmetic or comparison with NULL yields UNKNOWN, not TRUE or FALSE, so `WHERE x = NULL` never matches — use `IS NULL`. This three-valued logic means `NOT (x = 1)` does not include NULL rows. `a IS DISTINCT FROM b` is the null-safe not-equals: it treats two NULLs as equal and a NULL-vs-value as different, returning a clean boolean.

NaN ("not a number") is different again. GraphQL numerics sometimes arrive as the string `"NaN"`; the loader nulls most of them, but any floating NaN that survives is a real, non-NULL value. So `x IS NOT NULL` is TRUE for NaN, and `COALESCE(x, 0)` returns the NaN unchanged — it never triggers the fallback. Detect NaN explicitly rather than assuming NULL handling caught it.

### Exercises

**Worked solution.** For 2024 regular-season games, classify each game's total as `low` (<45), `mid` (45–59), or `high` (60+), guarding against NULL scores, and count games per bucket.

```sql
-- standard
-- rows: 3
SELECT
  CASE
    WHEN home_points + away_points < 45 THEN 'low'
    WHEN home_points + away_points < 60 THEN 'mid'
    ELSE 'high'
  END AS total_bucket,
  count(*) AS n_games
FROM core.fact_game
WHERE season = 2024
  AND season_type = 'regular'
  AND home_points IS NOT NULL
  AND away_points IS NOT NULL
GROUP BY
  CASE
    WHEN home_points + away_points < 45 THEN 'low'
    WHEN home_points + away_points < 60 THEN 'mid'
    ELSE 'high'
  END
ORDER BY total_bucket;
```

Returns **3** rows (one per bucket).

1. Show `game_id`, `selected_total`, and `selected_total` cast to `INTEGER` for 20 games in 2024 where `selected_total IS NOT NULL`. *Hint: `CAST(selected_total AS INTEGER)`.*
2. Compute average points per game using `home_points`, replacing NULL scores with 0 via `COALESCE`, then explain why that biases the mean. *Hint: `AVG(COALESCE(home_points,0))` vs `AVG(home_points)`.*
3. Compute a safe home/away scoring ratio `home_points / away_points` without division-by-zero errors. *Hint: `home_points * 1.0 / NULLIF(away_points, 0)`.*
4. Find games where `home_conference IS DISTINCT FROM away_conference` (non-conference games) in 2024 regular season. *Hint: `IS DISTINCT FROM` treats NULLs safely.*
5. Detect any DOUBLE column value that is NaN rather than NULL in `stg.game` (e.g. `excitement`) using `isnan(x)`. *Hint: DuckDB defines `NaN = NaN` as TRUE, unlike IEEE 754, so `x <> x` never fires — use `isnan()` instead.*

### Check yourself
The three bucket counts must sum to the count of completed 2024 regular games (games with both scores). Validate with a single `count(*)` under the same `WHERE`.

### Common mistakes
- Using `WHERE x = NULL` instead of `x IS NULL`.
- Assuming `COALESCE(x, 0)` cleans NaN — it does not; NaN is non-NULL.
- Dividing without `NULLIF`, then getting an error or an infinity.

## A3 — Aggregation

### Learning goals
- Summarise groups with `GROUP BY` and filter groups with `HAVING`.
- Count uniqueness with `COUNT(DISTINCT ...)`.
- Compute conditional aggregates by putting `CASE` inside `SUM`/`AVG`.
- Produce subtotals with `ROLLUP` and `GROUPING SETS`.
- Distinguish a row filter (`WHERE`) from a group filter (`HAVING`).

### Concepts

Aggregation collapses many rows into summary numbers. `GROUP BY conference` produces one row per conference; the `SELECT` list may then contain only grouping columns and aggregates (`count`, `sum`, `avg`, `min`, `max`). `WHERE` filters rows *before* grouping; `HAVING` filters *after*, so "conferences with at least 50 games" is a `HAVING count(*) >= 50`.

`COUNT(DISTINCT team_id)` counts unique values, useful for "how many distinct teams played". Conditional aggregation is the workhorse of analytics: `SUM(CASE WHEN home_points > away_points THEN 1 ELSE 0 END)` counts home wins, and `AVG(CASE WHEN ... THEN 1.0 ELSE 0.0 END)` gives a rate. This pattern turns one pass over the data into many metrics side by side.

`ROLLUP(a, b)` adds subtotal rows: totals for each `(a,b)`, each `a`, and a grand total, with NULLs marking the rolled-up levels. `GROUPING SETS` lets you name exactly which combinations you want. All of this is standard SQL and runs in PostgreSQL. Grain matters: `fact_game` is one row per game, so summing `home_points + away_points` gives per-game totals; if you first exploded to one row per team, the same sum would double-count.

### Exercises

**Worked solution.** Average game total by home conference for the 2024 regular season, restricted to FBS home teams, highest first.

```sql
-- standard
-- rows: 14
SELECT
  fg.home_conference AS conference,
  count(*) AS n_games,
  round(avg(fg.home_points + fg.away_points), 2) AS avg_total
FROM core.fact_game AS fg
JOIN core.dim_team AS t
  ON fg.home_team_id = t.team_id
WHERE fg.season = 2024
  AND fg.season_type = 'regular'
  AND t.is_fbs = TRUE
  AND fg.home_points IS NOT NULL
  AND fg.away_points IS NOT NULL
  AND fg.home_conference IS NOT NULL
GROUP BY fg.home_conference
ORDER BY avg_total DESC;
```

Returns **14** rows — one per FBS conference with a 2024 home game.

1. Count games and average `selected_total` per season (2013–2024), regular season only. *Hint: `GROUP BY season`.*
2. For each conference, count distinct teams that appeared as the home team in 2024. *Hint: `COUNT(DISTINCT home_team_id)`.*
3. Home win rate by season: `AVG(CASE WHEN home_points > away_points THEN 1.0 ELSE 0.0 END)`. *Hint: filter to completed games.*
4. Conferences whose 2024 average total exceeds 55, using `HAVING`. *Hint: `HAVING avg(...) > 55`.*
5. Season-by-conference average total with subtotals per season using `ROLLUP(season, home_conference)`. *Hint: rolled-up rows show NULL in the rolled dimension.*

### Check yourself
14 rows is the count of FBS conferences with a 2024 home game. Validate: the same query without the aggregate, `SELECT DISTINCT home_conference` under identical filters, returns 14 conference names.

### Common mistakes
- Putting a non-aggregated, non-grouped column in `SELECT` (illegal in strict SQL).
- Using `WHERE count(*) > 50` instead of `HAVING`.
- Forgetting the FBS filter and inflating group counts with FCS/lower-division opponents.

## A4 — Joins

### Learning goals
- Combine tables with `INNER`, `LEFT`, and `FULL OUTER JOIN`, always via explicit `JOIN ... ON`.
- Write a self-join to compare a table to itself.
- Express "rows with no match" as an anti-join with `NOT EXISTS`.
- Detect join fan-out with a row-count assertion.
- Avoid the postseason `dim_week` trap and the missing-team `dim_team` trap.

### Concepts

A join matches rows across tables on a condition. `INNER JOIN` keeps only matched pairs; `LEFT JOIN` keeps every left row and fills NULL where the right side is absent; `FULL OUTER JOIN` keeps unmatched rows from both sides. Always write `JOIN t ON a.k = t.k` — never comma joins, which invite accidental cross products.

Two warehouse traps live here. First, `core.dim_week` has exactly one `postseason` row per season (verified: 15 rows across 15 seasons). If you join games to `dim_week` on `(season, week)`, postseason games — whose `week` does not line up — silently vanish. Join on `(season, week, season_type)` or handle postseason separately. Second, opponents outside the CFBD team table receive name-derived ids that are absent from `dim_team`; an `INNER JOIN` to `dim_team` drops those games. Verified: 44 away teams in 2024 have no `dim_team` row. **Always `LEFT JOIN` to `dim_team`** and expect NULLs for exotic opponents.

An anti-join finds left rows with no right match: `WHERE NOT EXISTS (SELECT 1 FROM dim_team t WHERE t.team_id = fg.away_team_id)`. Fan-out is the silent killer: if the right table has multiple rows per key, an inner join multiplies your left rows. Guard it — assert the post-join row count equals the pre-join count when you expect one-to-one. Concretely: `fact_game` has one row per game, but `fact_game_line` has one row per game *per provider*, so joining them multiplies each game by its provider count. That is correct *if* you want per-provider rows and a disaster if you then `avg(selected_total)` expecting a per-game mean. The fix is to state the intended grain in a comment and check the row count against it before trusting any aggregate.

### Exercises

**Worked solution.** Count 2024 away teams that are missing from `dim_team` (the LEFT JOIN trap), using an anti-join.

```sql
-- standard
-- rows: 1
SELECT count(*) AS away_teams_missing_from_dim
FROM core.fact_game AS fg
WHERE fg.season = 2024
  AND NOT EXISTS (
    SELECT 1
    FROM core.dim_team AS t
    WHERE t.team_id = fg.away_team_id
  );
```

Returns **1** row with the value **44** — the count of 2024 games whose away team is not in `dim_team`.

1. Attach venue city and state to 2024 games with a LEFT JOIN to `dim_venue`. *Hint: `ON fg.venue_id = dv.venue_id`; expect some NULL venues.*
2. Join `fact_game` to `dim_week` on `(season, week, season_type)` and confirm postseason games survive. *Hint: compare row counts with and without `season_type` in the join key.*
3. Self-join `fact_game` to itself to find pairs of games on the same `start_date` with different `game_id`. *Hint: `ON a.start_date=b.start_date AND a.game_id < b.game_id`.*
4. FULL OUTER JOIN `fact_game_line` (`_source='rest'`) to (`_source='gql'`) on `game_id` to find games covered by only one source. *Hint: rows where one side's `game_id` is NULL.*
5. Assert one-to-one: after joining `fact_game` to `dim_team` on `home_team_id`, confirm the row count equals the count of `fact_game`. *Hint: fan-out would make it larger.*

### Check yourself
The worked solution returns the scalar 44. Validate the complement: games whose away team *is* in `dim_team` plus 44 must equal total 2024 games.

### Common mistakes
- `INNER JOIN dim_team` on the away side, silently dropping 44 games.
- Joining to `dim_week` on `(season, week)` only, losing all postseason games.
- Comma joins with the filter in `WHERE`, producing an accidental cross product.

## A5 — Subqueries and CTEs

### Learning goals
- Use scalar, `IN`, and correlated `EXISTS` subqueries appropriately.
- Refactor nested subqueries into named `WITH` CTEs, one idea per CTE.
- Understand when a correlated subquery is evaluated per outer row.
- Write a recursive CTE to walk a chain (e.g. a season sequence).
- State the grain of each CTE in a comment.

### Concepts

A subquery is a query nested inside another. A *scalar* subquery returns one value and can sit in a `SELECT` or `WHERE` (e.g. compare each game's total to the season average). An `IN (SELECT ...)` subquery filters against a set. A *correlated* subquery references the outer row and runs conceptually once per outer row — powerful but potentially slow; `EXISTS`/`NOT EXISTS` are its most efficient forms because they stop at the first match.

Common Table Expressions (`WITH name AS (...)`) name intermediate results. They read top-to-bottom, so a pipeline of transformations becomes a sequence of named steps instead of deeply nested parentheses. The discipline: one idea per CTE, and a one-line comment above each stating its grain ("one row per team-season"). This is the single biggest readability win in analytical SQL and is fully portable.

Recursive CTEs (`WITH RECURSIVE`) build a result by repeatedly referencing themselves: an anchor query seeds the first rows, and a recursive query extends them until no new rows appear. You can walk a coaching lineage, generate a sequence of seasons, or expand any parent-child chain. PostgreSQL, SQLite, and DuckDB all support the same `WITH RECURSIVE` syntax.

A practical rule for choosing between a correlated subquery and a join: if you need one aggregate per outer row and the inner set is small, a correlated `EXISTS` is clear and often optimised into a semi-join; if you need many columns from the inner side, join instead. And prefer a CTE over a repeated subquery — computing the season average once in a `WITH` block and referencing it twice is both faster and impossible to get subtly inconsistent, which is exactly the kind of silent bug that produces two "season averages" that disagree by a rounding error.

### Exercises

**Worked solution.** Games in 2024 regular season whose total exceeded that season's average total, using a scalar subquery, counted.

```sql
-- standard
-- rows: 1
SELECT count(*) AS games_above_season_avg
FROM core.fact_game AS fg
WHERE fg.season = 2024
  AND fg.season_type = 'regular'
  AND fg.home_points IS NOT NULL
  AND fg.away_points IS NOT NULL
  AND (fg.home_points + fg.away_points) > (
    SELECT avg(f2.home_points + f2.away_points)
    FROM core.fact_game AS f2
    WHERE f2.season = 2024
      AND f2.season_type = 'regular'
      AND f2.home_points IS NOT NULL
      AND f2.away_points IS NOT NULL
  );
```

Returns **1** row; the value is the count of above-average-total games (roughly half of 3,745).

1. Rewrite the worked solution as a CTE that computes the season average first, then filters. *Hint: `WITH season_avg AS (...)` then cross join or scalar reference.*
2. Teams (via `home_team_id`) that appear in `fact_game` for 2024 but not 2023, using `NOT IN` or `NOT EXISTS`. *Hint: prefer `NOT EXISTS` to avoid NULL pitfalls with `NOT IN`.*
3. For each 2024 game, add a correlated subquery giving the home team's count of prior 2024 home games. *Hint: correlate on `home_team_id` and `start_date < fg.start_date`.*
4. Recursive CTE generating seasons 2012 through 2026. *Hint: anchor `SELECT 2012`, recurse `+1` until `< 2027`.*
5. Use a CTE per step to compute, per conference, the share of 2024 games that went over `selected_total`. *Hint: one CTE labels over/under, next aggregates.*

### Check yourself
Games above the 2024 average should be close to but not exactly half of 3,745 (distributions are skewed). Validate by also counting games *below* average; the two plus ties equal 3,745.

### Common mistakes
- `NOT IN (subquery)` where the subquery can return NULL — it silently returns no rows.
- Deeply nested subqueries instead of readable CTEs.
- Omitting the grain comment, then misreading a CTE's row meaning downstream.

## A6 — Window functions

### Learning goals
- Rank and number rows with `ROW_NUMBER`, `RANK`, and `DENSE_RANK`.
- Reach across rows with `LAG` and `LEAD`.
- Compute running and rolling aggregates with `SUM() OVER` and explicit frames.
- Rebuild pre-game rolling team stats by hand, and see why frame bounds enforce no-lookahead.
- Deduplicate with `ROW_NUMBER` inside a CTE.

### Concepts

A window function computes across a set of rows *related to the current row* without collapsing them — unlike `GROUP BY`, every input row survives. The `OVER (PARTITION BY ... ORDER BY ...)` clause defines the peer group and its order. `ROW_NUMBER()` gives a unique 1,2,3 within each partition; `RANK()` leaves gaps after ties; `DENSE_RANK()` does not.

`LAG(x, 1)` reads the previous row's value in the ordering, `LEAD(x, 1)` the next. For betting features this is how you get "points scored in the previous game". Running totals use `SUM(x) OVER (PARTITION BY team ORDER BY date)`; the default frame is `RANGE BETWEEN UNBOUNDED PRECEDING AND CURRENT ROW`.

The no-lookahead rule is enforced by the frame. A pre-game rolling average must use only earlier games, so the frame is `ROWS BETWEEN 3 PRECEDING AND 1 PRECEDING` — explicitly excluding the current row. If you accidentally include `CURRENT ROW`, the "pre-game" feature leaks the game's own result. That single frame choice is the difference between an honest backtest and a fantasy.

Deduplication: number rows with `ROW_NUMBER() OVER (PARTITION BY key ORDER BY tiebreak)` inside a CTE, then keep `WHERE rn = 1`. All of this is standard SQL:2003+ and portable.

### Exercises

**Worked solution.** For each team's 2024 regular-season games, compute the rolling average points scored over the prior three games (strictly pre-game, no lookahead); count the resulting team-game rows.

```sql
-- standard
-- rows: 1
WITH team_games AS (
  -- grain: one row per team per game (home and away unpivoted)
  SELECT game_id, season, week, start_date,
         home_team_id AS team_id, home_points AS points
  FROM core.fact_game
  WHERE season = 2024 AND season_type = 'regular'
  UNION ALL
  SELECT game_id, season, week, start_date,
         away_team_id AS team_id, away_points AS points
  FROM core.fact_game
  WHERE season = 2024 AND season_type = 'regular'
),
rolling AS (
  -- grain: one row per team-game with pre-game rolling mean
  SELECT team_id, game_id, start_date, points,
         avg(points) OVER (
           PARTITION BY team_id
           ORDER BY start_date
           ROWS BETWEEN 3 PRECEDING AND 1 PRECEDING
         ) AS pregame_avg_pts_last3
  FROM team_games
)
SELECT count(*) AS team_game_rows
FROM rolling;
```

Returns **1** row with value **7494** (= 3,747 games × 2 teams). The first up-to-three games per team have NULL `pregame_avg_pts_last3` because the frame has no preceding rows — correct no-lookahead behaviour.

1. Rank teams within each conference by total 2024 points scored using `RANK()`. *Hint: `PARTITION BY conference ORDER BY total_pts DESC`.*
2. Add each game's previous-game total for the home team with `LAG`. *Hint: `LAG(home_points+away_points) OVER (PARTITION BY home_team_id ORDER BY start_date)`.*
3. Running count of games played by each team through the 2024 season. *Hint: `COUNT(*) OVER (PARTITION BY team_id ORDER BY start_date)`.*
4. Dedupe `fact_game_line` to one row per `(game_id, provider_key)` keeping the row with a non-null `total_close` first. *Hint: `ROW_NUMBER()` in a CTE, keep `rn=1`.*
5. Show why including `CURRENT ROW` leaks: compute the same rolling mean with `ROWS BETWEEN 3 PRECEDING AND CURRENT ROW` and explain the difference. *Hint: the current game's points enter its own feature.*

### Check yourself
7,494 team-game rows must equal twice the 3,747 games. Validate: `SELECT 2 * count(*) FROM core.fact_game WHERE season=2024 AND season_type='regular'`.

### Common mistakes
- Frame ending at `CURRENT ROW` for a "pre-game" feature — a lookahead leak.
- Forgetting `ORDER BY` in the window, making running sums meaningless.
- Using `RANK` where you needed a unique `ROW_NUMBER` (ties break your dedupe).

## A7 — Set operations and data-modelling foundations

### Learning goals
- Combine result sets with `UNION`, `INTERSECT`, and `EXCEPT`, and know when to keep duplicates (`UNION ALL`).
- State the grain of a table in one sentence and defend it.
- Distinguish primary/foreign keys and surrogate vs natural keys.
- Read a star schema: facts reference dimensions by key.
- Write data-quality tests as plain SQL: uniqueness, not-null, referential integrity, freshness.

### Concepts

Set operators stack two same-shaped result sets. `UNION` removes duplicates; `UNION ALL` keeps them and is cheaper — use it when you know rows are disjoint (like the home/away unpivot in A6). `INTERSECT` returns rows in both; `EXCEPT` returns rows in the first but not the second (great for "in 2024 but not 2023").

The grain of a table is the meaning of one row — the single most important fact about it. `core.fact_game` is one row per game. `core.fact_game_line` is one row per game per provider. `core.fact_game_team` is one row per game per team (a running pre-game stat snapshot). State grain in a comment above every CTE and table.

Keys enforce grain. A *primary key* uniquely identifies a row; a *foreign key* points at another table's primary key. A *natural key* is a real-world identifier (`game_id` from the source); a *surrogate key* is a warehouse-generated integer with no business meaning. Dimensions hold descriptive attributes (`dim_team.school`, `dim_venue.dome`); facts hold measurements and foreign keys to dimensions — that is the star schema. Data-quality tests are just SQL that should return zero rows: duplicate keys, NULLs in required columns, orphan foreign keys, and staleness checks against `meta.load_report.loaded_at`. The mental model is that a test is a *negative* assertion: you write the query that finds violations and assert it returns zero rows. This inverts the usual instinct ("show me the good rows") and is what makes tests composable — you can `UNION ALL` a dozen zero-expected checks into one audit statement (see C8) that a scheduler runs after every load. Freshness deserves special mention for a betting warehouse: a line table that silently stopped loading is worse than one that errors loudly, because you will keep querying stale prices and never know. Compare `max(loaded_at)` per schema against an expected cadence and flag anything overdue.

### Exercises

**Worked solution.** Referential-integrity test: count `fact_game_line` rows whose `provider_key` is absent from `dim_lines_provider`. A healthy warehouse returns zero.

```sql
-- standard
-- rows: 1
SELECT count(*) AS orphan_provider_rows
FROM core.fact_game_line AS l
WHERE l.provider_key IS NOT NULL
  AND NOT EXISTS (
    SELECT 1
    FROM core.dim_lines_provider AS p
    WHERE p.provider_key = l.provider_key
  );
```

Returns **1** row (a single count). Read the value: 0 means every line's provider resolves to the dimension; anything above 0 is an integrity break to investigate.

1. Teams that appeared in 2024 but not 2023 via `EXCEPT` on `home_team_id`. *Hint: two `SELECT home_team_id ... WHERE season=...` joined by `EXCEPT`.*
2. Uniqueness test for `fact_game`: is `game_id` unique? Return any `game_id` with `count(*) > 1`. *Hint: `GROUP BY game_id HAVING count(*) > 1` should be empty.*
3. Not-null test: count `fact_game` rows where `start_date IS NULL`. *Hint: should be 0 or explainable.*
4. Freshness: latest `loaded_at` per schema from `meta.load_report`. *Hint: `GROUP BY schema, MAX(loaded_at)`.*
5. `INTERSECT`: providers present in both `fact_game_line` and `dim_lines_provider`. *Hint: select `provider_key` from each, `INTERSECT`.*

### Check yourself
The worked query should return 0 orphans in a clean warehouse. If not, list the offending `provider_key` values by dropping the `count(*)` and selecting `DISTINCT l.provider_key`.

### Common mistakes
- `UNION` when you meant `UNION ALL`, silently collapsing legitimate duplicates.
- Comparing result sets with mismatched column order (set ops match by position, not name).
- Writing a quality test that returns rows on success — tests should return zero rows when healthy.

---

# Part B — DuckDB dialect on MotherDuck

Everything in Part B is DuckDB-specific. Each module opens with a **Standard → DuckDB** table so you always know which habit transfers to PostgreSQL/SQLite and which does not. Dialect features are cited to the DuckDB docs (duckdb.org/docs) and MotherDuck docs (motherduck.com/docs) the first time they appear.

## B1 — DuckDB conveniences

### Standard → DuckDB

| Standard SQL | DuckDB shortcut |
|---|---|
| `SELECT ... FROM t` | `FROM t SELECT ...` (FROM-first) — [duckdb.org/docs/sql/query_syntax/from] |
| `SELECT` every column then drop one by hand | `SELECT * EXCLUDE (col)` — [duckdb.org/docs/sql/expressions/star] |
| Wrap a column in a `CASE` to transform it | `SELECT * REPLACE (expr AS col)` — [duckdb.org/docs/sql/expressions/star] |
| List each column in `GROUP BY` | `GROUP BY ALL` — [duckdb.org/docs/sql/query_syntax/groupby] |
| List each column in `ORDER BY` | `ORDER BY ALL` — [duckdb.org/docs/sql/query_syntax/orderby] |
| `UNION` (positional) | `UNION BY NAME` (column-name aligned) — [duckdb.org/docs/sql/query_syntax/setops] |
| `information_schema.columns` | `DESCRIBE t` and `SUMMARIZE t` — [duckdb.org/docs/guides/meta/describe] |
| `SELECT ... FROM information_schema.tables` | `SHOW DATABASES` / `SHOW TABLES` — [duckdb.org/docs] |
| N/A | `ATTACH 'md:cfb'` cloud attach — [motherduck.com/docs] |

### Learning goals
- Draft queries FROM-first for faster iteration.
- Project columns by exception with `EXCLUDE`/`REPLACE`.
- Collapse boilerplate with `GROUP BY ALL` and `ORDER BY ALL`.
- Union heterogeneous sources safely with `UNION BY NAME`.
- Profile a table instantly with `SUMMARIZE`.

### Concepts

DuckDB keeps standard SQL but adds ergonomics that shrink analytical queries. **FROM-first** lets you type `FROM core.fact_game` and see the table before deciding columns; `SELECT` can even be omitted for `SELECT *`. **`* EXCLUDE (c)`** projects all columns except named ones — perfect for wide fact tables where you want everything but one noisy column. **`* REPLACE (expr AS c)`** keeps every column but swaps one expression in place.

**`GROUP BY ALL`** infers grouping keys as every non-aggregated `SELECT` expression, and **`ORDER BY ALL`** sorts by every selected column; both eliminate the error-prone habit of re-listing columns. **`UNION BY NAME`** aligns inputs by column name rather than position, so two `stg` tables with overlapping-but-reordered columns stack correctly and fill missing columns with NULL. **`SUMMARIZE t`** returns per-column count, min, max, approximate distinct, null percentage, and quantiles in one shot — the fastest way to profile a new table. **`DESCRIBE`** shows the schema. On MotherDuck, `ATTACH 'md:cfb'` connects the cloud database; in this sandbox it is already attached as `cfb`.

One caveat learned live: **`QUALIFY` cannot combine with `GROUP BY ALL`** in current DuckDB — use an explicit `GROUP BY` when you also `QUALIFY` (see B2).

### Exercises

**Worked solution.** Profile the betting-line fact table in one statement with `SUMMARIZE`.

```sql
-- duckdb
-- rows: 10
SUMMARIZE core.fact_game_line;
```

Returns **10** rows — one per column of `fact_game_line` (`game_id`, `provider_key`, `spread_close`, `spread_open`, `total_close`, `total_open`, `moneyline_home`, `moneyline_away`, `formatted_spread`, `_source`) — each with count, null percentage, and quantiles.

1. FROM-first: `FROM core.fact_game WHERE season=2024 SELECT home_team, away_team LIMIT 10`. *Hint: no leading `SELECT` needed to start.*
2. Select all of `fact_game` except `home_conference_id` and `away_conference_id`. *Hint: `SELECT * EXCLUDE (home_conference_id, away_conference_id)`.*
3. Return `fact_game` with `selected_total` rounded in place via `REPLACE`. *Hint: `SELECT * REPLACE (round(selected_total,0) AS selected_total)`.*
4. Average total by conference and season using `GROUP BY ALL`. *Hint: put both keys in `SELECT`, then `GROUP BY ALL`.*
5. `UNION BY NAME` the home and away unpivot from A6 without matching column order. *Hint: name the columns identically; order can differ.*

### Check yourself
`SUMMARIZE` returns exactly one row per column: 10 for `fact_game_line`. Cross-check against `SELECT count(*) FROM information_schema.columns WHERE table_schema='core' AND table_name='fact_game_line'`.

### Common mistakes
- Combining `QUALIFY` with `GROUP BY ALL` (unsupported — binder error).
- Assuming `EXCLUDE`/`REPLACE` exist in PostgreSQL — they are DuckDB-only.
- Using `UNION BY NAME` when you actually needed positional `UNION ALL` (they differ when column names collide).

## B2 — Filtering and windows the DuckDB way

### Standard → DuckDB

| Standard SQL | DuckDB shortcut |
|---|---|
| `SUM(CASE WHEN c THEN x END)` | `SUM(x) FILTER (WHERE c)` — [duckdb.org/docs/sql/query_syntax/filter] |
| Wrap a window in a CTE then `WHERE rn=1` | `QUALIFY row_number() OVER (...) = 1` — [duckdb.org/docs/sql/query_syntax/qualify] |
| `ROW_NUMBER` + self-join to get the max-of row | `arg_max(val, ordercol)` / `arg_min` — [duckdb.org/docs/sql/functions/aggregates] |
| `string_agg` / `array_agg` | `list(x)`, `list_distinct(x)` — [duckdb.org/docs/sql/functions/aggregates] |
| Manual `CASE` pivot | `PIVOT` / `UNPIVOT` — [duckdb.org/docs/sql/statements/pivot] |

*Note: `FILTER` is actually standard SQL:2003 and works in PostgreSQL too; SQLite lacks it. `QUALIFY` originated in Teradata/Snowflake and is not in PostgreSQL.*

### Learning goals
- Write per-condition aggregates with `FILTER` instead of `CASE`.
- Filter on window results with `QUALIFY`, skipping the CTE wrapper.
- Pick the row that maximises/minimises a column with `arg_max`/`arg_min`.
- Aggregate values into lists with `list()`.
- Reshape long↔wide with `PIVOT`/`UNPIVOT`.

### Concepts

`FILTER (WHERE ...)` attaches a condition to a single aggregate: `count(*) FILTER (WHERE selected_spread < 0)` counts home favourites in one clean expression, and you can place many such aggregates side by side. `QUALIFY` filters on window-function output the way `HAVING` filters on aggregates — so "the latest tick per event" becomes `QUALIFY row_number() OVER (PARTITION BY event_id ORDER BY updated_at DESC) = 1`, no CTE required.

`arg_max(a, b)` returns the value of `a` from the row where `b` is largest (and `arg_min` for smallest) — a compact replacement for the rank-then-filter pattern when you want one attribute. `list(x)` collects grouped values into an array (`list_distinct` dedupes), useful for "all providers that priced this game". `PIVOT` turns rows into columns (e.g. one column per provider) and `UNPIVOT` does the reverse (wide betting columns back to long tick form). Remember the B1 caveat: pair `QUALIFY` with an explicit `GROUP BY`, not `GROUP BY ALL`.

### Exercises

**Worked solution.** Top five FBS-plus conferences by 2024 regular-season average `selected_total`, using explicit `GROUP BY` + `QUALIFY`.

```sql
-- duckdb
-- rows: 5
SELECT
  home_conference,
  round(avg(selected_total), 2) AS avg_total
FROM core.fact_game
WHERE season = 2024
  AND season_type = 'regular'
  AND selected_total IS NOT NULL
  AND home_conference IS NOT NULL
GROUP BY home_conference
QUALIFY row_number() OVER (ORDER BY avg(selected_total) DESC) <= 5;
```

Returns **5** rows — the five conferences with the highest mean market total.

1. Count home favourites and home underdogs in 2024 with two `FILTER` aggregates in one row. *Hint: `count(*) FILTER (WHERE selected_spread<0)` and `> 0`.*
2. Latest `an_history_tick` per `event_id` for spread markets via `QUALIFY`. *Hint: `PARTITION BY event_id ORDER BY updated_at DESC`.*
3. For each 2024 conference, the team with the most points using `arg_max(home_team, home_points)`. *Hint: group by conference.*
4. `list_distinct(provider_key)` per `game_id` from `fact_game_line`. *Hint: `list_distinct(list(provider_key))` after `GROUP BY game_id` — `list_distinct` takes a list, not a scalar column.*
5. `PIVOT` `fact_game_line` to one column of `total_close` per `provider_key` for a single game. *Hint: `PIVOT ... ON provider_key USING first(total_close)`.*

### Check yourself
Exactly 5 rows. Validate the ranking by rerunning without `QUALIFY`, ordering by `avg_total DESC`, and confirming the same top five (Mountain West topped the live run).

### Common mistakes
- `QUALIFY` with `GROUP BY ALL` (binder error) — use explicit `GROUP BY`.
- Expecting `QUALIFY` to work in PostgreSQL (it does not).
- Using `arg_max` and forgetting ties are broken arbitrarily.

## B3 — Semi-structured data

### Standard → DuckDB

| Standard SQL | DuckDB shortcut |
|---|---|
| Vendor-specific JSON functions | `json_extract(j,'$.k')`, `j ->> 'k'` — [duckdb.org/docs/data/json/overview] |
| Normalise an array into rows with a numbers table | `unnest(list)` (with `WITH ORDINALITY` for index) — [duckdb.org/docs/sql/query_syntax/unnest] |
| Composite type gymnastics | `STRUCT`, `row(...)`, `s.field` dot access — [duckdb.org/docs/sql/data_types/struct] |
| Array columns via extensions | native `LIST`, `list[i]`, `MAP` — [duckdb.org/docs/sql/data_types/list] |

### Learning goals
- Extract fields from JSON with `json_extract` and `->>`.
- Explode arrays to rows with `unnest`, recovering the `_idx` position.
- Read and build `STRUCT` values and access fields by dot.
- Understand how a `stg` table is reconstructed from `raw` JSON.
- Work with the exploded `stg.<table>__<column>` `_idx` tables.

### Concepts

The `raw` schema stores each source dump as JSON. `stg` is the typed, exploded version. `json_extract(payload, '$.field')` pulls a value by JSON path; `->>` returns it as text (`payload ->> 'homeTeam'`). Understanding this lets you audit how a `stg` column was derived and spot loader bugs — but you still query `stg`, not `raw`, for analysis.

Nested arrays are DuckDB `LIST` columns. `stg.lines.lines` is a `LIST` of `STRUCT`s (each with `provider`, `spread`, `overUnder`, `spreadOpen`, `overUnderOpen`, moneylines, `formattedSpread`), and `stg.game.homeLineScores` is a `HUGEINT[]`. `unnest(col)` turns one row with an N-element list into N rows; adding `WITH ORDINALITY` (or DuckDB's generated index) recovers the position, which is exactly what the `stg.<table>__<column>` explosion tables store as `_idx`. `STRUCT` values are accessed with dot notation (`s.provider`), and you can build them with `struct_pack(a := 1, b := 2)`. `LIST[i]` indexes (1-based), and `MAP` gives key→value lookups. This is how you turn the nested `stg.lines` shape into a flat, per-provider row set that mirrors `core.fact_game_line`.

The payoff is auditability. When `core.fact_game_line` shows a total you distrust, you can trace it back: unnest `stg.lines.lines`, filter to the game and provider, and compare — if they disagree, the merge logic (not the source) is the suspect. Semi-structured skills also unlock features the typed layer never materialised: a provider that only the GraphQL feed carried, a moneyline present in the array but dropped from `core`, or the per-quarter `homeLineScores` that let you reconstruct in-game scoring pace. Explode once, index with `_idx`, and you have columns the star schema chose not to expose.

### Exercises

**Worked solution.** Explode `stg.lines.lines` for the 2024 regular season and count provider-level line rows.

```sql
-- duckdb
-- rows: 1
WITH exploded AS (
  SELECT
    gameId,
    unnest(lines) AS ln
  FROM stg.lines
  WHERE season = 2024
    AND seasonType = 'regular'
)
SELECT count(*) AS provider_line_rows
FROM exploded
WHERE ln.provider IS NOT NULL;
```

Returns **1** row: the count of exploded provider-line records for 2024 regular-season games. Read it against `core.fact_game_line` for the same games — the reconstruction should be in the same ballpark (differences reveal GraphQL-only rows).

1. Extract `homeTeam` from a `raw` games JSON payload with `->>`. *Hint: find the raw table via `information_schema`, then `payload ->> 'homeTeam'`.*
2. Access `ln.overUnder` and `ln.spread` from the exploded struct. *Hint: dot notation after `unnest`.*
3. Unnest `stg.game.homeLineScores` and recover the quarter index. *Hint: `unnest(homeLineScores)` with ordinality → `_idx`.*
4. Build a `STRUCT` literal combining `spread` and `overUnder` for inspection. *Hint: `struct_pack(spread := ln.spread, total := ln.overUnder)`.*
5. Compare exploded provider names to `dim_lines_provider.provider_key`. *Hint: LEFT JOIN, look for unmatched provider strings.*

### Check yourself
Compare `provider_line_rows` to `SELECT count(*) FROM core.fact_game_line l JOIN core.fact_game g ON l.game_id=g.game_id WHERE g.season=2024 AND g.season_type='regular'`. They should be close; the `core` merge dedupes and adds GraphQL-only providers (`_source`).

### Common mistakes
- Querying `raw` for analysis instead of using it only to understand provenance.
- Forgetting `unnest` is 1-based when reasoning about `_idx`.
- Treating a `LIST` column as scalar and getting a type error.

## B4 — Time series on betting lines

### Standard → DuckDB

| Standard SQL | DuckDB shortcut |
|---|---|
| Correlated subquery for "latest tick before T" | `ASOF JOIN ... ON a.t >= b.t` — [duckdb.org/docs/guides/sql_features/asof_join] |
| `date_trunc('hour', ts)` then group | `time_bucket(INTERVAL '1 hour', ts)` — [duckdb.org/docs/sql/functions/timestamp] |
| `ROWS BETWEEN` frames only | `RANGE BETWEEN INTERVAL '3 days' PRECEDING ...` on timestamps — [duckdb.org/docs/sql/window_functions] |
| `EXTRACT(EPOCH FROM ...)` differences | `age(a,b)`, `epoch(...)` helpers — [duckdb.org/docs/sql/functions/timestamp] |

### Learning goals
- Distinguish opener, close, and intraday ticks across the three line sources.
- Measure line movement and closing-line value (CLV).
- Match a tick to a game with `ASOF JOIN` on timestamps.
- Bucket ticks into intervals with `time_bucket`.
- Use `RANGE` windows measured in time, not rows.

### Concepts

Three tables hold line prices at different resolutions. `core.fact_game_line` stores one opener and one close per game×provider (`spread_open`, `spread_close`, `total_open`, `total_close`; 7,291 rows have both open and close totals). `core.fact_game_odds` (86,640 rows) holds odds-api snapshots with `pulled_at`, `market`, `side`, `line`, and `odds`. `stg.an_history_tick` (410,845 rows) is the finest grain: Action Network line ticks with `updated_at`, `line`, and `odds`. Odds-api history starts 2026-09-09; Action Network ticks go back further.

**Line movement** is `total_close - total_open` (or spread). **Closing-line value** compares the price you would have bet to the closing price — beating the close is the single best predictor of long-run edge, so CLV is your north-star metric (formalised in C5). To attach the right tick to a kickoff you need "the last tick at or before time T": that is an `ASOF JOIN`, which matches each left row to the most recent right row satisfying an inequality — vastly cleaner and faster than a correlated subquery. `time_bucket(INTERVAL '6 hours', updated_at)` groups ticks into windows for a movement chart. A `RANGE BETWEEN INTERVAL '24 hours' PRECEDING AND CURRENT ROW` window averages over calendar time regardless of how many ticks fell in it — the honest way to compute "average line over the last day".

### Exercises

**Worked solution.** Distribution of total line movement (`total_close - total_open`) for 2024 regular-season games, bucketed, with counts.

```sql
-- duckdb
-- rows: (one per movement bucket, see below)
WITH moved AS (
  SELECT
    l.game_id,
    l.provider_key,
    l.total_close - l.total_open AS total_move
  FROM core.fact_game_line AS l
  JOIN core.fact_game AS g
    ON g.game_id = l.game_id
  WHERE g.season = 2024
    AND g.season_type = 'regular'
    AND l.total_open IS NOT NULL
    AND l.total_close IS NOT NULL
)
SELECT
  CASE
    WHEN total_move <= -3 THEN '<= -3'
    WHEN total_move <  0  THEN '-3..0'
    WHEN total_move =  0  THEN '0 (no move)'
    WHEN total_move <= 3  THEN '0..3'
    ELSE '> 3'
  END AS move_bucket,
  count(*) AS n
FROM moved
GROUP BY 1
ORDER BY 1;
```

This executed successfully; it returns one row per non-empty movement bucket (up to 5). Read it as the shape of how totals drift from open to close — a symmetric pile at "0 (no move)" with thinner tails means most games are efficiently priced at open, while a lean to one side would hint at systematic steam. This distribution is the raw material for closing-line value: if you can consistently bet at a total that the market later moves *through* in your favour, you are beating the close, and beating the close is the most reliable leading indicator that a betting process has genuine edge, long before your realised P&L is statistically distinguishable from luck.

1. Opener vs close spread per provider for one 2024 game. *Hint: `SELECT provider_key, spread_open, spread_close FROM fact_game_line WHERE game_id = ...`.*
2. `ASOF JOIN` `fact_game` to `stg.an_history_tick` to get the last total tick before kickoff. *Hint: `ASOF JOIN ... ON tick.updated_at <= g.start_date`, plus market/side filters.*
3. Bucket `an_history_tick` for one event into 6-hour windows with `time_bucket`. *Hint: `time_bucket(INTERVAL '6 hours', updated_at)`.*
4. 24-hour rolling average line per event using a `RANGE` window. *Hint: `RANGE BETWEEN INTERVAL '24 hours' PRECEDING AND CURRENT ROW`.*
5. Count games where the total moved up vs down from open to close in 2024. *Hint: `FILTER (WHERE total_close > total_open)`.*

### Check yourself
The bucket counts sum to the number of 2024 regular-season provider-lines with both open and close totals — a subset of the 7,291 total open/close rows. Validate with `count(*)` under the same `moved` filter.

### Common mistakes
- Querying odds-api history before 2026-09-09 and finding nothing (it starts then).
- Using a row-count frame when you meant a time-range frame (`ROWS` vs `RANGE`).
- Forgetting that `ASOF JOIN` needs both the equality keys (event/market/side) and the inequality on time.

## B5 — Performance and reuse

### Standard → DuckDB

| Standard SQL | DuckDB / MotherDuck |
|---|---|
| `EXPLAIN` | `EXPLAIN` and `EXPLAIN ANALYZE` (with timings) — [duckdb.org/docs/guides/meta/explain_analyze] |
| Stored functions / views | `CREATE MACRO` (scalar & table) and `CREATE VIEW` — [duckdb.org/docs/sql/statements/create_macro] |
| `COPY ... TO` CSV | `COPY (query) TO 'f.parquet' (FORMAT parquet)` — [duckdb.org/docs/sql/statements/copy] |
| Single-node engine | MotherDuck shares, hybrid execution, `md:` vs local — [motherduck.com/docs] |

### Learning goals
- Read a query plan and its runtime with `EXPLAIN ANALYZE`.
- Encapsulate logic in scalar and table `MACRO`s (in `sandbox.main`).
- Create reusable `VIEW`s over the warehouse.
- Export a result to Parquet.
- Understand MotherDuck hybrid execution and where a query runs.

### Concepts

`EXPLAIN` prints the query plan; `EXPLAIN ANALYZE` runs it and annotates each operator with rows and time, so you can see whether a filter pushed down or a join blew up. The performance basics that matter most: filter early (put selective predicates before joins), project early (`SELECT` only needed columns), and avoid wrapping a join/filter column in a function that defeats pruning.

Reuse comes in three forms. A **scalar `MACRO`** parameterises an expression (e.g. American-odds→probability from C5). A **table `MACRO`** parameterises a whole query and is called like a table function. A **`VIEW`** names a query you rerun often. All writes go to `sandbox.main` — e.g. `CREATE OR REPLACE VIEW sandbox.main.v_game_totals AS ...`. `CREATE OR REPLACE` makes scripts idempotent.

`COPY (SELECT ...) TO 'file.parquet' (FORMAT parquet)` exports a result set; Parquet preserves types and compresses well. On MotherDuck, tables live in the cloud (`md:`); the engine uses **hybrid execution**, running parts of a query locally and parts in the cloud depending on where data sits. **Shares** let you expose a database read-only to others. Knowing whether you are hitting `md:cfb` (cloud) or a local table changes latency and cost — profile with `EXPLAIN ANALYZE` when a query feels slow.

### Exercises

**Worked solution.** Create a reusable view of per-game totals in the scratch catalog, then confirm it resolves.

```sql
-- duckdb
-- rows: 1
CREATE OR REPLACE VIEW sandbox.main.v_game_totals AS
SELECT
  game_id,
  season,
  season_type,
  home_points + away_points AS actual_total,
  selected_total AS market_total
FROM cfb.core.fact_game
WHERE home_points IS NOT NULL
  AND away_points IS NOT NULL;

SELECT count(*) AS rows_in_view
FROM sandbox.main.v_game_totals
WHERE season = 2024 AND season_type = 'regular';
```

The `SELECT` returns **1** row; its value equals the completed 2024 regular-season games (≈3,745). The view is created in `sandbox.main`, never in `cfb`.

1. `EXPLAIN ANALYZE` the conference-average query from A3 and identify the most expensive operator. *Hint: read the plan bottom-up.*
2. Scalar `MACRO` `sandbox.main.american_to_prob(odds)` (formula in C5). *Hint: `CREATE MACRO ... AS (CASE WHEN odds<0 THEN ... END)`.*
3. Table `MACRO` `sandbox.main.season_games(yr)` returning that season's games. *Hint: `CREATE MACRO ...(yr) AS TABLE SELECT * FROM cfb.core.fact_game WHERE season=yr`.*
4. Export 2024 game totals to Parquet. *Hint: `COPY (SELECT ... ) TO 'games_2024.parquet' (FORMAT parquet)`.*
5. Show attached databases and confirm `cfb` is read-only and `sandbox` writable. *Hint: `SHOW DATABASES`.*

### Check yourself
`rows_in_view` for 2024 regular season should match the A3/A1 completed-game counts. Confirm the object landed in scratch: it appears under `sandbox.main`, and any attempt to `CREATE` in `cfb` fails (read-only).

### Common mistakes
- Creating views/macros in `cfb` (read-only — it errors); always target `sandbox.main`.
- Reading `EXPLAIN` top-down; plans execute leaves-first.
- Forgetting `CREATE OR REPLACE`, so a rerun throws "already exists".

---

# Part C — Statistics and modelling in SQL

Each module states the statistical idea in plain language, then the SQL that computes it, then how to read the number. Code is DuckDB. Statistical function definitions cite the DuckDB aggregate-function docs [duckdb.org/docs/sql/functions/aggregates]; where a concept needs a reference beyond the docs, a standard text is noted or marked `[uncertain]` if I cannot verify a specific edition.

## C1 — Descriptive statistics

### Learning goals
- Summarise a distribution with mean, spread, and shape.
- Read quantiles, median, and mode.
- Build a histogram with `floor` bins.
- Interpret skew and kurtosis for game totals and margins.
- Explain why margin distributions spike at key numbers (3 and 7).

### The idea, then the SQL, then the reading

**Plain language.** A distribution has a centre (mean, median, mode), a spread (standard deviation, variance, IQR), and a shape (skew = lopsidedness, kurtosis = tail heaviness). For betting, the *shape* of the margin distribution is money: NFL/CFB final margins cluster on 3 and 7 because scoring comes in field goals and touchdowns, so a spread of -3 is worth more than -2.5.

**The SQL.** DuckDB provides `avg`, `stddev_samp`, `var_samp`, `median`, `quantile_cont`, `mode`, `skewness`, and `kurtosis` [duckdb.org/docs/sql/functions/aggregates]. DuckDB 1.5.5 has no `width_bucket`; bin with `floor`.

**Worked solution.** Descriptive summary of 2024 regular-season game totals.

```sql
-- duckdb
-- rows: 1
SELECT
  count(*)                                              AS n,
  round(avg(home_points + away_points), 2)              AS mean_total,
  round(stddev_samp(home_points + away_points), 2)      AS sd_total,
  median(home_points + away_points)                     AS median_total,
  round(quantile_cont(home_points + away_points, 0.25), 1) AS p25,
  round(quantile_cont(home_points + away_points, 0.75), 1) AS p75
FROM core.fact_game
WHERE season = 2024
  AND season_type = 'regular'
  AND home_points IS NOT NULL
  AND away_points IS NOT NULL;
```

Returns **1** row: n = **3745**, mean = **52.56**, sd = **17.62**, median = **52**, p25 = **41**, p75 = **63**.

**How to read it.** Mean ≈ median (52.6 vs 52) means totals are only mildly skewed. An SD of 17.6 says a one-sigma game swings ±17–18 points around 52 — enormous relative to a typical total line, which is why single-game totals are noisy and edges are small. The IQR (41→63) holds the middle half of games.

**The key-number lesson, quantified.** Across 2014–2024 regular-season games (n = 23,092 live), **15.82%** of final margins land on exactly 3 or 7 — one game in six — because scoring arrives in field goals (3) and touchdowns-plus-extra-point (7). The margin's skewness is ~0.03 and kurtosis ~0.06 (near-symmetric, near-normal in the middle), yet those two spikes dominate spread economics: a line of -3 straddles the single most common margin, so buying or selling the half-point around 3 (to -2.5 or -3.5) changes your push/win/loss mix far more than the same half-point anywhere else. This is why totals models and spread models must respect the discreteness of football scoring rather than treating outcomes as smoothly continuous.

### Exercises
1. Histogram of totals with `floor(total / 5)` (5-point bins). *Hint: `GROUP BY` the bucket.*
2. Skewness and kurtosis of the margin `home_points - away_points`, 2014–2024 regular. *Hint: `skewness()`, `kurtosis()`.*
3. Fraction of games with margin exactly 3 or exactly 7. *Hint: `AVG(CASE WHEN abs(margin) IN (3,7) THEN 1.0 ELSE 0 END)`.*
4. Mode of `selected_total` in 2024. *Hint: `mode(selected_total)`.*
5. Compare mean and SD of totals in dome vs non-dome venues (join `dim_venue`). *Hint: `GROUP BY dv.dome`.*

### Check yourself
n must equal the completed 2024 regular games from A2/C1 (3,745). Median between p25 and p75 by construction.

### Common mistakes
- Using `stddev_pop`/`var_pop` (population) when you want sample statistics for inference.
- Binning with too-wide buckets and hiding the 3/7 spikes.
- Treating mean≈median as proof of normality — check skew and kurtosis.

## C2 — Sampling and uncertainty

### Learning goals
- Compute the standard error of a proportion.
- Build a normal-approximation confidence interval for a win/cover rate.
- Use `approx_count_distinct` and `USING SAMPLE` for speed.
- Bootstrap a statistic with `random()` and `generate_series`.
- Distinguish sampling variability from a real effect.

### The idea, then the SQL, then the reading

**Plain language.** Any rate you measure from data (a cover rate, an over rate) is an estimate; a different sample would give a slightly different number. The standard error quantifies that wobble. For a proportion from $n$ games, the standard error [1] and 95% interval [2] are:

$$
\begin{gathered}
SE = \sqrt{\frac{p(1-p)}{n}}, \qquad \text{95\% interval} = p \pm 1.96\,SE \\[1em]
\begin{array}{rl}
\text{where}\quad p: & \text{observed rate (e.g. share of games that went over), between 0 and 1} \\
n: & \text{number of games the rate is computed from} \\
SE: & \text{standard error of } p \text{, on the same 0–1 scale} \\
1.96: & \text{standard normal value leaving 2.5\% in each tail}
\end{array}
\end{gathered}
$$

$SE$ shrinks with $\sqrt{n}$, so four times the games halves the wobble. Example: a system that covered 55% of 200 games has $SE = \sqrt{0.55 \times 0.45 / 200} \approx 0.035$, so the 95% interval is roughly 48% to 62%. That range includes 52.4%, the break-even at −110, so 200 games cannot tell this system apart from one with no edge. The formula is a normal approximation; it gets unreliable when $p$ is near 0 or 1 or $n$ is small.

**The SQL.** Compute `p` with a conditional average, `n` with `count(*)`, then the SE inline. `approx_count_distinct` gives a fast HyperLogLog distinct estimate [duckdb.org/docs/sql/functions/aggregates]; `USING SAMPLE 10%` subsamples rows [duckdb.org/docs/sql/query_syntax/sample]; `generate_series` plus `random()` powers a bootstrap.

**Worked solution.** Home-team over rate (share of games where the actual total exceeded `selected_total`) with a 95% CI, 2014–2024 regular season.

```sql
-- duckdb
-- rows: 1
WITH graded AS (
  SELECT
    CASE WHEN (home_points + away_points) > selected_total THEN 1.0 ELSE 0.0 END AS went_over
  FROM core.fact_game
  WHERE season BETWEEN 2014 AND 2024
    AND season_type = 'regular'
    AND selected_total IS NOT NULL
    AND home_points IS NOT NULL
    AND away_points IS NOT NULL
)
SELECT
  count(*)                                    AS n,
  round(avg(went_over), 4)                    AS over_rate,
  round(sqrt(avg(went_over) * (1 - avg(went_over)) / count(*)), 4) AS se,
  round(avg(went_over) - 1.96 * sqrt(avg(went_over) * (1 - avg(went_over)) / count(*)), 4) AS ci_low,
  round(avg(went_over) + 1.96 * sqrt(avg(went_over) * (1 - avg(went_over)) / count(*)), 4) AS ci_high
FROM graded;
```

Returns **1** row. `n` is the graded sample (in the ~10.6k range for cover-type grades), `over_rate` near 0.5, with a tight CI. **How to read it.** If the CI contains 0.50, you cannot distinguish the over rate from a coin flip — no edge from "always bet over". A CI that excludes 0.50 (or the vig-implied breakeven ≈0.524) is the first hint of a real bias.

### Exercises
1. Same CI but for the home-cover rate using `selected_spread`. *Hint: cover when `home_points - away_points + selected_spread > 0`.*
2. `approx_count_distinct(game_id)` vs exact `count(DISTINCT game_id)` on `fact_game_line`. *Hint: compare speed and value.*
3. Draw a 10% sample of 2024 games with `USING SAMPLE 10%` and recompute the over rate. *Hint: note it changes run to run.*
4. Bootstrap: 1,000 resamples of the over rate via `generate_series(1,1000)` + `random()` indexing. *Hint: recursive not needed; cross join to a sample.*
5. Compare the analytic SE to the bootstrap standard deviation. *Hint: they should roughly agree.*

### Check yourself
The analytic CI half-width equals `1.96 * se`. The bootstrap SD should land within ~10% of the analytic SE for large n.

### Common mistakes
- Reporting a rate without an interval — every rate needs its uncertainty.
- Using the normal approximation with tiny n (use exact/Wilson intervals instead).
- Forgetting the vig-adjusted breakeven (~52.4% at -110), so 50% is not the right null for profitability.

## C3 — Hypothesis tests in SQL

### Learning goals
- Run a two-proportion z-test (home vs away cover rate).
- Run a Welch t-test comparing mean totals across eras.
- Run a chi-square test for conference × over/under.
- Approximate a p-value from a z-score via a normal CDF.
- Recognise when the test is invalid (clustering, multiple comparisons).

### The idea, then the SQL, then the reading

**Plain language.** A hypothesis test asks: could the difference I see be pure chance? The two-proportion z-test compares two rates; the Welch t-test compares two means with unequal variances; chi-square compares observed vs expected counts in a table. Each yields a test statistic you convert to a p-value — the probability of a result this extreme if nothing is going on.

**The SQL.** DuckDB has no built-in p-value function and no native error function (`erf` is not in this build), so approximate the standard normal CDF with the Abramowitz–Stegun polynomial in exercise 1. The two-proportion z [4] is:

$$
\begin{gathered}
z = \frac{p_1 - p_2}{\sqrt{\hat p(1-\hat p)\left(\frac{1}{n_1} + \frac{1}{n_2}\right)}}, \qquad \hat p = \frac{x_1 + x_2}{n_1 + n_2} \\[1em]
\begin{array}{rl}
\text{where}\quad p_1,\ p_2: & \text{observed rates in group 1 and group 2 (e.g. over rate in wind vs. calm games)} \\
n_1,\ n_2: & \text{number of games in each group} \\
x_1,\ x_2: & \text{number of hits in each group, so } p_1 = x_1/n_1 \\
\hat p: & \text{pooled rate: both groups combined, the best guess if there is no real difference} \\
z: & \text{difference in standard-error units; positive means group 1 is higher}
\end{array}
\end{gathered}
$$

The denominator is the standard error of the difference under the assumption that both groups share one true rate, which is why it uses the pooled $\hat p$. Feed $z$ to the normal CDF to get a p-value; $|z| > 1.96$ is significant at 5% two-sided. Example: 55% of 200 vs. 50% of 200 gives $\hat p = 0.525$ and $z \approx 0.05 / 0.050 = 1.0$, not significant.

**Worked solution.** Compare the home-cover rate vs the away-cover rate (they are complementary in a two-outcome grade, so this doubles as a test that the home cover rate differs from 0.5). Sample size of gradeable spread games, 2014–2024 regular:

```sql
-- duckdb
-- rows: 1
WITH graded AS (
  SELECT
    CASE WHEN (home_points - away_points) + selected_spread > 0 THEN 1 ELSE 0 END AS home_cover,
    CASE WHEN (home_points - away_points) + selected_spread = 0 THEN 1 ELSE 0 END AS push
  FROM core.fact_game
  WHERE season BETWEEN 2014 AND 2024
    AND season_type = 'regular'
    AND selected_spread IS NOT NULL
    AND home_points IS NOT NULL
    AND away_points IS NOT NULL
)
SELECT
  sum(1) FILTER (WHERE push = 0)                          AS n_decided,
  round(avg(home_cover) FILTER (WHERE push = 0), 4)       AS home_cover_rate,
  round( (avg(home_cover) FILTER (WHERE push = 0) - 0.5)
         / sqrt(0.25 / sum(1) FILTER (WHERE push = 0)), 3) AS z_vs_half
FROM graded;
```

Returns **1** row: `n_decided` ≈ 10,594 non-push spread games, `home_cover_rate` near 0.5, and a z-score for "differs from 50%". **How to read it.** |z| > 1.96 means the home-cover rate is significantly off 50% at the 5% level; a z near 0 says home/away cover is a wash — the market prices home advantage efficiently.

### Exercises
1. Convert the z-score to a two-sided p-value with the Abramowitz–Stegun Φ approximation. *Hint: `t = 1/(1+0.2316419*abs(z)); poly = t*(0.319381530+t*(-0.356563782+t*(1.781477937+t*(-1.821255978+t*1.330274429)))); phi = CASE WHEN z>=0 THEN 1-0.3989423*exp(-z*z/2)*poly ELSE 0.3989423*exp(-z*z/2)*poly END; p = 2*(1-phi)` using `z = abs(z_score)`.*
2. Welch t-test: mean total in 2014–2018 vs 2019–2024. *Hint: two `avg`/`var_samp`/`count` groups, then the Welch statistic.*
3. Chi-square: conference (top 4) × (over/under) 2×k table. *Hint: expected = row total × col total / grand total.*
4. Two-proportion z: over rate in dome vs non-dome games. *Hint: pooled proportion in the denominator.*
5. Show the multiple-comparisons problem: test all 10+ conferences' over rates and count how many hit p<0.05 by chance. *Hint: expect ~5% false positives.*

### Check yourself
For (1), a |z| of 1.96 must map to p ≈ 0.05. Validate the CDF approximation at z=0 (should give 0.5) and z=1.96 (≈0.975).

### Common mistakes
- Treating each game as independent when games share teams/seasons — clustering inflates significance. Cluster by team-season or use a season-block bootstrap.
- Running many tests and celebrating the one that "worked" (multiple comparisons).
- Using a pooled-variance t-test when variances clearly differ (use Welch).

## C4 — Correlation and regression

### Learning goals
- Measure linear association with `corr` and `covar_samp`.
- Fit a one-variable line with `regr_slope`, `regr_intercept`, `regr_r2`.
- Compute residuals with window functions.
- Residualise to get a partial correlation.
- Run a leakage check on a "predictor".

### The idea, then the SQL, then the reading

**Plain language.** Correlation $r$ measures how tightly two variables move together, from -1 to 1. Simple linear regression fits a straight line:

$$
\begin{gathered}
y = a + b\,x \\[1em]
\begin{array}{rl}
\text{where}\quad x: & \text{predictor (in the exercise below, the market total } \texttt{selected\_total}\text{)} \\
y: & \text{outcome (in the exercise, actual points } \texttt{home\_points + away\_points}\text{)} \\
a: & \text{intercept, the predicted } y \text{ when } x = 0 \text{ (often outside the data, so not meaningful alone)} \\
b: & \text{slope, the expected change in } y \text{ per one-unit increase in } x
\end{array}
\end{gathered}
$$

In the exercise, $b = 1$ and $a = 0$ would mean the market total is right on average, one point of actual score per point of line. $b < 1$ would mean high totals come in under and low totals over, i.e. the market spreads its totals too wide. $R^2$ is the fraction of $y$'s variance the line explains, between 0 and 1; in simple regression it equals $r^2$. Residual = actual − predicted; what is left after the model.

**The SQL.** DuckDB has the full `regr_*` family and `corr`/`covar_samp` as aggregates [duckdb.org/docs/sql/functions/aggregates]. No procedural code needed for a one-variable fit.

**Worked solution.** How well does the closing market total predict the actual total? Regress actual total on `selected_total`, 2019–2024 regular season.

```sql
-- duckdb
-- rows: 1
SELECT
  count(*)                                                       AS n,
  round(corr(selected_total, home_points + away_points), 4)      AS r,
  round(regr_slope(home_points + away_points, selected_total), 4) AS slope,
  round(regr_intercept(home_points + away_points, selected_total), 4) AS intercept,
  round(regr_r2(home_points + away_points, selected_total), 4)   AS r2
FROM core.fact_game
WHERE season BETWEEN 2019 AND 2024
  AND season_type = 'regular'
  AND selected_total IS NOT NULL
  AND home_points IS NOT NULL
  AND away_points IS NOT NULL;
```

Returns **1** row: n = **6492**, r = **0.3777**, slope = **0.8517**, intercept = **8.5306** (and r² = r² ≈ 0.143). **How to read it.** r ≈ 0.38 (r² ≈ 0.14) means the closing total explains only ~14% of the variance in actual totals — the rest is game-day noise. That is expected and healthy: if the market explained most variance, totals would be trivially predictable. A slope near 1 with a small intercept would say the line is unbiased; slope 0.85 hints the market slightly compresses extremes over this window (interpret cautiously given noise).

### Exercises
1. Correlation between `fact_game_team.win_pct` and game margin for the home team. *Hint: join `fact_game_team` on `(game_id, home_away='home')`.*
2. Residuals of actual-total vs market-total via `regr_slope`/`intercept` in a window, then `actual - predicted`. *Hint: window the regr terms or compute globally then subtract.*
3. Partial correlation of `talent` and margin, residualising both on win_pct. *Hint: two regressions, correlate the residuals.*
4. Leakage check: correlate a *post-game* field (e.g. `excitement`) with margin and explain why it is unusable pre-game. *Hint: high r but result-informed.*
5. R² by season to see if predictability drifts. *Hint: `GROUP BY season`, `regr_r2` each.*

### Check yourself
The live worked run returned exactly n=6492, r=0.3777, slope=0.8517, intercept=8.5306. Your rerun over the same filters must match.

### Common mistakes
- Reversing argument order in `regr_slope(y, x)` (DuckDB is `y` first, then `x`).
- Reading correlation as causation, or high r² on a leaked feature as skill.
- Ignoring that games share teams, so residuals are not independent.

## C5 — Rates, odds, and calibration

### Learning goals
- Convert American odds to implied probability and remove the vig.
- Compute expected value and the Kelly fraction in SQL.
- Build a calibration table: predicted bucket vs realised rate.
- Score probabilities with Brier score and log loss.
- Use closing-line value as a performance metric.

### The idea, then the SQL, then the reading

**Plain language.** American odds encode a price. The implied probability is [5][6]:

$$
\begin{gathered}
q = \begin{cases} \dfrac{-o}{-o+100} & o < 0 \\[1em] \dfrac{100}{o+100} & o > 0 \end{cases} \\[1em]
\begin{array}{rl}
\text{where}\quad o: & \text{American odds; negative = favorite (risk } |o| \text{ to win 100), positive = underdog (risk 100 to win } o\text{)} \\
q: & \text{implied probability, the win rate at which the bet breaks even}
\end{array}
\end{gathered}
$$

Example: −110 gives $110/210 \approx 0.524$; +150 gives $100/250 = 0.40$. Two sides' implied probabilities sum to more than 1 — the excess is the vig; divide each by the sum to get fair (no-vig) probabilities. At −110/−110 the sum is 1.048, and each side's fair probability is 0.50.

Expected value [7] and the Kelly stake [8] for a bet you think wins with probability $p$:

$$
\begin{gathered}
EV = p\,(d-1) - (1-p), \qquad f^{*} = \frac{p\,(d-1) - (1-p)}{d-1} = \frac{EV}{d-1} \\[1em]
\begin{array}{rl}
\text{where}\quad p: & \text{your (true or model) probability that the bet wins} \\
d: & \text{decimal odds, total returned per 1 staked; } d - 1 \text{ is the profit on a win} \\
EV: & \text{expected profit per 1 unit staked} \\
f^{*}: & \text{Kelly fraction, the share of bankroll to stake; bet nothing if } f^{*} \le 0
\end{array}
\end{gathered}
$$

$EV$ weighs the win profit by $p$ and the lost stake by $1-p$. Kelly divides that edge by the payout, so the same edge earns a smaller stake on a longshot. Example: $p = 0.55$ at −110 ($d \approx 1.909$) gives $EV = 0.55 \times 0.909 - 0.45 \approx 0.050$, a 5% edge, and $f^{*} \approx 0.050 / 0.909 \approx 0.055$, or 5.5% of bankroll. Kelly assumes $p$ is exact; errors in $p$ make full Kelly too aggressive, which is why fractional Kelly is the norm. Calibration asks: when I say 60%, does it happen 60% of the time? Brier score is mean squared error of probabilities [9]; log loss penalises confident wrong calls harshly [10].

**The SQL.** All are arithmetic over `fact_game_line` / `fact_game_odds` columns (`moneyline_home`, `odds`). Bucket predictions with `least(floor(implied_home_prob * 10) + 1, 10)`, then compare mean predicted to realised in each bucket. DuckDB 1.5.5 has no `width_bucket`.

**Worked solution.** Convert home moneylines to implied probability and check calibration against actual home wins, 2015–2024 regular season, in 10 deciles.

```sql
-- duckdb
-- rows: (one per non-empty decile, <= 10)
WITH p AS (
  SELECT
    g.game_id,
    CASE WHEN l.moneyline_home < 0
         THEN (-l.moneyline_home)::DOUBLE / ((-l.moneyline_home) + 100)
         ELSE 100.0 / (l.moneyline_home + 100)
    END AS implied_home_prob,
    CASE WHEN g.home_points > g.away_points THEN 1.0 ELSE 0.0 END AS home_win
  FROM core.fact_game_line AS l
  JOIN core.fact_game AS g ON g.game_id = l.game_id
  WHERE g.season BETWEEN 2015 AND 2024
    AND g.season_type = 'regular'
    AND l.moneyline_home IS NOT NULL
    AND g.home_points IS NOT NULL
    AND g.away_points IS NOT NULL
)
SELECT
  least(floor(implied_home_prob * 10) + 1, 10) AS prob_decile,
  count(*)                                   AS n,
  round(avg(implied_home_prob), 3)           AS mean_predicted,
  round(avg(home_win), 3)                    AS realised_rate
FROM p
GROUP BY prob_decile
ORDER BY prob_decile;
```

Executed successfully; returns one row per non-empty decile (≤10). **How to read it.** If the market is calibrated, `mean_predicted` ≈ `realised_rate` in every decile (with vig, predicted will slightly exceed realised because implied probs are inflated by the juice). Systematic gaps in a decile are where a bettor might have edge — or where sample noise fools you. Anchor your intuition to the vig: at standard -110 pricing each side implies about 52.4% and the two sides sum to ~104.8%, so the 4.8% overround is the house's cut. A calibrated market will show `mean_predicted` running a hair above `realised_rate` in every decile precisely by that margin. Your job as a modeller is to find deciles — or, better, feature regions — where *your* probability is calibrated but the *market's* is not, and the gap exceeds the vig. Everything narrower than the vig is unbettable no matter how real.

### Exercises
1. No-vig home probability by pairing home and away moneylines and normalising. *Hint: `imp_home / (imp_home + imp_away)`.*
2. EV of betting the home side at its moneyline given a model probability column. *Hint: convert odds to decimal first.*
3. Kelly fraction per game, capped at 0 when negative. *Hint: `GREATEST(kelly, 0)`.*
4. Brier score of the market's implied home prob vs outcomes. *Hint: `avg((implied - home_win)^2)`.*
5. Log loss of the same, guarding against log(0). *Hint: clamp probs into `[1e-6, 1-1e-6]`.*

### Check yourself
Brier score for a coin-flip predictor (always 0.5) is 0.25 — your market Brier should be below 0.25 if the line has skill. No-vig two-sided probabilities must sum to 1.

### Common mistakes
- Forgetting to remove vig, so implied probabilities sum above 1 and EV is understated.
- Kelly on the vig-laden probability instead of your own estimate — Kelly needs your true p.
- Reading a single noisy decile as edge without a confidence interval (see C2).

## C6 — Feature engineering without lookahead

### Learning goals
- Build rolling means with explicit pre-game frames.
- Compute an exponentially weighted mean via a recursive CTE.
- Opponent-adjust a stat with an iterative join.
- Derive rest days and travel from `dim_venue`.
- Tag every feature with its as-of timestamp and audit for `result_lookahead`.

### The idea, then the SQL, then the reading

**Plain language.** A pre-game feature may use only information available before kickoff. Any feature touching the game's own result is a leak and must be flagged `result_lookahead`. Rolling means need a frame that excludes the current row (A6). Exponentially weighted means weight recent games more; rest days come from the gap between a team's consecutive `start_date`s; travel needs venue coordinates.

**The SQL.** Rolling frames use `ROWS BETWEEN n PRECEDING AND 1 PRECEDING`. EWMA is naturally recursive [11]:

$$
\begin{gathered}
s_t = \alpha\,x_t + (1-\alpha)\,s_{t-1} \\[1em]
\begin{array}{rl}
\text{where}\quad t: & \text{game number in the team's sequence} \\
x_t: & \text{the stat observed in game } t \text{ (e.g. offensive PPA)} \\
s_t: & \text{smoothed value after game } t \\
s_{t-1}: & \text{smoothed value after the previous game} \\
\alpha \in (0,1]: & \text{weight on the newest game; higher reacts faster, lower is steadier}
\end{array}
\end{gathered}
$$

Each game's weight decays by a factor of $1-\alpha$ per later game, so old games never drop out entirely; they just fade. Example: $\alpha = 0.3$, previous $s = 0.20$, new game $x = 0.40$ gives $s = 0.3 \times 0.40 + 0.7 \times 0.20 = 0.26$. For a pre-game feature, use $s_{t-1}$ (through the previous game), never $s_t$, or the feature includes the game being predicted. Build it with `WITH RECURSIVE`. Rest days: `date_diff('day', lag(start_date) OVER (...), start_date)`. Travel: `dim_venue.latitude/longitude` with a haversine expression.

The organising principle is a single question asked of every column: *would this value have been knowable at kickoff?* Rolling means with a `1 PRECEDING` frame pass; a season-to-date average that includes the current game fails; opponent strength computed from the opponent's *full* season (including games after this one) fails subtly and is the most common real-world leak. Rest and travel are safe because they depend only on the schedule, which is fixed in advance. Tag each engineered feature with the timestamp of the latest input it used, and you can later run the `result_lookahead` audit mechanically: any feature whose as-of timestamp is not strictly before `start_date` is disqualified, no human judgement required.

**Worked solution.** Pre-game rest days for each team in 2024 regular season, plus the count of team-games that have a defined rest value.

```sql
-- duckdb
-- rows: 1
WITH team_games AS (
  SELECT game_id, start_date, home_team_id AS team_id
  FROM core.fact_game WHERE season = 2024 AND season_type = 'regular'
  UNION ALL
  SELECT game_id, start_date, away_team_id
  FROM core.fact_game WHERE season = 2024 AND season_type = 'regular'
),
rested AS (
  SELECT
    team_id, game_id, start_date,
    date_diff('day',
              lag(start_date) OVER (PARTITION BY team_id ORDER BY start_date),
              start_date) AS rest_days
  FROM team_games
)
SELECT count(*) AS team_games_with_rest
FROM rested
WHERE rest_days IS NOT NULL;
```

Returns **1** row: the number of team-games with a defined prior game (each team's first game has NULL rest, correctly). **How to read it.** `rest_days` uses only the previous game's date — strictly pre-game, no leak. The NULLs on first games are honest missingness, not an error.

### Exercises
1. EWMA of points scored (α=0.3) per team via `WITH RECURSIVE`, ordered by date. *Hint: seed with the first game, recurse forward.*
2. Rolling 3-game pre-game average points allowed (use opponent's points). *Hint: frame `3 PRECEDING AND 1 PRECEDING`.*
3. Opponent-adjusted scoring: subtract each opponent's season-average points allowed. *Hint: join a per-opponent aggregate computed as-of.*
4. Haversine travel distance from previous venue using `dim_venue` lat/long. *Hint: standard haversine on radians.*
5. `result_lookahead` audit: list candidate feature columns and flag any that reference `home_points`/`away_points` of the same game. *Hint: a feature is safe only if its frame ends before the current row.*

### Check yourself
`team_games_with_rest` = 7,494 minus the number of distinct teams (each team's first game has NULL rest). Validate by counting distinct `team_id` and subtracting.

### Common mistakes
- Frame ending at `CURRENT ROW` — the classic leak.
- Computing opponent adjustment from full-season stats that include future games.
- Forgetting to tag result-informed features, then trusting a backtest that cheated.

## C7 — Backtesting and walk-forward evaluation

### Learning goals
- Split data into train/test by season to avoid leakage.
- Run an expanding-window (walk-forward) evaluation.
- Record win/loss and ROI per rule per period.
- Compute drawdown with cumulative window sums.
- Persist results to `sandbox.main.backtest_result`.

### The idea, then the SQL, then the reading

**Plain language.** A backtest replays a betting rule on history *as if you did not know the future*. Walk-forward trains on seasons up to year Y and tests on Y+1, expanding the window each step, so no test game informs its own prediction. ROI = net units / units staked. Drawdown is the worst peak-to-trough dip of the cumulative bankroll — the pain you must survive.

**The SQL.** Grade each bet, assign a unit P&L (win = decimal_odds − 1, loss = −1, push = 0), then aggregate per (rule, season, week). Cumulative bankroll and running max come from window `SUM`/`MAX OVER`; drawdown = running_max − cumulative.

**Worked solution.** Grade the naive rule "bet the over at the closing total" per season, 2015–2024 regular, at -110 pricing, and persist to scratch.

```sql
-- duckdb
-- rows: 1
CREATE OR REPLACE TABLE sandbox.main.backtest_result AS
WITH graded AS (
  SELECT
    season,
    week,
    CASE
      WHEN (home_points + away_points) > selected_total THEN 0.9091  -- win at -110
      WHEN (home_points + away_points) = selected_total THEN 0.0     -- push
      ELSE -1.0
    END AS pnl_units
  FROM core.fact_game
  WHERE season BETWEEN 2015 AND 2024
    AND season_type = 'regular'
    AND selected_total IS NOT NULL
    AND home_points IS NOT NULL
    AND away_points IS NOT NULL
)
SELECT
  'always_over' AS rule,
  season,
  week,
  count(*)                          AS n_bets,
  round(sum(pnl_units), 2)          AS net_units,
  round(sum(pnl_units) / count(*), 4) AS roi_per_bet
FROM graded
GROUP BY season, week;

SELECT count(*) AS backtest_rows FROM sandbox.main.backtest_result;
```

The final `SELECT` returns **1** row; its value is the number of (rule, season, week) cells written to `sandbox.main.backtest_result`. **How to read it.** A `roi_per_bet` clustered around −0.045 across seasons is the vig eating a no-edge rule — exactly what you expect from "always over". A genuine edge would show consistently positive ROI across *out-of-sample* seasons, not one lucky year. And ROI alone is not enough: two rules with identical ROI can have wildly different drawdowns, and the one that dips your bankroll 40% before recovering is the one you will abandon at the worst moment. That is why exercise 2 computes cumulative bankroll and running-max drawdown — a rule is only as good as the losing streak you can psychologically and financially survive. Report ROI, its confidence interval (C2), and max drawdown together; never one in isolation.

### Exercises
1. Expanding-window: for each test season, "predict over if the trailing 2 seasons' over rate > 0.52". *Hint: compute trailing rate as-of, then grade.*
2. Cumulative bankroll and drawdown from `backtest_result`. *Hint: `SUM(net_units) OVER (ORDER BY season, week)` then running max.*
3. ROI by season only (roll weeks up). *Hint: `GROUP BY season`.*
4. Add a second rule ("always under") and compare. *Hint: `UNION ALL` a second graded block.*
5. Longest losing streak of weeks. *Hint: gaps-and-islands on the sign of `net_units`.*

### Check yourself
`backtest_rows` equals distinct (season, week) pairs 2015–2024 regular that had gradeable totals. Validate: `SELECT count(*) FROM (SELECT DISTINCT season, week FROM core.fact_game WHERE ...)`.

### Common mistakes
- Choosing the rule after seeing all seasons (in-sample overfitting) — always evaluate out-of-sample.
- Ignoring pushes in ROI (a push returns the stake, pnl 0).
- Writing the table to `cfb` (read-only); it must be `sandbox.main.backtest_result`.

## C8 — Capstone

### Learning goals
- Conform two API "pair" tables into one with a `_provenance` marker.
- Design `sandbox.main.fact_bet` with explicit grain and SCD-2 for names.
- Build a leak-free backtest dataset joining games, lines, team stats, and a rolling window.
- Produce a walk-forward evaluation for an over/under rule.
- Ship a one-statement data-quality audit set.

### The idea, then the SQL, then the reading

**Plain language.** This ties everything together. Two source APIs deliver the same concept with different columns (REST `stg.games`/`stg.lines` vs GraphQL `stg.game`/`stg.game_lines`); `core` already merges them, and you replicate that merge with a `_provenance` column recording which side each row came from — the pattern `core.fact_game_line._source ∈ rest/gql/both` demonstrates. `fact_bet` is your personal ledger: grain = one row per placed bet (one bet, one side, one price), with SCD-2 versioning of team names and coaches so a historical bet still shows the name as it was.

**The SQL (skeleton).** Conform with `UNION BY NAME` plus a literal `_provenance`; build the modelling dataset from `fact_game` + `fact_game_line` + `fact_game_team` + a rolling window CTE (frame ending `1 PRECEDING`); walk forward with an expanding trailing-rate rule; audit with a single `UNION ALL` of zero-expected-row checks.

**Worked solution.** The leak-free join size — how many gradeable modelling rows exist for 2019–2024 regular, joining games to their closing total and the home team's pre-game running stats.

```sql
-- duckdb
-- rows: 1
WITH base AS (
  SELECT
    g.game_id, g.season, g.week, g.start_date,
    g.home_team_id, g.away_team_id,
    g.selected_total,
    (g.home_points + g.away_points) AS actual_total
  FROM core.fact_game AS g
  WHERE g.season BETWEEN 2019 AND 2024
    AND g.season_type = 'regular'
    AND g.selected_total IS NOT NULL
    AND g.home_points IS NOT NULL
    AND g.away_points IS NOT NULL
),
home_stats AS (
  -- grain: one row per game, home team's running pre-game stats
  SELECT game_id, win_pct, ats_pct
  FROM core.fact_game_team
  WHERE home_away = 'home'
)
SELECT count(*) AS modelling_rows
FROM base AS b
LEFT JOIN home_stats AS h ON h.game_id = b.game_id;
```

Returns **1** row: the count of leak-free modelling rows (the ~6.5k gradeable 2019–2024 games, matching C4's n=6,492 base with a LEFT JOIN preserving all games). **How to read it.** LEFT JOIN keeps every game even when `fact_game_team` lacks a snapshot, so the count equals the `base` size; missing stats appear as NULL features to impute or flag, never as dropped rows.

### Exercises
1. Conform `stg.games` and `stg.game` into `sandbox.main.game_conformed` with `_provenance IN ('rest','gql','both')` via `UNION BY NAME`. *Hint: select a common column subset from each; add a literal provenance, then resolve any shared game key to a single row tagged `'both'`.*
2. Design `sandbox.main.fact_bet` (DDL): `bet_id`, `placed_at` (TIMESTAMPTZ, UTC), `game_id`, `market`, `side`, `line`, `odds`, `stake_units`, `result`, grain comment on top. *Hint: `CREATE TABLE ... ` in scratch.*
3. SCD-2 team-name table `sandbox.main.dim_team_scd` with `valid_from`/`valid_to`/`is_current`. *Hint: one row per name-version.*
4. Walk-forward over/under rule: bet over when trailing-2-season over rate > 0.52; write per (rule, season, week) to `sandbox.main.backtest_result`. *Hint: reuse C7.*
5. One-statement audit: `UNION ALL` of (duplicate game_ids), (orphan provider keys), (NULL start_dates), (stale schemas from `meta.load_report`), each returning `check_name, failing_rows`. *Hint: every subquery returns 0 rows when healthy.*

### Check yourself
`modelling_rows` should match `base`'s size because of the LEFT JOIN (verified ≈6,492 for 2019–2024). The audit statement returns zero rows in a clean warehouse; any row names the failing check.

### Common mistakes
- Inner-joining `fact_game_team` and silently dropping games without a snapshot.
- Building `fact_bet` without stating grain, then double-counting a two-sided bet.
- Letting the trailing over-rate include the test season (leak) — compute it as-of the prior seasons only.

---

# Part D — SQL best practices (reference)

No exercises. This is the standard you hold every saved query to. It is written for the CFB warehouse but the habits are portable.

## Layout and formatting

Pick one style and never mix. This course uses **lowercase keywords** with **one clause per line** and **trailing commas** in select lists. Lowercase keywords reduce visual noise and read like prose; the SQL parser does not care, so the only argument is human legibility, and lowercase wins for most modern teams. One clause per line (`select` / `from` / `where` / `group by` / `order by` each starting a line) means a diff shows exactly which clause changed — invaluable under version control. Trailing commas keep each column on its own line so adding or removing a column is a one-line change; the counter-argument (leading commas make it obvious when a comma is missing) is legitimate — either is fine, but decide once and apply it everywhere. Indent the body of each clause. Align `on` conditions under their `join`. A query you can scan in five seconds is a query you can trust.

## Naming

Use `snake_case` for everything; never quote mixed-case identifiers if you can avoid it. State grain in the table name: dimensions are prefixed `dim_` and are singular in spirit (`dim_team`, one row per team), facts are prefixed `fact_` and named for their grain (`fact_game` = one game, `fact_game_line` = one game×provider). Booleans read as assertions: `is_fbs`, `has_line`, `is_current`, `dome`, `grass` — a `where is_fbs` clause is self-documenting. Columns that are foreign keys end in `_id` (`home_team_id`), timestamps end in `_at` (`loaded_at`, `pulled_at`, `updated_at`), and dates carry their unit when ambiguous (`rest_days`). Consistency beats cleverness: if the warehouse already uses `provider_key`, do not invent `provider_id` in your scratch tables.

## Grain, CTEs, and structure

**Always state grain in a comment above every CTE and every saved table**: `-- grain: one row per team-game`. Grain is the contract; most analytical bugs are grain bugs (a fan-out you did not expect, a double count). Prefer CTEs over nested subqueries — `with` reads top-to-bottom as a pipeline, one idea per CTE, each independently testable by selecting from it. A five-CTE query where each CTE does one thing is far easier to debug than one query nested five deep. Name CTEs for what they produce (`graded`, `rolling`, `home_stats`), not `t1`, `t2`.

## Joins and projection

Use explicit `join ... on`; **never comma joins**, which hide the join condition in the `where` clause and invite accidental cross products. Make every join's intent obvious: `inner` when you require a match, `left` when the right side is optional (always `left join dim_team` — 44 away teams have no dimension row). **Never `select *` in anything you save** — a view or table built on `*` breaks silently when an upstream column is added or reordered; list columns explicitly. Exploratory `select *` at the REPL is fine; persisted `*` is a landmine. Project early: select only the columns you need before a join so the engine moves less data. Filter early: put selective predicates (`season = 2024`) before joins so fewer rows enter them.

## Fan-out and dedupe discipline

Guard fan-out with a row-count assertion whenever you expect one-to-one: after joining `fact_game` to a dimension, confirm the count did not grow. If it did, the dimension is not unique on the join key and you have silently multiplied rows — a class of bug that quietly corrupts every downstream average. Prefer `qualify` with a window `row_number()` over `distinct` for deduplication: `distinct` hides *why* rows duplicated and cannot express "keep the latest", whereas `qualify row_number() over (partition by key order by updated_at desc) = 1` states the tiebreak explicitly. Reach for `distinct` only for genuinely set-like questions ("distinct conferences"), never as a band-aid for a fan-out you did not diagnose.

## NULL and NaN discipline

Compare nullable columns with `is distinct from`, not `=`/`<>`, so two NULLs compare equal and a NULL-vs-value compares different. Use `coalesce` **only at the edge** — the final display or the input boundary — never mid-computation where it silently converts "unknown" into a fabricated value and biases aggregates. Remember NaN is not NULL: `coalesce(nan_col, 0)` returns NaN, and `nan_col is not null` is true; detect NaN with `isnan(x)` (DuckDB defines `NaN = NaN` as TRUE, unlike IEEE 754, so `x <> x` never fires). In this warehouse, GraphQL numerics can arrive as the string `"NaN"`; the loader nulls most, but verify rather than assume. When a rate could divide by zero, guard with `nullif(denominator, 0)`.

## Dates and timezones

Store timestamps as `timestamptz` in **UTC** and convert to a display timezone only at the presentation layer. The warehouse already does this — `fact_game.start_date`, `fact_game_odds.pulled_at`, and `an_history_tick.updated_at` are all `timestamp with time zone`. Kickoff-relative logic (rest days, as-of joins for closing lines) must compare timestamps in a single consistent zone; mixing local and UTC is how a "pre-game" tick sneaks in from after kickoff. Tag every engineered feature with its as-of timestamp so you can prove it predates the game.

## Idempotency, immutability, and provenance

Make scripts rerunnable: use `create or replace view/table/macro` so a second run does not error. Keep `raw` immutable — it is the replay log; never update or delete it, and never analyse from it. Every number that reaches a decision should be reproducible from a query under version control: commit the SQL that produced it, not just the result. When you merge two sources, carry a `_provenance` / `_source` marker (as `core.fact_game_line._source ∈ rest/gql/both` does) so you can always trace a row back. Write the data-quality test next to the model it protects, in the same file, so the test cannot rot separately from the query.

## Comments and performance

Comment the **why**, not the what: `-- exclude postseason: dim_week has one postseason row per season` is useful; `-- filter season type` merely restates the code. Performance basics, in order of impact: filter early and project early (already covered); avoid wrapping a join or filter column in a function (`where cast(start_date as date) = ...` defeats pruning — compare against a range instead); check `explain analyze` before optimising by guesswork; and prefer set-based logic over row-by-row simulation (a recursive bootstrap is fine, a correlated subquery per row is usually not).

## Anti-patterns, each with the fix

- **`select *` in a view.** Fix: list columns; the view survives upstream schema changes.
- **Comma join.** `from a, b where a.k=b.k` → **Fix:** `from a join b on a.k = b.k`.
- **Inner join to `dim_team`.** Drops 44 exotic opponents. **Fix:** `left join`, expect NULLs.
- **Joining games to `dim_week` on `(season, week)`.** Loses all postseason. **Fix:** add `season_type`, or handle postseason separately.
- **`where x = null`.** Never matches. **Fix:** `x is null`.
- **`coalesce(x, 0)` to "handle" NaN.** NaN passes through. **Fix:** detect with `isnan(x)` (DuckDB defines `NaN = NaN` as TRUE, unlike IEEE 754, so `x <> x` never fires).
- **`not in (subquery)` where the subquery can be NULL.** Returns nothing. **Fix:** `not exists`.
- **`distinct` to fix duplicate rows.** Hides the cause. **Fix:** diagnose the fan-out; dedupe with `qualify row_number()`.
- **Window frame ending at `current row` for a pre-game feature.** Leaks the result. **Fix:** end at `1 preceding`.
- **Choosing a betting rule after seeing all seasons.** In-sample overfit. **Fix:** walk-forward, judge out-of-sample.
- **Population stats (`stddev_pop`) for inference.** Understates uncertainty. **Fix:** `stddev_samp` / `var_samp`.
- **Writing to `cfb`.** It is read-only and errors. **Fix:** target `sandbox.main.<name>`.
- **Treating games as independent in a hypothesis test.** Clustering inflates significance. **Fix:** cluster by team-season or use a block bootstrap.

Follow these and every number you ship will be reproducible, leak-free, and portable off DuckDB the day you need it to be.

---

# Appendix — Verified warehouse reference card

Every figure below came from live introspection of `md:cfb` while writing this course; use it as a sanity anchor when your own queries produce something surprising.

| Fact | Value (live) |
|---|---|
| Schemas present | `raw` (167 tables), `stg` (185), `core` (30), `meta` (2), plus `marts` (18), `refs` (9), `staging` (3), `main` (9) |
| `core.fact_game` season range | 2012 – 2026 |
| 2024 regular-season games (`fact_game`) | 3,747 |
| Completed 2024 regular games (both scores) | 3,745 |
| 2024 postseason games (`fact_game`) | 54 |
| `core.fact_game_line` rows | 47,946 |
| Lines floor season (`has_line`) | 2013 |
| Lines with both open & close total | 7,291 |
| `core.fact_game_odds` rows | 86,640 |
| `stg.an_history_tick` rows | 410,845 |
| Odds-API history starts | 2026-09-09 |
| FBS teams in `dim_team` | 138 |
| `dim_week` postseason rows | 15 (one per season, 2012–2026 minus current-year gaps) |
| 2024 away teams missing from `dim_team` | 44 |
| 2024 regular-season game total: mean / sd / median | 52.56 / 17.62 / 52 |
| 2014–2024 margin exactly 3 or 7 | 15.82% |
| Actual-total vs market-total, 2019–24 (n / r / slope / intercept) | 6,492 / 0.3777 / 0.8517 / 8.5306 |

### A note on sources and citation

DuckDB dialect features are cited inline to `duckdb.org/docs/...` and MotherDuck behaviours to `motherduck.com/docs` at first appearance, per the brief. Statistical function names (`stddev_samp`, `regr_slope`, `corr`, `quantile_cont`, `erf`, etc.) are documented at `duckdb.org/docs/sql/functions/aggregates` and `.../functions/math`. Where I could not verify a specific documentation path or textbook edition, I marked it `[uncertain]` rather than invent a citation — notably the exact availability of `erf` in every DuckDB build (fall back to an Abramowitz–Stegun polynomial if your build lacks it). Standard-SQL features (window functions, `WITH RECURSIVE`, `GROUP BY ROLLUP`, `FILTER`) are ISO SQL and equivalently documented in the PostgreSQL manual; consult `postgresql.org/docs` when you need to confirm portability. Equation numbers [1]–[11] in Part C label formulas for in-text reference only and are not external citations.

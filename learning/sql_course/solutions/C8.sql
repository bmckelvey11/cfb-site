-- exercise: 1
-- check: probe
-- probe: SELECT _provenance, count(*) AS n FROM sandbox.main.game_conformed GROUP BY 1 ORDER BY 1
-- probe: SELECT count(*) FILTER (WHERE _provenance = 'both') AS n_both FROM sandbox.main.game_conformed
CREATE OR REPLACE TABLE sandbox.main.game_conformed AS
WITH rest AS (
  SELECT gameId AS game_id, season, week, startDate AS start_date
  FROM stg.games
),
gql AS (
  SELECT gameId AS game_id, season, week, startDate AS start_date
  FROM stg.game
)
SELECT
  coalesce(r.game_id, g.game_id) AS game_id,
  coalesce(r.season, g.season) AS season,
  coalesce(r.week, g.week) AS week,
  coalesce(r.start_date, g.start_date) AS start_date,
  CASE
    WHEN r.game_id IS NOT NULL AND g.game_id IS NOT NULL THEN 'both'
    WHEN r.game_id IS NOT NULL THEN 'rest'
    ELSE 'gql'
  END AS _provenance
FROM rest AS r
FULL OUTER JOIN gql AS g
  ON r.game_id = g.game_id;

-- exercise: 2
-- check: probe
-- probe: DESCRIBE sandbox.main.fact_bet
-- probe: SELECT constraint_type FROM duckdb_constraints() WHERE table_name = 'fact_bet' ORDER BY 1
-- grain: one row per placed bet
CREATE OR REPLACE TABLE sandbox.main.fact_bet (
  bet_id INTEGER PRIMARY KEY,
  placed_at TIMESTAMPTZ,
  game_id BIGINT,
  market TEXT,
  side TEXT,
  line DOUBLE,
  odds INTEGER,
  stake_units DOUBLE,
  result TEXT
);

-- exercise: 3
-- check: probe
-- probe: DESCRIBE sandbox.main.dim_team_scd
-- probe: SELECT constraint_type FROM duckdb_constraints() WHERE table_name = 'dim_team_scd' ORDER BY 1
CREATE OR REPLACE TABLE sandbox.main.dim_team_scd (
  team_id BIGINT,
  school TEXT,
  valid_from DATE,
  valid_to DATE,
  is_current BOOLEAN,
  PRIMARY KEY (team_id, valid_from)
);

-- exercise: 4
-- check: probe
-- probe: DESCRIBE sandbox.main.backtest_result
-- probe: SELECT count(*) AS n FROM sandbox.main.backtest_result
CREATE OR REPLACE TABLE sandbox.main.backtest_result AS
WITH graded AS (
  SELECT
    season,
    week,
    CASE WHEN home_points + away_points > selected_total THEN 1.0 ELSE 0.0 END AS went_over,
    CASE
      WHEN home_points + away_points > selected_total THEN 0.9091
      WHEN home_points + away_points = selected_total THEN 0.0
      ELSE -1.0
    END AS pnl
  FROM core.fact_game
  WHERE season BETWEEN 2015 AND 2024
    AND season_type = 'regular'
    AND selected_total IS NOT NULL
    AND home_points IS NOT NULL
    AND away_points IS NOT NULL
),
season_rate AS (
  SELECT season, avg(went_over) AS over_rate
  FROM graded
  GROUP BY season
),
trail AS (
  SELECT
    s.season AS test_season,
    avg(p.over_rate) AS trailing_2_rate
  FROM season_rate AS s
  JOIN season_rate AS p
    ON p.season IN (s.season - 1, s.season - 2)
  GROUP BY s.season
  HAVING count(*) = 2
)
SELECT
  'trail2_over_gt_052' AS rule,
  g.season,
  g.week,
  count(*) AS n_bets,
  round(sum(g.pnl), 2) AS net_units
FROM graded AS g
JOIN trail AS t ON t.test_season = g.season
WHERE t.trailing_2_rate > 0.52
GROUP BY g.season, g.week;

-- exercise: 5
-- check: exact
SELECT 'duplicate_game_ids' AS check_name, count(*) AS failing_rows
FROM (
  SELECT game_id FROM core.fact_game GROUP BY game_id HAVING count(*) > 1
)
UNION ALL
SELECT 'orphan_provider_keys', count(*)
FROM core.fact_game_line AS l
WHERE l.provider_key IS NOT NULL
  AND NOT EXISTS (
    SELECT 1 FROM core.dim_lines_provider AS p WHERE p.provider_key = l.provider_key
  )
UNION ALL
SELECT 'null_start_dates', count(*)
FROM core.fact_game
WHERE start_date IS NULL
UNION ALL
SELECT 'stale_schemas', count(*)
FROM (
  SELECT schema
  FROM meta.load_report
  GROUP BY schema
  HAVING max(loaded_at) < now() - INTERVAL '365 days'
);

-- exercise: 1
-- check: exact
-- note: ORDER BY table_schema, table_name — exercise does not pin row order.
SELECT table_schema, table_name
FROM information_schema.tables
WHERE table_schema = 'core'
ORDER BY table_schema, table_name;

-- exercise: 2
-- check: exact
-- note: ORDER BY ordinal_position so column order matches the table, not name.
SELECT column_name, data_type
FROM information_schema.columns
WHERE table_schema = 'core'
  AND table_name = 'fact_game_line'
ORDER BY ordinal_position;

-- exercise: 3
-- check: exact
SELECT
  game_id,
  home_team,
  away_team,
  home_points,
  away_points,
  home_points + away_points AS combined
FROM core.fact_game
WHERE season = 2023
  AND home_points IS NOT NULL
  AND away_points IS NOT NULL
ORDER BY home_points + away_points DESC, game_id
LIMIT 10;

-- exercise: 4
-- check: exact
SELECT schema, name, rows, loaded_at
FROM meta.load_report
ORDER BY loaded_at DESC
LIMIT 15;

-- exercise: 5
-- check: exact
-- note: ORDER BY seasonType — DISTINCT does not pin order.
SELECT DISTINCT seasonType
FROM stg.games
ORDER BY seasonType;

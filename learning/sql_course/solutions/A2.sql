-- exercise: 1
-- check: exact
-- note: First 20 2024 games with a total, ordered by game_id. Exercise does not pin which 20.
SELECT
  game_id,
  selected_total,
  CAST(selected_total AS INTEGER) AS selected_total_int
FROM core.fact_game
WHERE season = 2024
  AND selected_total IS NOT NULL
ORDER BY game_id
LIMIT 20;

-- exercise: 2
-- check: manual
SELECT
  avg(coalesce(home_points, 0)) AS avg_coalesce_zero,
  avg(home_points) AS avg_skip_null
FROM core.fact_game
WHERE season = 2024
  AND season_type = 'regular';

-- exercise: 3
-- check: exact
-- note: 2024 regular completed games; ratio is NULL when away_points is 0.
SELECT
  game_id,
  home_points,
  away_points,
  home_points * 1.0 / nullif(away_points, 0) AS home_away_ratio
FROM core.fact_game
WHERE season = 2024
  AND season_type = 'regular'
  AND home_points IS NOT NULL
  AND away_points IS NOT NULL
ORDER BY game_id;

-- exercise: 4
-- check: exact
SELECT
  game_id,
  home_conference,
  away_conference
FROM core.fact_game
WHERE season = 2024
  AND season_type = 'regular'
  AND home_conference IS DISTINCT FROM away_conference
ORDER BY game_id;

-- exercise: 5
-- check: exact
SELECT gameId, excitement
FROM stg.game
WHERE isnan(excitement)
ORDER BY gameId;

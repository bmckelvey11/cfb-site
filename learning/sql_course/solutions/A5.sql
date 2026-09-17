-- exercise: 1
-- check: exact
WITH season_avg AS (
  -- grain: one row, 2024 regular-season mean total
  SELECT avg(home_points + away_points) AS mean_total
  FROM core.fact_game
  WHERE season = 2024
    AND season_type = 'regular'
    AND home_points IS NOT NULL
    AND away_points IS NOT NULL
)
SELECT count(*) AS games_above_season_avg
FROM core.fact_game AS fg
CROSS JOIN season_avg AS sa
WHERE fg.season = 2024
  AND fg.season_type = 'regular'
  AND fg.home_points IS NOT NULL
  AND fg.away_points IS NOT NULL
  AND (fg.home_points + fg.away_points) > sa.mean_total;

-- exercise: 2
-- check: exact
SELECT DISTINCT fg.home_team_id
FROM core.fact_game AS fg
WHERE fg.season = 2024
  AND NOT EXISTS (
    SELECT 1
    FROM core.fact_game AS prior
    WHERE prior.season = 2023
      AND prior.home_team_id = fg.home_team_id
  )
ORDER BY fg.home_team_id;

-- exercise: 3
-- check: exact
-- note: 2024 regular-season games; prior count is home games only, same season.
SELECT
  fg.game_id,
  fg.home_team_id,
  fg.start_date,
  (
    SELECT count(*)
    FROM core.fact_game AS prior
    WHERE prior.home_team_id = fg.home_team_id
      AND prior.season = 2024
      AND prior.start_date < fg.start_date
  ) AS prior_home_games
FROM core.fact_game AS fg
WHERE fg.season = 2024
  AND fg.season_type = 'regular'
ORDER BY fg.game_id;

-- exercise: 4
-- check: exact
WITH RECURSIVE seasons AS (
  SELECT 2012 AS season
  UNION ALL
  SELECT season + 1
  FROM seasons
  WHERE season < 2026
)
SELECT season FROM seasons ORDER BY season;

-- exercise: 5
-- check: exact
WITH labeled AS (
  -- grain: one 2024 regular completed game with an over/under flag
  SELECT
    home_conference,
    CASE WHEN home_points + away_points > selected_total THEN 1.0 ELSE 0.0 END AS is_over
  FROM core.fact_game
  WHERE season = 2024
    AND season_type = 'regular'
    AND selected_total IS NOT NULL
    AND home_points IS NOT NULL
    AND away_points IS NOT NULL
    AND home_conference IS NOT NULL
),
agg AS (
  -- grain: one row per conference
  SELECT home_conference AS conference, avg(is_over) AS over_share
  FROM labeled
  GROUP BY home_conference
)
SELECT conference, over_share
FROM agg
ORDER BY conference;

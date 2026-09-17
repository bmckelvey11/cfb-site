-- exercise: 1
-- check: exact
WITH team_pts AS (
  -- grain: one row per team-game
  SELECT home_team_id AS team_id, home_conference AS conference, home_points AS pts
  FROM core.fact_game
  WHERE season = 2024 AND season_type = 'regular'
  UNION ALL
  SELECT away_team_id, away_conference, away_points
  FROM core.fact_game
  WHERE season = 2024 AND season_type = 'regular'
),
tot AS (
  -- grain: one row per team-conference
  SELECT team_id, conference, sum(pts) AS total_pts
  FROM team_pts
  WHERE conference IS NOT NULL
    AND pts IS NOT NULL
  GROUP BY team_id, conference
)
SELECT
  team_id,
  conference,
  total_pts,
  rank() OVER (PARTITION BY conference ORDER BY total_pts DESC) AS rnk
FROM tot
ORDER BY conference, rnk, team_id;

-- exercise: 2
-- check: exact
SELECT
  game_id,
  home_team_id,
  start_date,
  home_points + away_points AS actual_total,
  lag(home_points + away_points) OVER (
    PARTITION BY home_team_id ORDER BY start_date
  ) AS prev_home_game_total
FROM core.fact_game
WHERE season = 2024
  AND season_type = 'regular'
ORDER BY home_team_id, start_date;

-- exercise: 3
-- check: exact
WITH team_games AS (
  -- grain: one row per team-game
  SELECT game_id, start_date, home_team_id AS team_id
  FROM core.fact_game
  WHERE season = 2024 AND season_type = 'regular'
  UNION ALL
  SELECT game_id, start_date, away_team_id
  FROM core.fact_game
  WHERE season = 2024 AND season_type = 'regular'
)
SELECT
  team_id,
  game_id,
  start_date,
  count(*) OVER (PARTITION BY team_id ORDER BY start_date) AS games_played
FROM team_games
ORDER BY team_id, start_date, game_id;

-- exercise: 4
-- check: exact
WITH ranked AS (
  SELECT
    l.*,
    row_number() OVER (
      PARTITION BY l.game_id, l.provider_key
      ORDER BY (l.total_close IS NULL), l.game_id
    ) AS rn
  FROM core.fact_game_line AS l
)
SELECT *
FROM ranked
WHERE rn = 1
ORDER BY game_id, provider_key;

-- exercise: 5
-- check: manual
WITH team_games AS (
  SELECT game_id, start_date, home_team_id AS team_id, home_points AS points
  FROM core.fact_game
  WHERE season = 2024 AND season_type = 'regular'
  UNION ALL
  SELECT game_id, start_date, away_team_id, away_points
  FROM core.fact_game
  WHERE season = 2024 AND season_type = 'regular'
)
SELECT
  team_id,
  game_id,
  points,
  avg(points) OVER (
    PARTITION BY team_id ORDER BY start_date
    ROWS BETWEEN 3 PRECEDING AND CURRENT ROW
  ) AS leaking_avg,
  avg(points) OVER (
    PARTITION BY team_id ORDER BY start_date
    ROWS BETWEEN 3 PRECEDING AND 1 PRECEDING
  ) AS pregame_avg
FROM team_games
ORDER BY team_id, start_date
LIMIT 50;

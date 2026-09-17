-- exercise: 1
-- check: exact
-- note: ORDER BY game_id — FROM-first LIMIT 10 does not pin which 10.
FROM core.fact_game
SELECT home_team, away_team, game_id
WHERE season = 2024
ORDER BY game_id
LIMIT 10;

-- exercise: 2
-- check: exact
-- note: Bounded to 2024 regular so the star-projection stays gradeable.
SELECT * EXCLUDE (home_conference_id, away_conference_id)
FROM core.fact_game
WHERE season = 2024
  AND season_type = 'regular'
ORDER BY game_id;

-- exercise: 3
-- check: exact
-- note: Bounded to 2024 regular; REPLACE rounds selected_total in place.
SELECT * REPLACE (round(selected_total, 0) AS selected_total)
FROM core.fact_game
WHERE season = 2024
  AND season_type = 'regular'
ORDER BY game_id;

-- exercise: 4
-- check: exact
SELECT
  season,
  home_conference,
  avg(home_points + away_points) AS avg_total
FROM core.fact_game
WHERE season_type = 'regular'
  AND home_points IS NOT NULL
  AND away_points IS NOT NULL
  AND home_conference IS NOT NULL
GROUP BY ALL
ORDER BY ALL;

-- exercise: 5
-- check: exact
SELECT game_id, season, week, start_date, team_id, points
FROM (
  SELECT game_id, season, week, start_date, home_team_id AS team_id, home_points AS points
  FROM core.fact_game
  WHERE season = 2024 AND season_type = 'regular'
)
UNION BY NAME
SELECT game_id, season, week, start_date, points, team_id
FROM (
  SELECT game_id, season, week, start_date, away_team_id AS team_id, away_points AS points
  FROM core.fact_game
  WHERE season = 2024 AND season_type = 'regular'
)
ORDER BY game_id, team_id;

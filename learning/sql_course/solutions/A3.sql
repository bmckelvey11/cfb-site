-- exercise: 1
-- check: exact
SELECT
  season,
  count(*) AS n_games,
  avg(selected_total) AS avg_selected_total
FROM core.fact_game
WHERE season BETWEEN 2013 AND 2024
  AND season_type = 'regular'
GROUP BY season
ORDER BY season;

-- exercise: 2
-- check: exact
SELECT
  home_conference AS conference,
  count(DISTINCT home_team_id) AS n_home_teams
FROM core.fact_game
WHERE season = 2024
  AND home_conference IS NOT NULL
GROUP BY home_conference
ORDER BY conference;

-- exercise: 3
-- check: exact
SELECT
  season,
  avg(CASE WHEN home_points > away_points THEN 1.0 ELSE 0.0 END) AS home_win_rate
FROM core.fact_game
WHERE home_points IS NOT NULL
  AND away_points IS NOT NULL
GROUP BY season
ORDER BY season;

-- exercise: 4
-- check: exact
SELECT
  home_conference AS conference,
  avg(home_points + away_points) AS avg_total
FROM core.fact_game
WHERE season = 2024
  AND season_type = 'regular'
  AND home_points IS NOT NULL
  AND away_points IS NOT NULL
  AND home_conference IS NOT NULL
GROUP BY home_conference
HAVING avg(home_points + away_points) > 55
ORDER BY conference;

-- exercise: 5
-- check: exact
-- note: 2013–2024 regular season; ROLLUP emits NULL conference for season subtotals.
SELECT
  season,
  home_conference,
  avg(home_points + away_points) AS avg_total
FROM core.fact_game
WHERE season BETWEEN 2013 AND 2024
  AND season_type = 'regular'
  AND home_points IS NOT NULL
  AND away_points IS NOT NULL
GROUP BY ROLLUP (season, home_conference)
ORDER BY season, home_conference;

-- exercise: 1
-- check: manual
EXPLAIN ANALYZE
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

-- exercise: 2
-- check: probe
-- probe: SELECT sandbox.main.american_to_prob(-100)
-- probe: SELECT sandbox.main.american_to_prob(150)
-- probe: SELECT sandbox.main.american_to_prob(0)
CREATE OR REPLACE MACRO sandbox.main.american_to_prob(odds) AS (
  CASE
    WHEN odds IS NULL OR odds = 0 THEN NULL
    WHEN odds < 0 THEN (-odds)::DOUBLE / ((-odds) + 100)
    ELSE 100.0 / (odds + 100)
  END
);

-- exercise: 3
-- check: probe
-- probe: SELECT * FROM sandbox.main.season_games(2024)
-- probe: SELECT * FROM sandbox.main.season_games(2023)
CREATE OR REPLACE MACRO sandbox.main.season_games(yr) AS TABLE (
  SELECT * FROM cfb.core.fact_game WHERE season = yr
);

-- exercise: 4
-- check: manual
COPY (
  SELECT
    game_id,
    home_points + away_points AS actual_total,
    selected_total
  FROM core.fact_game
  WHERE season = 2024
    AND season_type = 'regular'
    AND home_points IS NOT NULL
    AND away_points IS NOT NULL
) TO 'data/games_2024.parquet' (FORMAT parquet);

-- exercise: 5
-- check: manual
SHOW DATABASES;

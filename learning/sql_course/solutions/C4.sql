-- exercise: 1
-- check: exact
SELECT corr(t.win_pct, fg.home_points - fg.away_points) AS r
FROM core.fact_game AS fg
JOIN core.fact_game_team AS t
  ON t.game_id = fg.game_id
 AND t.home_away = 'home'
WHERE fg.season BETWEEN 2019 AND 2024
  AND fg.season_type = 'regular'
  AND fg.home_points IS NOT NULL
  AND fg.away_points IS NOT NULL
  AND t.win_pct IS NOT NULL;

-- exercise: 2
-- check: exact
WITH base AS (
  SELECT
    game_id,
    selected_total,
    home_points + away_points AS actual
  FROM core.fact_game
  WHERE season BETWEEN 2019 AND 2024
    AND season_type = 'regular'
    AND selected_total IS NOT NULL
    AND home_points IS NOT NULL
    AND away_points IS NOT NULL
),
fit AS (
  SELECT
    regr_slope(actual, selected_total) AS slope,
    regr_intercept(actual, selected_total) AS intercept
  FROM base
)
SELECT
  b.game_id,
  b.actual - (f.intercept + f.slope * b.selected_total) AS residual
FROM base AS b
CROSS JOIN fit AS f
ORDER BY b.game_id;

-- exercise: 3
-- check: exact
WITH base AS (
  SELECT
    t.win_pct,
    tal.talent,
    fg.home_points - fg.away_points AS margin
  FROM core.fact_game AS fg
  JOIN core.fact_game_team AS t
    ON t.game_id = fg.game_id AND t.home_away = 'home'
  JOIN core.fact_team_talent AS tal
    ON tal.team_id = fg.home_team_id AND tal.season = fg.season
  WHERE fg.season BETWEEN 2019 AND 2024
    AND fg.season_type = 'regular'
    AND fg.home_points IS NOT NULL
    AND fg.away_points IS NOT NULL
    AND t.win_pct IS NOT NULL
    AND tal.talent IS NOT NULL
),
fit AS (
  SELECT
    regr_slope(talent, win_pct) AS talent_slope,
    regr_intercept(talent, win_pct) AS talent_int,
    regr_slope(margin, win_pct) AS margin_slope,
    regr_intercept(margin, win_pct) AS margin_int
  FROM base
)
SELECT corr(
  b.talent - (f.talent_int + f.talent_slope * b.win_pct),
  b.margin - (f.margin_int + f.margin_slope * b.win_pct)
) AS partial_r
FROM base AS b
CROSS JOIN fit AS f;

-- exercise: 4
-- check: manual
SELECT corr(sg.excitement, fg.home_points - fg.away_points) AS leaked_r
FROM core.fact_game AS fg
JOIN stg.game AS sg
  ON sg.gameId = fg.game_id
WHERE fg.season = 2024
  AND fg.season_type = 'regular'
  AND fg.home_points IS NOT NULL
  AND sg.excitement IS NOT NULL;

-- exercise: 5
-- check: exact
SELECT
  season,
  regr_r2(home_points + away_points, selected_total) AS r2
FROM core.fact_game
WHERE season_type = 'regular'
  AND selected_total IS NOT NULL
  AND home_points IS NOT NULL
  AND away_points IS NOT NULL
GROUP BY season
ORDER BY season;

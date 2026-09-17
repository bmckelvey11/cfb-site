-- exercise: 1
-- check: exact
WITH graded AS (
  SELECT
    CASE WHEN (home_points - away_points) + selected_spread > 0 THEN 1.0 ELSE 0.0 END AS home_cover
  FROM core.fact_game
  WHERE season BETWEEN 2014 AND 2024
    AND season_type = 'regular'
    AND selected_spread IS NOT NULL
    AND home_points IS NOT NULL
    AND away_points IS NOT NULL
    AND (home_points - away_points) + selected_spread <> 0
)
SELECT
  count(*) AS n,
  round(avg(home_cover), 4) AS cover_rate,
  round(sqrt(avg(home_cover) * (1 - avg(home_cover)) / count(*)), 4) AS se,
  round(avg(home_cover) - 1.96 * sqrt(avg(home_cover) * (1 - avg(home_cover)) / count(*)), 4) AS ci_low,
  round(avg(home_cover) + 1.96 * sqrt(avg(home_cover) * (1 - avg(home_cover)) / count(*)), 4) AS ci_high
FROM graded;

-- exercise: 2
-- check: exact
SELECT
  approx_count_distinct(game_id) AS approx_n,
  count(DISTINCT game_id) AS exact_n
FROM core.fact_game_line;

-- exercise: 3
-- check: manual
SELECT avg(CASE WHEN home_points + away_points > selected_total THEN 1.0 ELSE 0.0 END) AS over_rate
FROM core.fact_game
WHERE season = 2024
  AND season_type = 'regular'
  AND selected_total IS NOT NULL
  AND home_points IS NOT NULL
  AND away_points IS NOT NULL
USING SAMPLE 10%;

-- exercise: 4
-- check: manual
WITH graded AS (
  SELECT CASE WHEN home_points + away_points > selected_total THEN 1.0 ELSE 0.0 END AS went_over
  FROM core.fact_game
  WHERE season = 2024
    AND season_type = 'regular'
    AND selected_total IS NOT NULL
    AND home_points IS NOT NULL
    AND away_points IS NOT NULL
),
indexed AS (
  SELECT went_over, row_number() OVER () AS rn, count(*) OVER () AS n
  FROM graded
),
boot AS (
  SELECT s.i, avg(idx.went_over) AS over_rate
  FROM generate_series(1, 1000) AS s(i)
  JOIN indexed AS idx
    ON idx.rn = 1 + floor(random() * idx.n)
  GROUP BY s.i
)
SELECT i, over_rate FROM boot ORDER BY i;

-- exercise: 5
-- check: manual
WITH graded AS (
  SELECT CASE WHEN home_points + away_points > selected_total THEN 1.0 ELSE 0.0 END AS went_over
  FROM core.fact_game
  WHERE season BETWEEN 2014 AND 2024
    AND season_type = 'regular'
    AND selected_total IS NOT NULL
    AND home_points IS NOT NULL
    AND away_points IS NOT NULL
),
indexed AS (
  SELECT went_over, row_number() OVER () AS rn, count(*) OVER () AS n
  FROM graded
),
boot AS (
  SELECT s.i, avg(idx.went_over) AS over_rate
  FROM generate_series(1, 200) AS s(i)
  JOIN indexed AS idx
    ON idx.rn = 1 + floor(random() * idx.n)
  GROUP BY s.i
)
SELECT
  (SELECT sqrt(avg(went_over) * (1 - avg(went_over)) / count(*)) FROM graded) AS analytic_se,
  (SELECT stddev_samp(over_rate) FROM boot) AS bootstrap_sd;

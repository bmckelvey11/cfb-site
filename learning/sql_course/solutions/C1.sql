-- exercise: 1
-- check: exact
SELECT
  floor((home_points + away_points) / 5) AS total_bin,
  count(*) AS n
FROM core.fact_game
WHERE season = 2024
  AND season_type = 'regular'
  AND home_points IS NOT NULL
  AND away_points IS NOT NULL
GROUP BY 1
ORDER BY 1;

-- exercise: 2
-- check: exact
SELECT
  round(skewness(home_points - away_points), 4) AS margin_skew,
  round(kurtosis(home_points - away_points), 4) AS margin_kurtosis
FROM core.fact_game
WHERE season BETWEEN 2014 AND 2024
  AND season_type = 'regular'
  AND home_points IS NOT NULL
  AND away_points IS NOT NULL;

-- exercise: 3
-- check: exact
SELECT
  avg(CASE WHEN abs(home_points - away_points) IN (3, 7) THEN 1.0 ELSE 0 END) AS frac_key_number
FROM core.fact_game
WHERE season BETWEEN 2014 AND 2024
  AND season_type = 'regular'
  AND home_points IS NOT NULL
  AND away_points IS NOT NULL;

-- exercise: 4
-- check: exact
SELECT mode(selected_total) AS modal_total
FROM core.fact_game
WHERE season = 2024
  AND selected_total IS NOT NULL;

-- exercise: 5
-- check: exact
SELECT
  dv.dome,
  avg(fg.home_points + fg.away_points) AS mean_total,
  stddev_samp(fg.home_points + fg.away_points) AS sd_total
FROM core.fact_game AS fg
LEFT JOIN core.dim_venue AS dv
  ON fg.venue_id = dv.venue_id
WHERE fg.season = 2024
  AND fg.season_type = 'regular'
  AND fg.home_points IS NOT NULL
  AND fg.away_points IS NOT NULL
GROUP BY dv.dome
ORDER BY dv.dome;

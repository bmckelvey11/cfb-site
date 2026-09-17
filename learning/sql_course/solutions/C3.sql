-- exercise: 1
-- check: exact
WITH graded AS (
  SELECT
    CASE WHEN (home_points - away_points) + selected_spread > 0 THEN 1 ELSE 0 END AS home_cover,
    CASE WHEN (home_points - away_points) + selected_spread = 0 THEN 1 ELSE 0 END AS push
  FROM core.fact_game
  WHERE season BETWEEN 2014 AND 2024
    AND season_type = 'regular'
    AND selected_spread IS NOT NULL
    AND home_points IS NOT NULL
    AND away_points IS NOT NULL
),
zrow AS (
  SELECT
    (avg(home_cover) FILTER (WHERE push = 0) - 0.5)
    / sqrt(0.25 / sum(1) FILTER (WHERE push = 0)) AS z
  FROM graded
)
SELECT
  z,
  2 * (
    0.3989423 * exp(-(abs(z) * abs(z)) / 2)
    * (t * (0.319381530 + t * (-0.356563782 + t * (1.781477937 + t * (-1.821255978 + t * 1.330274429)))))
  ) AS p_value
FROM zrow
CROSS JOIN LATERAL (SELECT 1.0 / (1 + 0.2316419 * abs(z)) AS t) AS _;

-- exercise: 2
-- check: exact
WITH g AS (
  SELECT
    CASE WHEN season BETWEEN 2014 AND 2018 THEN 'early' ELSE 'late' END AS era,
    home_points + away_points AS total
  FROM core.fact_game
  WHERE season BETWEEN 2014 AND 2024
    AND season_type = 'regular'
    AND home_points IS NOT NULL
    AND away_points IS NOT NULL
),
s AS (
  SELECT era, avg(total) AS mu, var_samp(total) AS v, count(*) AS n
  FROM g
  GROUP BY era
)
SELECT (e.mu - l.mu) / sqrt(e.v / e.n + l.v / l.n) AS welch_t
FROM s AS e
JOIN s AS l ON e.era = 'early' AND l.era = 'late';

-- exercise: 3
-- check: exact
WITH top4 AS (
  SELECT home_conference
  FROM core.fact_game
  WHERE season = 2024 AND season_type = 'regular' AND home_conference IS NOT NULL
  GROUP BY home_conference
  ORDER BY count(*) DESC
  LIMIT 4
),
base AS (
  SELECT
    fg.home_conference,
    CASE WHEN fg.home_points + fg.away_points > fg.selected_total THEN 'over' ELSE 'under' END AS ou
  FROM core.fact_game AS fg
  JOIN top4 ON top4.home_conference = fg.home_conference
  WHERE fg.season = 2024
    AND fg.season_type = 'regular'
    AND fg.selected_total IS NOT NULL
    AND fg.home_points IS NOT NULL
    AND fg.away_points IS NOT NULL
),
obs AS (
  SELECT home_conference, ou, count(*) AS n
  FROM base
  GROUP BY 1, 2
),
tot AS (
  SELECT
    n,
    sum(n) OVER (PARTITION BY home_conference) AS row_tot,
    sum(n) OVER (PARTITION BY ou) AS col_tot,
    sum(n) OVER () AS grand
  FROM obs
)
SELECT round(sum(pow(n - row_tot * col_tot / grand, 2) / (row_tot * col_tot / grand)), 4) AS chi_sq
FROM tot;

-- exercise: 4
-- check: exact
WITH g AS (
  SELECT
    dv.dome,
    CASE WHEN fg.home_points + fg.away_points > fg.selected_total THEN 1.0 ELSE 0.0 END AS went_over
  FROM core.fact_game AS fg
  LEFT JOIN core.dim_venue AS dv ON fg.venue_id = dv.venue_id
  WHERE fg.season BETWEEN 2014 AND 2024
    AND fg.season_type = 'regular'
    AND fg.selected_total IS NOT NULL
    AND fg.home_points IS NOT NULL
    AND fg.away_points IS NOT NULL
    AND dv.dome IS NOT NULL
),
s AS (
  SELECT dome, avg(went_over) AS p, count(*) AS n
  FROM g
  GROUP BY dome
)
SELECT (a.p - b.p) / sqrt(pp * (1 - pp) * (1.0 / a.n + 1.0 / b.n)) AS z
FROM s AS a
JOIN s AS b ON a.dome = TRUE AND b.dome = FALSE
CROSS JOIN (SELECT avg(went_over) AS pp FROM g) AS pooled;

-- exercise: 5
-- check: exact
WITH g AS (
  SELECT
    home_conference,
    CASE WHEN home_points + away_points > selected_total THEN 1.0 ELSE 0.0 END AS went_over
  FROM core.fact_game
  WHERE season BETWEEN 2014 AND 2024
    AND season_type = 'regular'
    AND selected_total IS NOT NULL
    AND home_points IS NOT NULL
    AND away_points IS NOT NULL
    AND home_conference IS NOT NULL
),
s AS (
  SELECT
    home_conference,
    (avg(went_over) - 0.5) / sqrt(0.25 / count(*)) AS z
  FROM g
  GROUP BY home_conference
  HAVING count(*) >= 50
)
SELECT count(*) AS n_sig
FROM s
WHERE abs(z) > 1.96;

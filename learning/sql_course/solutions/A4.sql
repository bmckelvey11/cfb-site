-- exercise: 1
-- check: exact
SELECT
  fg.game_id,
  fg.home_team,
  fg.away_team,
  dv.city,
  dv.state
FROM core.fact_game AS fg
LEFT JOIN core.dim_venue AS dv
  ON fg.venue_id = dv.venue_id
WHERE fg.season = 2024
ORDER BY fg.game_id;

-- exercise: 2
-- check: exact
SELECT
  (SELECT count(*)
   FROM core.fact_game AS fg
   JOIN core.dim_week AS dw
     ON fg.season = dw.season AND fg.week = dw.week) AS joined_season_week,
  (SELECT count(*)
   FROM core.fact_game AS fg
   JOIN core.dim_week AS dw
     ON fg.season = dw.season
    AND fg.week = dw.week
    AND fg.season_type = dw.season_type) AS joined_with_season_type;

-- exercise: 3
-- check: exact
SELECT
  a.game_id AS game_id_a,
  b.game_id AS game_id_b,
  a.start_date
FROM core.fact_game AS a
JOIN core.fact_game AS b
  ON a.start_date = b.start_date
 AND a.game_id < b.game_id
ORDER BY a.start_date, a.game_id, b.game_id;

-- exercise: 4
-- check: exact
SELECT
  coalesce(r.game_id, g.game_id) AS game_id,
  r.game_id AS rest_game_id,
  g.game_id AS gql_game_id
FROM (
  SELECT DISTINCT game_id
  FROM core.fact_game_line
  WHERE _source = 'rest'
) AS r
FULL OUTER JOIN (
  SELECT DISTINCT game_id
  FROM core.fact_game_line
  WHERE _source = 'gql'
) AS g
  ON r.game_id = g.game_id
WHERE r.game_id IS NULL
   OR g.game_id IS NULL
ORDER BY 1;

-- exercise: 5
-- check: exact
SELECT
  (SELECT count(*) FROM core.fact_game) AS fact_game_rows,
  (SELECT count(*)
   FROM core.fact_game AS fg
   JOIN core.dim_team AS t
     ON fg.home_team_id = t.team_id) AS joined_rows;

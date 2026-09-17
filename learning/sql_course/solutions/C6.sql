-- exercise: 1
-- check: exact
WITH RECURSIVE numbered AS (
  SELECT
    team_id, game_id, start_date, points,
    row_number() OVER (PARTITION BY team_id ORDER BY start_date, game_id) AS rn
  FROM (
    SELECT game_id, start_date, home_team_id AS team_id, home_points AS points
    FROM core.fact_game
    WHERE season = 2024 AND season_type = 'regular' AND home_points IS NOT NULL
    UNION ALL
    SELECT game_id, start_date, away_team_id, away_points
    FROM core.fact_game
    WHERE season = 2024 AND season_type = 'regular' AND away_points IS NOT NULL
  )
),
ewma AS (
  SELECT team_id, game_id, start_date, points, rn, points::DOUBLE AS ewma_pts
  FROM numbered
  WHERE rn = 1
  UNION ALL
  SELECT n.team_id, n.game_id, n.start_date, n.points, n.rn,
         0.3 * n.points + 0.7 * e.ewma_pts
  FROM numbered AS n
  JOIN ewma AS e
    ON n.team_id = e.team_id AND n.rn = e.rn + 1
)
SELECT team_id, game_id, start_date, points, ewma_pts
FROM ewma
ORDER BY team_id, rn;

-- exercise: 2
-- check: exact
WITH team_games AS (
  SELECT game_id, start_date, home_team_id AS team_id, away_points AS pts_allowed
  FROM core.fact_game
  WHERE season = 2024 AND season_type = 'regular' AND away_points IS NOT NULL
  UNION ALL
  SELECT game_id, start_date, away_team_id, home_points
  FROM core.fact_game
  WHERE season = 2024 AND season_type = 'regular' AND home_points IS NOT NULL
)
SELECT
  team_id,
  game_id,
  start_date,
  avg(pts_allowed) OVER (
    PARTITION BY team_id ORDER BY start_date
    ROWS BETWEEN 3 PRECEDING AND 1 PRECEDING
  ) AS pregame_pts_allowed_l3
FROM team_games
ORDER BY team_id, start_date, game_id;

-- exercise: 3
-- check: exact
WITH team_games AS (
  SELECT
    game_id, start_date, season,
    home_team_id AS team_id,
    away_team_id AS opp_id,
    home_points AS pts_scored
  FROM core.fact_game
  WHERE season = 2024 AND season_type = 'regular' AND home_points IS NOT NULL
  UNION ALL
  SELECT
    game_id, start_date, season,
    away_team_id, home_team_id, away_points
  FROM core.fact_game
  WHERE season = 2024 AND season_type = 'regular' AND away_points IS NOT NULL
),
allowed AS (
  SELECT
    team_id AS opp_id,
    start_date,
    avg(pts_allowed) OVER (
      PARTITION BY team_id ORDER BY start_date
      ROWS BETWEEN UNBOUNDED PRECEDING AND 1 PRECEDING
    ) AS opp_pts_allowed_asof
  FROM (
    SELECT team_id, start_date, pts_allowed
    FROM (
      SELECT home_team_id AS team_id, start_date, away_points AS pts_allowed
      FROM core.fact_game
      WHERE season = 2024 AND season_type = 'regular'
      UNION ALL
      SELECT away_team_id, start_date, home_points
      FROM core.fact_game
      WHERE season = 2024 AND season_type = 'regular'
    )
  )
)
SELECT
  tg.team_id,
  tg.game_id,
  tg.pts_scored - a.opp_pts_allowed_asof AS adj_scoring
FROM team_games AS tg
LEFT JOIN allowed AS a
  ON a.opp_id = tg.opp_id AND a.start_date = tg.start_date
ORDER BY tg.team_id, tg.start_date, tg.game_id;

-- exercise: 4
-- check: exact
-- note: dim_venue has no lat/long; coordinates come from stg.venues.
WITH team_games AS (
  SELECT
    fg.game_id, fg.start_date, fg.home_team_id AS team_id, fg.venue_id
  FROM core.fact_game AS fg
  WHERE fg.season = 2024 AND fg.season_type = 'regular'
  UNION ALL
  SELECT fg.game_id, fg.start_date, fg.away_team_id, fg.venue_id
  FROM core.fact_game AS fg
  WHERE fg.season = 2024 AND fg.season_type = 'regular'
),
geo AS (
  SELECT
    tg.*,
    v.latitude,
    v.longitude,
    lag(v.latitude) OVER (PARTITION BY tg.team_id ORDER BY tg.start_date) AS prev_lat,
    lag(v.longitude) OVER (PARTITION BY tg.team_id ORDER BY tg.start_date) AS prev_lon
  FROM team_games AS tg
  LEFT JOIN stg.venues AS v ON v.venueId = tg.venue_id
)
SELECT
  game_id,
  team_id,
  2 * 3958.8 * asin(sqrt(
    pow(sin(radians(latitude - prev_lat) / 2), 2)
    + cos(radians(prev_lat)) * cos(radians(latitude))
    * pow(sin(radians(longitude - prev_lon) / 2), 2)
  )) AS miles
FROM geo
WHERE prev_lat IS NOT NULL AND latitude IS NOT NULL
ORDER BY team_id, start_date, game_id;

-- exercise: 5
-- check: manual
SELECT
  'pregame_avg_pts_last3' AS feature,
  'safe' AS lookahead_flag
UNION ALL
SELECT 'rolling_including_current_row', 'result_lookahead'
UNION ALL
SELECT 'excitement', 'result_lookahead';

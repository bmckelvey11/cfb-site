-- exercise: 1
-- check: exact
-- note: Opener vs close spread for game_id 401628319 (min 2024 regular game with a line).
SELECT provider_key, spread_open, spread_close
FROM core.fact_game_line
WHERE game_id = 401628319
ORDER BY provider_key;

-- exercise: 2
-- check: exact
-- note: 2026 games linked to AN events on (season, week, start_time); rn=1 breaks remaining ties.
WITH linked AS (
  SELECT
    g.game_id,
    g.start_date,
    sb.event_id,
    row_number() OVER (PARTITION BY g.game_id ORDER BY sb.event_id) AS rn
  FROM core.fact_game AS g
  JOIN stg.an_scoreboard AS sb
    ON sb.season = g.season
   AND sb.week = g.week
   AND sb.start_time = g.start_date
  WHERE g.season = 2026
    AND g.season_type = 'regular'
)
SELECT
  g.game_id,
  t.line AS last_total_tick,
  t.updated_at
FROM linked AS g
ASOF JOIN (
  SELECT event_id, updated_at, line
  FROM stg.an_history_tick
  WHERE market_type = 'total'
    AND side = 'over'
    AND period = 'event'
) AS t
  ON t.event_id = g.event_id
 AND t.updated_at <= g.start_date
WHERE g.rn = 1
ORDER BY g.game_id;

-- exercise: 3
-- check: exact
-- note: 6-hour buckets for event_id 287968 (the busiest total-market event).
SELECT
  time_bucket(INTERVAL '6 hours', updated_at) AS bucket,
  count(*) AS n_ticks,
  avg(line) AS avg_line
FROM stg.an_history_tick
WHERE event_id = 287968
  AND market_type = 'total'
  AND period = 'event'
GROUP BY 1
ORDER BY 1;

-- exercise: 4
-- check: exact
-- note: RANGE 24h average on event_id 287968 total ticks.
SELECT
  event_id,
  updated_at,
  line,
  avg(line) OVER (
    PARTITION BY event_id
    ORDER BY updated_at
    RANGE BETWEEN INTERVAL '24 hours' PRECEDING AND CURRENT ROW
  ) AS avg_line_24h
FROM stg.an_history_tick
WHERE event_id = 287968
  AND market_type = 'total'
  AND period = 'event'
ORDER BY updated_at;

-- exercise: 5
-- check: exact
SELECT
  count(*) FILTER (WHERE total_close > total_open) AS moved_up,
  count(*) FILTER (WHERE total_close < total_open) AS moved_down
FROM core.fact_game_line AS l
JOIN core.fact_game AS g
  ON g.game_id = l.game_id
WHERE g.season = 2024
  AND g.season_type = 'regular'
  AND l.total_close IS NOT NULL
  AND l.total_open IS NOT NULL;

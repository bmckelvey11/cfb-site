-- exercise: 1
-- check: exact
SELECT
  count(*) FILTER (WHERE selected_spread < 0) AS home_favourites,
  count(*) FILTER (WHERE selected_spread > 0) AS home_underdogs
FROM core.fact_game
WHERE season = 2024
  AND season_type = 'regular'
  AND selected_spread IS NOT NULL;

-- exercise: 2
-- check: exact
SELECT event_id, book_id, period, market_type, side, updated_at, line, odds
FROM stg.an_history_tick
WHERE market_type = 'spread'
  AND period = 'event'
QUALIFY row_number() OVER (PARTITION BY event_id ORDER BY updated_at DESC) = 1
ORDER BY event_id;

-- exercise: 3
-- check: exact
SELECT
  home_conference AS conference,
  arg_max(home_team, home_points) AS top_scoring_home_team,
  max(home_points) AS max_home_points
FROM core.fact_game
WHERE season = 2024
  AND season_type = 'regular'
  AND home_conference IS NOT NULL
  AND home_points IS NOT NULL
GROUP BY home_conference
ORDER BY conference;

-- exercise: 4
-- check: exact
SELECT
  game_id,
  list_distinct(list(provider_key)) AS providers
FROM core.fact_game_line
GROUP BY game_id
ORDER BY game_id;

-- exercise: 5
-- check: exact
-- note: PIVOT of total_close for game_id 401628319 (min 2024 regular game with a line).
PIVOT (
  SELECT provider_key, total_close
  FROM core.fact_game_line
  WHERE game_id = 401628319
)
ON provider_key
USING first(total_close);

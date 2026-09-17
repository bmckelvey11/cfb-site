-- exercise: 1
-- check: exact
SELECT
  l.game_id,
  ih / (ih + ia) AS no_vig_home
FROM (
  SELECT
    game_id,
    CASE WHEN moneyline_home < 0
         THEN (-moneyline_home)::DOUBLE / ((-moneyline_home) + 100)
         ELSE 100.0 / (moneyline_home + 100)
    END AS ih,
    CASE WHEN moneyline_away < 0
         THEN (-moneyline_away)::DOUBLE / ((-moneyline_away) + 100)
         ELSE 100.0 / (moneyline_away + 100)
    END AS ia
  FROM core.fact_game_line
  WHERE moneyline_home IS NOT NULL
    AND moneyline_away IS NOT NULL
) AS l
JOIN core.fact_game AS g ON g.game_id = l.game_id
WHERE g.season BETWEEN 2015 AND 2024
  AND g.season_type = 'regular'
ORDER BY l.game_id, no_vig_home;

-- exercise: 2
-- check: exact
-- note: Model p is the no-vig implied home probability; EV of a 1-unit home moneyline bet.
SELECT
  l.game_id,
  p * (d - 1) - (1 - p) AS ev
FROM (
  SELECT
    game_id,
    moneyline_home,
    CASE WHEN moneyline_home < 0
         THEN 1 + 100.0 / abs(moneyline_home)
         ELSE 1 + moneyline_home / 100.0
    END AS d,
    CASE WHEN moneyline_home < 0
         THEN (-moneyline_home)::DOUBLE / ((-moneyline_home) + 100)
         ELSE 100.0 / (moneyline_home + 100)
    END AS p
  FROM core.fact_game_line
  WHERE moneyline_home IS NOT NULL
) AS l
JOIN core.fact_game AS g ON g.game_id = l.game_id
WHERE g.season = 2024
  AND g.season_type = 'regular'
ORDER BY l.game_id, ev;

-- exercise: 3
-- check: exact
SELECT
  l.game_id,
  greatest(
    (p * (d - 1) - (1 - p)) / (d - 1),
    0
  ) AS kelly
FROM (
  SELECT
    game_id,
    CASE WHEN moneyline_home < 0
         THEN 1 + 100.0 / abs(moneyline_home)
         ELSE 1 + moneyline_home / 100.0
    END AS d,
    CASE WHEN moneyline_home < 0
         THEN (-moneyline_home)::DOUBLE / ((-moneyline_home) + 100)
         ELSE 100.0 / (moneyline_home + 100)
    END AS p
  FROM core.fact_game_line
  WHERE moneyline_home IS NOT NULL
    AND moneyline_home <> 0
) AS l
JOIN core.fact_game AS g ON g.game_id = l.game_id
WHERE g.season = 2024
  AND g.season_type = 'regular'
  AND d > 1
ORDER BY l.game_id, kelly;

-- exercise: 4
-- check: exact
SELECT
  avg(pow(implied - home_win, 2)) AS brier
FROM (
  SELECT
    CASE WHEN l.moneyline_home < 0
         THEN (-l.moneyline_home)::DOUBLE / ((-l.moneyline_home) + 100)
         ELSE 100.0 / (l.moneyline_home + 100)
    END AS implied,
    CASE WHEN g.home_points > g.away_points THEN 1.0 ELSE 0.0 END AS home_win
  FROM core.fact_game_line AS l
  JOIN core.fact_game AS g ON g.game_id = l.game_id
  WHERE g.season BETWEEN 2015 AND 2024
    AND g.season_type = 'regular'
    AND l.moneyline_home IS NOT NULL
    AND g.home_points IS NOT NULL
    AND g.away_points IS NOT NULL
);

-- exercise: 5
-- check: exact
SELECT
  avg(
    -(home_win * ln(greatest(least(implied, 1 - 1e-6), 1e-6))
      + (1 - home_win) * ln(greatest(least(1 - implied, 1 - 1e-6), 1e-6)))
  ) AS log_loss
FROM (
  SELECT
    CASE WHEN l.moneyline_home < 0
         THEN (-l.moneyline_home)::DOUBLE / ((-l.moneyline_home) + 100)
         ELSE 100.0 / (l.moneyline_home + 100)
    END AS implied,
    CASE WHEN g.home_points > g.away_points THEN 1.0 ELSE 0.0 END AS home_win
  FROM core.fact_game_line AS l
  JOIN core.fact_game AS g ON g.game_id = l.game_id
  WHERE g.season BETWEEN 2015 AND 2024
    AND g.season_type = 'regular'
    AND l.moneyline_home IS NOT NULL
    AND g.home_points IS NOT NULL
    AND g.away_points IS NOT NULL
);

-- exercise: 1
-- check: exact
WITH graded AS (
  SELECT
    season,
    week,
    game_id,
    CASE WHEN home_points + away_points > selected_total THEN 1.0 ELSE 0.0 END AS went_over,
    CASE
      WHEN home_points + away_points > selected_total THEN 0.9091
      WHEN home_points + away_points = selected_total THEN 0.0
      ELSE -1.0
    END AS pnl
  FROM core.fact_game
  WHERE season BETWEEN 2015 AND 2024
    AND season_type = 'regular'
    AND selected_total IS NOT NULL
    AND home_points IS NOT NULL
    AND away_points IS NOT NULL
),
season_rate AS (
  SELECT season, avg(went_over) AS over_rate
  FROM graded
  GROUP BY season
),
trail AS (
  SELECT
    s.season AS test_season,
    avg(p.over_rate) AS trailing_2_rate
  FROM season_rate AS s
  JOIN season_rate AS p
    ON p.season IN (s.season - 1, s.season - 2)
  GROUP BY s.season
  HAVING count(*) = 2
)
SELECT
  g.season,
  g.week,
  count(*) AS n_bets,
  round(sum(g.pnl), 2) AS net_units
FROM graded AS g
JOIN trail AS t ON t.test_season = g.season
WHERE t.trailing_2_rate > 0.52
GROUP BY g.season, g.week
ORDER BY g.season, g.week;

-- exercise: 2
-- check: exact
-- note: Recomputes the C7-1 always-over backtest inline; grading uses a fresh connection.
WITH graded AS (
  SELECT
    season,
    week,
    CASE
      WHEN home_points + away_points > selected_total THEN 0.9091
      WHEN home_points + away_points = selected_total THEN 0.0
      ELSE -1.0
    END AS pnl_units
  FROM core.fact_game
  WHERE season BETWEEN 2015 AND 2024
    AND season_type = 'regular'
    AND selected_total IS NOT NULL
    AND home_points IS NOT NULL
    AND away_points IS NOT NULL
),
backtest_result AS (
  SELECT
    'always_over' AS rule,
    season,
    week,
    count(*) AS n_bets,
    round(sum(pnl_units), 2) AS net_units
  FROM graded
  GROUP BY season, week
),
cum AS (
  SELECT
    season,
    week,
    net_units,
    sum(net_units) OVER (ORDER BY season, week) AS bankroll
  FROM backtest_result
)
SELECT
  season,
  week,
  net_units,
  bankroll,
  max(bankroll) OVER (
    ORDER BY season, week
    ROWS BETWEEN UNBOUNDED PRECEDING AND CURRENT ROW
  ) - bankroll AS drawdown
FROM cum
ORDER BY season, week;

-- exercise: 3
-- check: exact
WITH graded AS (
  SELECT
    season,
    CASE
      WHEN home_points + away_points > selected_total THEN 0.9091
      WHEN home_points + away_points = selected_total THEN 0.0
      ELSE -1.0
    END AS pnl_units
  FROM core.fact_game
  WHERE season BETWEEN 2015 AND 2024
    AND season_type = 'regular'
    AND selected_total IS NOT NULL
    AND home_points IS NOT NULL
    AND away_points IS NOT NULL
)
SELECT
  season,
  count(*) AS n_bets,
  round(sum(pnl_units), 2) AS net_units,
  round(sum(pnl_units) / count(*), 4) AS roi_per_bet
FROM graded
GROUP BY season
ORDER BY season;

-- exercise: 4
-- check: exact
WITH over_g AS (
  SELECT
    season,
    CASE
      WHEN home_points + away_points > selected_total THEN 0.9091
      WHEN home_points + away_points = selected_total THEN 0.0
      ELSE -1.0
    END AS pnl
  FROM core.fact_game
  WHERE season BETWEEN 2015 AND 2024
    AND season_type = 'regular'
    AND selected_total IS NOT NULL
    AND home_points IS NOT NULL
    AND away_points IS NOT NULL
),
under_g AS (
  SELECT
    season,
    CASE
      WHEN home_points + away_points < selected_total THEN 0.9091
      WHEN home_points + away_points = selected_total THEN 0.0
      ELSE -1.0
    END AS pnl
  FROM core.fact_game
  WHERE season BETWEEN 2015 AND 2024
    AND season_type = 'regular'
    AND selected_total IS NOT NULL
    AND home_points IS NOT NULL
    AND away_points IS NOT NULL
)
SELECT 'always_over' AS rule, season, round(sum(pnl) / count(*), 4) AS roi
FROM over_g
GROUP BY season
UNION ALL
SELECT 'always_under', season, round(sum(pnl) / count(*), 4)
FROM under_g
GROUP BY season
ORDER BY rule, season;

-- exercise: 5
-- check: exact
WITH graded AS (
  SELECT
    season,
    week,
    CASE
      WHEN home_points + away_points > selected_total THEN 0.9091
      WHEN home_points + away_points = selected_total THEN 0.0
      ELSE -1.0
    END AS pnl_units
  FROM core.fact_game
  WHERE season BETWEEN 2015 AND 2024
    AND season_type = 'regular'
    AND selected_total IS NOT NULL
    AND home_points IS NOT NULL
    AND away_points IS NOT NULL
),
weeks AS (
  SELECT season, week, sum(pnl_units) AS net_units
  FROM graded
  GROUP BY season, week
),
marked AS (
  SELECT
    *,
    CASE WHEN net_units < 0 THEN 1 ELSE 0 END AS is_loss,
    sum(CASE WHEN net_units >= 0 THEN 1 ELSE 0 END) OVER (ORDER BY season, week) AS grp
  FROM weeks
)
SELECT max(n) AS longest_losing_weeks
FROM (
  SELECT grp, count(*) AS n
  FROM marked
  WHERE is_loss = 1
  GROUP BY grp
);

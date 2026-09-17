-- exercise: 1
-- check: exact
SELECT DISTINCT payload ->> 'homeTeam' AS home_team
FROM raw.games
WHERE payload ->> 'homeTeam' IS NOT NULL
ORDER BY 1;

-- exercise: 2
-- check: exact
SELECT
  gameId,
  ln.provider,
  ln.spread,
  ln.overUnder
FROM (
  SELECT gameId, unnest(lines) AS ln
  FROM stg.lines
  WHERE season = 2024
    AND seasonType = 'regular'
)
WHERE ln.provider IS NOT NULL
ORDER BY gameId, ln.provider;

-- exercise: 3
-- check: exact
SELECT
  gameId,
  t.score AS quarter_score,
  t._idx
FROM stg.game,
     unnest(homeLineScores) WITH ORDINALITY AS t(score, _idx)
WHERE homeLineScores IS NOT NULL
ORDER BY gameId, t._idx;

-- exercise: 4
-- check: exact
SELECT
  gameId,
  ln.provider,
  struct_pack(spread := ln.spread, total := ln.overUnder) AS line_struct
FROM (
  SELECT gameId, unnest(lines) AS ln
  FROM stg.lines
  WHERE season = 2024
    AND seasonType = 'regular'
)
WHERE ln.provider IS NOT NULL
ORDER BY gameId, ln.provider;

-- exercise: 5
-- check: exact
SELECT DISTINCT ln.provider
FROM (
  SELECT unnest(lines) AS ln
  FROM stg.lines
) e
LEFT JOIN core.dim_lines_provider AS p
  ON p.provider_key = ln.provider
WHERE ln.provider IS NOT NULL
  AND p.provider_key IS NULL
ORDER BY 1;

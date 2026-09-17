-- exercise: 1
-- check: exact
SELECT home_team_id
FROM core.fact_game
WHERE season = 2024
EXCEPT
SELECT home_team_id
FROM core.fact_game
WHERE season = 2023
ORDER BY 1;

-- exercise: 2
-- check: exact
SELECT game_id, count(*) AS n
FROM core.fact_game
GROUP BY game_id
HAVING count(*) > 1
ORDER BY game_id;

-- exercise: 3
-- check: exact
SELECT count(*) AS null_start_dates
FROM core.fact_game
WHERE start_date IS NULL;

-- exercise: 4
-- check: exact
SELECT schema, max(loaded_at) AS latest_loaded_at
FROM meta.load_report
GROUP BY schema
ORDER BY schema;

-- exercise: 5
-- check: exact
SELECT provider_key
FROM core.fact_game_line
WHERE provider_key IS NOT NULL
INTERSECT
SELECT provider_key
FROM core.dim_lines_provider
ORDER BY 1;

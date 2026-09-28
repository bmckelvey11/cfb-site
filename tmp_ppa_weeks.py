import os

os.environ["CFB_DATA_ROOT"] = r"C:\Users\mckel\dev\cfb\data"

import duckdb
import cfb_paths

con = duckdb.connect(str(cfb_paths.DB_PATH), read_only=True)
print(
    "columns",
    con.execute(
        "SELECT column_name FROM duckdb_columns() WHERE schema_name = 'stg' AND table_name = 'ppa_games'"
    )
    .fetchdf()["column_name"]
    .tolist(),
)
print("--- ppa seasons ---")
print(
    con.execute(
        "SELECT season, seasonType, COUNT(*) n, MIN(week) min_w, MAX(week) max_w "
        "FROM stg.ppa_games GROUP BY 1, 2 ORDER BY 1, 2"
    )
    .fetchdf()
    .to_string()
)
print("--- games 2025-2026 ---")
print(
    con.execute(
        "SELECT season, seasonType, MIN(week) min_w, MAX(week) max_w, COUNT(*) n "
        "FROM stg.games WHERE season >= 2025 GROUP BY 1, 2 ORDER BY 1, 2"
    )
    .fetchdf()
    .to_string()
)
print("--- 2026 ppa by week ---")
print(
    con.execute(
        "SELECT week, COUNT(*) rows, COUNT(DISTINCT team) teams "
        "FROM stg.ppa_games WHERE season = 2026 GROUP BY 1 ORDER BY 1"
    )
    .fetchdf()
    .to_string()
)
print("--- USC ---")
print(
    con.execute(
        "SELECT team, week, opponent FROM stg.ppa_games WHERE season = 2026 AND team = 'USC' ORDER BY week"
    )
    .fetchdf()
    .to_string()
)
print("--- raw ppa_games_2026 weeks ---")
print(
    con.execute(
        "SELECT week, COUNT(*) n FROM read_json_auto(?) GROUP BY 1 ORDER BY 1",
        [r"C:\Users\mckel\dev\cfb\data\raw\ppa_games_2026.json"],
    )
    .fetchdf()
    .to_string()
)
print("--- 2026 games by week ---")
print(
    con.execute(
        "SELECT week, COUNT(*) games "
        "FROM stg.games WHERE season = 2026 GROUP BY 1 ORDER BY 1"
    )
    .fetchdf()
    .to_string()
)

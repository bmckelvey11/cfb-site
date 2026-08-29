import duckdb

con = duckdb.connect(r"C:\Users\mckel\data\cfb\cfb.duckdb", read_only=True)
tables = [
    r[0]
    for r in con.execute(
        "SELECT table_name FROM duckdb_tables() WHERE schema_name='stg' ORDER BY 1"
    ).fetchall()
]
print("has stg.plays", "plays" in tables)
for table in ("games", "drives", "lines", "advanced_game_stats", "weather", "teams"):
    cols = [row[0] for row in con.execute(f'DESCRIBE stg."{table}"').fetchall()]
    print(f"\n{table} ({len(cols)}):")
    print("  " + ", ".join(cols))
con.close()

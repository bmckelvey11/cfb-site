import marimo

__generated_with = "0.24.0"
app = marimo.App(width="medium")


@app.cell
def _():
    import marimo as mo
    import duckdb
    import polars as pl

    return duckdb, mo


@app.cell
def _(duckdb):
    # Relative "cfb.duckdb" resolved against cwd, which is the empty 12 KB stray at
    # the repo root -- not the warehouse. cfb_paths is the only resolver that knows.
    import sys
    from pathlib import Path

    sys.path.insert(0, str(Path(__file__).resolve().parent))
    from cfb_paths import DB_PATH

    cfb = duckdb.connect(str(DB_PATH), read_only=True)
    return (cfb,)


@app.cell
def _(cfb, mo):
    _df = mo.sql(
        f"""
        SELECT table_catalog, table_schema, table_name
        FROM information_schema.tables
        ORDER BY table_schema, table_name
        """,
        engine=cfb
    )
    return


@app.cell
def _(mo):
    mo.md(r"""
    ### Why the table list is empty

    A few common causes:

    1. **`duckdb.connect("cfb.duckdb")` created a brand-new, empty file** because the
       path is *relative* to the notebook's working directory, not where you think the
       database lives. DuckDB silently creates the file if it doesn't exist.
    2. **The data lives in an attached database** — `information_schema.tables` only
       reports objects in the *current* catalog, so attached DBs won't show up.
    3. The objects are **views/temp tables** in another catalog, which is better
       inspected with `duckdb_tables()` / `duckdb_views()`.

    Run the cells below to diagnose.
    """)
    return


@app.cell
def _():
    import os

    cfb_path = os.path.abspath("cfb.duckdb")
    cfb_diagnostics = {
        "cwd": os.getcwd(),
        "resolved_db_path": cfb_path,
        "exists": os.path.exists(cfb_path),
        "size_bytes": os.path.getsize(cfb_path) if os.path.exists(cfb_path) else 0,
    }
    cfb_diagnostics
    return


@app.cell
def _(cfb, mo):
    _df = mo.sql(
        f"""
        SELECT database_name, path, type, readonly
        FROM duckdb_databases()
        ORDER BY database_name
        """,
        engine=cfb
    )
    return


@app.cell
def _(cfb, mo):
    _df = mo.sql(
        f"""
        SELECT database_name, schema_name, table_name, 'table' AS kind, estimated_size AS rows
        FROM duckdb_tables()
        UNION ALL
        SELECT database_name, schema_name, view_name AS table_name, 'view' AS kind, NULL AS rows
        FROM duckdb_views()
        WHERE NOT internal
        ORDER BY database_name, schema_name, table_name
        """,
        engine=cfb
    )
    return


@app.cell
def _():
    from pathlib import Path

    cfb_search_roots = [Path.cwd(), Path.cwd().parent, Path.home()]
    cfb_found_dbs = sorted(
        {
            str(p.resolve())
            for root in cfb_search_roots
            if root.exists()
            for p in root.rglob("*.duckdb")
            if p.is_file() and p.stat().st_size > 0
        }
    )
    cfb_found_dbs
    return (cfb_found_dbs,)


@app.cell
def _(cfb_found_dbs, mo):
    cfb_db_selector = mo.ui.dropdown(
        options=cfb_found_dbs,
        value=cfb_found_dbs[0] if cfb_found_dbs else None,
        label="Pick the real cfb database file",
    )
    cfb_db_selector
    return (cfb_db_selector,)


@app.cell
def _(cfb_db_selector, duckdb):
    cfb_db = duckdb.connect(cfb_db_selector.value, read_only=True)
    cfb_db
    return


@app.cell
def _(cfb, mo):
    _df = mo.sql(
        f"""
        SELECT database_name, schema_name, table_name, estimated_size AS approx_rows
        FROM duckdb_tables()
        ORDER BY database_name, schema_name, table_name
        """,
        engine=cfb
    )
    return


if __name__ == "__main__":
    app.run()

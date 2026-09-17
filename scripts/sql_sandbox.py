"""SQL practice sandbox over the CFB warehouse.

Opens a writable scratch database and attaches the warehouse READ ONLY as ``cfb``,
so practice queries cannot damage ``cfb.duckdb``. ``USE cfb`` is set, so
``stg.games`` and ``core.fact_game`` resolve unqualified; scratch tables go in the
``sandbox`` catalog (``CREATE TABLE sandbox.main.fact_bet AS ...``).

Usage (from repo root, CFB_DATA_ROOT set):

    python scripts/sql_sandbox.py                 # interactive REPL
    python scripts/sql_sandbox.py -c "FROM stg.games LIMIT 5"
    python scripts/sql_sandbox.py -f practice/m3.sql
    python scripts/sql_sandbox.py --md            # attach md:cfb instead of the local file

REPL: end a statement with ``;``. Dot commands: ``.tables [schema]``, ``.d <table>``,
``.run <file.sql>``, ``.q``.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

import duckdb

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from cfb_paths import DATA_ROOT, DB_PATH  # noqa: E402

SCRATCH = DATA_ROOT / "sandbox.duckdb"
MAX_ROWS = 40


def connect(md: bool, fresh: bool) -> duckdb.DuckDBPyConnection:
    con = duckdb.connect()
    con.execute(f"ATTACH '{':memory:' if fresh else SCRATCH}' AS sandbox")
    src = "md:cfb" if md else str(DB_PATH)
    con.execute(f"ATTACH '{src}' AS cfb (READ_ONLY)")
    con.execute("USE cfb")
    return con


def run(con: duckdb.DuckDBPyConnection, sql: str) -> None:
    sql = sql.strip().rstrip(";")
    if not sql:
        return
    try:
        rel = con.sql(sql)
        if rel is None:
            print("ok")
            return
        rel.show(max_rows=MAX_ROWS)
        n = con.sql(f"SELECT count(*) FROM ({sql})").fetchone()[0]
        print(f"({n} rows)")
    except duckdb.Error as exc:
        print(f"ERROR: {exc}")
        if "read-only" in str(exc):
            print("hint: write scratch tables to the sandbox catalog, e.g. "
                  "CREATE TABLE sandbox.main.my_table AS ...")


def run_file(con: duckdb.DuckDBPyConnection, path: Path) -> None:
    for stmt in path.read_text(encoding="utf-8").split(";"):
        if stmt.strip():
            print(f"\n>>> {stmt.strip()[:80]}")
            run(con, stmt)


def dot(con: duckdb.DuckDBPyConnection, line: str) -> bool:
    """Handle a dot command. Returns False when the REPL should exit."""
    cmd, _, arg = line[1:].partition(" ")
    if cmd == "q":
        return False
    if cmd == "tables":
        where = f"AND schema_name = '{arg}'" if arg else ""
        run(con, "SELECT database_name, schema_name, table_name, estimated_size AS rows "
                 f"FROM duckdb_tables() WHERE NOT internal {where} ORDER BY ALL")
    elif cmd == "d":
        run(con, f"DESCRIBE {arg}")
    elif cmd == "run":
        run_file(con, Path(arg))
    else:
        print(".tables [schema] | .d <table> | .run <file.sql> | .q")
    return True


def repl(con: duckdb.DuckDBPyConnection) -> None:
    print("cfb sandbox: warehouse attached read-only as `cfb`; scratch catalog `sandbox`.")
    print("End statements with `;`. `.q` quits, `.tables stg` lists tables, `.d core.fact_game` describes.")
    buf: list[str] = []
    while True:
        try:
            line = input("... " if buf else "sql> ")
        except (EOFError, KeyboardInterrupt):
            print()
            return
        if not buf and line.startswith("."):
            if not dot(con, line.strip()):
                return
            continue
        buf.append(line)
        if line.rstrip().endswith(";"):
            run(con, "\n".join(buf))
            buf = []


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("-c", "--command", help="run one statement and exit")
    ap.add_argument("-f", "--file", type=Path, help="run a .sql file and exit")
    ap.add_argument("--md", action="store_true", help="attach md:cfb instead of the local warehouse")
    ap.add_argument("--fresh", action="store_true", help="in-memory scratch instead of data/sandbox.duckdb")
    args = ap.parse_args()

    con = connect(args.md, args.fresh)
    if args.command:
        run(con, args.command)
    elif args.file:
        run_file(con, args.file)
    else:
        repl(con)


if __name__ == "__main__":
    main()

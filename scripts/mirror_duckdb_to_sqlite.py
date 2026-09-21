"""Mirror data/cfb.duckdb into data/cfb_mirror.sqlite (one sqlite table per schema.table, name = schema__table).

Nested types (STRUCT/LIST/MAP) have no sqlite equivalent, so those columns are
serialized with to_json() on the way out.
"""
from pathlib import Path
import sys
import time

import duckdb

REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO))
from cfb_paths import DATA_ROOT  # noqa: E402

_ROOT = str(DATA_ROOT)
SRC = f"{_ROOT}/cfb.duckdb"
DST = f"{_ROOT}/cfb_mirror.sqlite"

NESTED_MARKERS = ("STRUCT(", "[]", "MAP(")


def is_nested(data_type: str) -> bool:
    return any(m in data_type for m in NESTED_MARKERS)


def main():
    con = duckdb.connect()
    con.execute("INSTALL sqlite")
    con.execute("LOAD sqlite")
    con.execute(f"ATTACH '{SRC}' AS src (READ_ONLY)")
    con.execute(f"ATTACH '{DST}' AS dst (TYPE SQLITE)")

    tables = con.execute(
        """
        SELECT schema_name, table_name
        FROM duckdb_tables()
        WHERE database_name = 'src' AND schema_name IN ('raw', 'stg', 'meta')
        ORDER BY schema_name, table_name
        """
    ).fetchall()

    for schema, table in tables:
        cols = con.execute(
            """
            SELECT column_name, data_type
            FROM duckdb_columns()
            WHERE database_name = 'src' AND schema_name = ? AND table_name = ?
            ORDER BY column_index
            """,
            [schema, table],
        ).fetchall()

        select_parts = []
        for col, dtype in cols:
            ident = f'"{col}"'
            if is_nested(dtype):
                select_parts.append(f"to_json({ident}) AS {ident}")
            else:
                select_parts.append(ident)

        dst_table = f"{schema}__{table}"
        con.execute(f'DROP TABLE IF EXISTS dst."{dst_table}"')

        t0 = time.time()
        con.execute(
            f'CREATE TABLE dst."{dst_table}" AS SELECT {", ".join(select_parts)} '
            f'FROM src."{schema}"."{table}"'
        )
        n = con.execute(f'SELECT COUNT(*) FROM dst."{dst_table}"').fetchone()[0]
        print(f"{dst_table}: {n} rows ({time.time()-t0:.1f}s)", file=sys.stderr)

    con.close()


if __name__ == "__main__":
    main()

"""Audit the CFB SQL course against the local warehouse.

Parses every fenced ``sql`` block in the course markdown, checks that each
``schema.table`` (and ``alias.column``) it references exists in the attached
warehouse, runs the block in the read-only sandbox, and compares the returned
row count with the ``-- rows: N`` claim on line 2. Prose references of the form
``schema.table[.column]`` are checked for existence too.

Usage (from repo root, CFB_DATA_ROOT set):

    python scripts/sql_course_schema_audit.py path/to/cfb_sql_course.md
    python scripts/sql_course_schema_audit.py course.md --out audit.md   # also write markdown
    python scripts/sql_course_schema_audit.py course.md --md             # audit md:cfb instead

Scratch objects a block creates land in an in-memory ``sandbox`` catalog, so the
audit never touches ``data/sandbox.duckdb`` and never writes to ``cfb``.
"""

from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

import duckdb

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(Path(__file__).resolve().parent))
from sql_sandbox import connect  # noqa: E402
from learning.sql_course.course_parse import Block, parse_blocks  # noqa: E402

SCHEMAS = "raw|stg|core|meta|marts|refs|staging|main"
# `sandbox.main.x` is scratch, not warehouse: the lookbehind keeps it out of both regexes.
TABLE_REF = re.compile(rf"(?<!sandbox\.)\b({SCHEMAS})\.([A-Za-z_][A-Za-z0-9_]*)")
PROSE_REF = re.compile(rf"`(?<!sandbox\.)({SCHEMAS})\.([A-Za-z_][A-Za-z0-9_]*)(?:\.([A-Za-z_][A-Za-z0-9_]*))?`")
ALIAS_DEF = re.compile(
    rf"\b(?:FROM|JOIN)\s+({SCHEMAS})\.([A-Za-z_][A-Za-z0-9_]*)(?:\s+AS)?\s+([a-z][a-z0-9_]*)\b", re.I
)
COL_REF = re.compile(r"\b([a-z][a-z0-9_]*)\.([A-Za-z_][A-Za-z0-9_]*)\b")
NOT_ALIASES = {"as", "on", "where", "sandbox", "information_schema"}


def catalog(con: duckdb.DuckDBPyConnection) -> dict[str, set[str]]:
    rows = con.execute(
        "SELECT table_schema, table_name, column_name FROM information_schema.columns "
        "WHERE table_catalog = 'cfb'"
    ).fetchall()
    out: dict[str, set[str]] = {}
    for schema, table, col in rows:
        out.setdefault(f"{schema}.{table}", set()).add(col)
    return out


def resolve_refs(b: Block, cat: dict[str, set[str]]) -> None:
    b.tables = {f"{s}.{t}" for s, t in TABLE_REF.findall(b.sql)}
    aliases = {a.lower(): f"{s}.{t}" for s, t, a in ALIAS_DEF.findall(b.sql) if a.lower() not in NOT_ALIASES}
    schema_names = set(SCHEMAS.split("|"))
    for alias, col in COL_REF.findall(b.sql):
        if alias in NOT_ALIASES or alias in schema_names:
            continue
        table = aliases.get(alias)
        if table:
            b.columns.add(f"{table}.{col}")
    for t in sorted(b.tables):
        if t not in cat:
            b.missing.append(t)
    for c in sorted(b.columns):
        table, col = c.rsplit(".", 1)
        if table in cat and col not in cat[table]:
            b.missing.append(c)


def _is_comment_only(stmt: str) -> bool:
    return all(line.strip().startswith("--") for line in stmt.splitlines() if line.strip())


def run_block(con: duckdb.DuckDBPyConnection, b: Block) -> None:
    stmts = [s.strip() for s in b.sql.split(";") if s.strip() and not _is_comment_only(s)]
    try:
        for stmt in stmts:
            rel = con.sql(stmt)
            b.local_rows = len(rel.fetchall()) if rel is not None else 0
    except duckdb.Error as exc:
        b.status = "error: " + str(exc).splitlines()[0][:110]
        return
    if b.missing:
        b.status = "missing: " + ", ".join(b.missing)
    elif b.claimed is None:
        b.status = "unverifiable (no numeric claim)"
    elif b.claimed == b.local_rows:
        b.status = "ok"
    else:
        b.status = "MISMATCH"


def prose_refs(text: str, cat: dict[str, set[str]]) -> list[tuple[str, str]]:
    seen: dict[str, str] = {}
    for s, t, c in PROSE_REF.findall(text):
        table = f"{s}.{t}"
        if table not in cat:
            seen[table] = "missing table"
        elif c and c not in cat[table]:
            seen[f"{table}.{c}"] = "missing column"
        else:
            seen.setdefault(f"{table}.{c}" if c else table, "ok")
    return sorted(seen.items())


def render(blocks: list[Block], prose: list[tuple[str, str]]) -> str:
    out = [
        "| block | module | line | tables | columns checked | exists? | claimed rows | local rows | status |",
        "|---|---|---|---|---|---|---|---|---|",
    ]
    for b in blocks:
        exists = "no: " + ", ".join(b.missing) if b.missing else "yes"
        cols = ", ".join(sorted({c.rsplit(".", 1)[1] for c in b.columns})) or "-"
        claimed = "" if b.claimed is None else b.claimed
        local = "" if b.local_rows is None else b.local_rows
        out.append(
            f"| {b.block_id} | {b.module} | {b.line} | {', '.join(sorted(b.tables)) or '-'} | {cols} | "
            f"{exists} | {claimed} | {local} | {b.status} |"
        )
    n_ok = sum(b.status == "ok" for b in blocks)
    n_bad = sum(b.status.startswith(("MISMATCH", "error", "missing")) for b in blocks)
    out.append(
        f"\n{len(blocks)} blocks: {n_ok} ok, {n_bad} mismatch/error/missing, "
        f"{len(blocks) - n_ok - n_bad} unverifiable.\n"
    )
    out.append("## Prose references (`schema.table[.column]` in backticks)\n")
    out.append("| reference | status |\n|---|---|")
    out += [f"| {ref} | {st} |" for ref, st in prose]
    bad = [r for r, s in prose if s != "ok"]
    out.append(f"\n{len(prose)} distinct prose references, {len(bad)} missing.")
    return "\n".join(out)


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("course", type=Path, help="course markdown file")
    ap.add_argument("--md", action="store_true", help="audit md:cfb instead of the local warehouse")
    ap.add_argument("--out", type=Path, help="also write the markdown report here")
    args = ap.parse_args()

    text = args.course.read_text(encoding="utf-8")
    con = connect(md=args.md, fresh=True)
    cat = catalog(con)
    blocks = parse_blocks(text)
    for b in blocks:
        resolve_refs(b, cat)
        run_block(con, b)
    report = render(blocks, prose_refs(text, cat))
    print(report)
    if args.out:
        args.out.write_text(report, encoding="utf-8")


if __name__ == "__main__":
    main()

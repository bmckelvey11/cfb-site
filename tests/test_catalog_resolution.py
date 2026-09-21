"""Every ``<schema>.<table>`` literal in the repo must resolve in the warehouse.

Two renames in one migration broke two consumers silently and the suite stayed
green through both (see ``archive/docs/warehouse-schema-recommendation.md`` §0):
``stg.calendar`` -> ``stg.calendar_gql`` killed the nightly ``build_core``, and
``stg.gql_game`` -> ``stg.game`` killed the prediction tracker. Neither had a
test, because tests that build their own fixtures cannot notice that the live
catalog moved.

This is the gate for any further renaming. It reads string literals only --
docstrings are prose, and attribute access like ``meta.get(...)`` is not a table.
"""

from __future__ import annotations

import ast
import re
from collections import defaultdict
from pathlib import Path

import duckdb
import pytest

from cfb_paths import DB_PATH  # noqa: E402

REPO = Path(__file__).resolve().parents[1]
ROOTS = ("cfb_system_maker", "models", "research", "scripts")

# `stg_gql` is gone (ADR-0003); dropping it from the alternation means a literal
# naming it now resolves as `stg_gql.<x>` matching nothing, which is the point --
# a stale reference must fail, not be quietly skipped.
# The lookbehind rejects `.meta.json` -- a file suffix, not a schema.
REF = re.compile(r"(?<![\w.])(stg|raw|core|meta)\.([A-Za-z_][A-Za-z0-9_]*)")

# References that are correct but cannot resolve against the local file.
ALLOW = {
    ("meta", "warehouse_version"): "created on MotherDuck by promote_to_motherduck",
    ("stg", "game_lines__backfill"): "transient; built and dropped inside one load",
}


def _docstring_ids(tree: ast.AST) -> set[int]:
    """Object ids of every docstring node, so prose is not read as SQL."""
    out = set()
    for node in ast.walk(tree):
        if isinstance(node, (ast.Module, ast.ClassDef, ast.FunctionDef, ast.AsyncFunctionDef)):
            body = getattr(node, "body", None)
            if body and isinstance(body[0], ast.Expr) and isinstance(body[0].value, ast.Constant):
                out.add(id(body[0].value))
    return out


def collect_references() -> dict[tuple[str, str], list[str]]:
    """Map ``(schema, table)`` to the ``path:line`` sites naming it."""
    found: dict[tuple[str, str], list[str]] = defaultdict(list)
    for root in ROOTS:
        for path in sorted((REPO / root).rglob("*.py")):
            try:
                tree = ast.parse(path.read_text(encoding="utf-8", errors="replace"))
            except SyntaxError:
                continue
            docs = _docstring_ids(tree)
            for node in ast.walk(tree):
                if not (isinstance(node, ast.Constant) and isinstance(node.value, str)):
                    continue
                if id(node) in docs:
                    continue
                for m in REF.finditer(node.value):
                    key = (m.group(1), m.group(2))
                    if key in ALLOW:
                        continue
                    rel = path.relative_to(REPO).as_posix()
                    found[key].append(f"{rel}:{node.lineno}")
    return found


def test_every_schema_table_literal_resolves():
    db = DB_PATH
    if not db.exists():
        pytest.skip("no live CFB_DATA_ROOT warehouse")
    con = duckdb.connect(str(db), read_only=True)
    try:
        live = {
            (s, t)
            for s, t in con.execute(
                "SELECT schema_name, table_name FROM duckdb_tables()"
                " UNION ALL SELECT schema_name, view_name FROM duckdb_views()"
            ).fetchall()
        }
    finally:
        con.close()

    refs = collect_references()
    assert refs, "scanner found no references at all -- it has stopped working"
    missing = sorted(k for k in refs if k not in live)
    detail = "\n".join(f"  {s}.{t}  <- {', '.join(refs[(s, t)])}" for s, t in missing)
    assert not missing, f"{len(missing)} reference(s) do not resolve:\n{detail}"


def test_scanner_reads_sql_but_not_prose():
    """The two false-positive classes that made the naive version unusable."""
    src = '''
"""Docstring naming stg.calendar as prose."""
q = "SELECT * FROM stg.games"
p = f"snapshot{stamp}.meta.json"
meta.get("x")
'''
    tree = ast.parse(src)
    docs = _docstring_ids(tree)
    hits = {
        (m.group(1), m.group(2))
        for node in ast.walk(tree)
        if isinstance(node, ast.Constant) and isinstance(node.value, str) and id(node) not in docs
        for m in REF.finditer(node.value)
    }
    assert hits == {("stg", "games")}

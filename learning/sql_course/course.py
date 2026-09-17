"""SQL course runner: list / show / grade against the local warehouse.

The attached ``cfb`` catalog is DuckDB READ_ONLY. That stops writes to the
warehouse; it is not a process sandbox. Learner SQL can still read any file
DuckDB can reach, and some exercises (B5-4) intentionally write Parquet.
Same trust level as running a script the user wrote.
"""

from __future__ import annotations

import argparse
import math
import sys
import threading
import time
from dataclasses import dataclass, field
from decimal import Decimal
from pathlib import Path

import duckdb

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
from learning.sql_course.course_parse import Module, parse_course  # noqa: E402
from scripts.sql_sandbox import connect as sandbox_connect  # noqa: E402

HERE = Path(__file__).resolve().parent
COURSE_PATH = HERE / "cfb_sql_course.md"
SOLUTIONS_DIR = HERE / "solutions"
TIMEOUT_S = 10.0
BYTE_BUDGET = 200 * 1024 * 1024
FETCH_BATCH = 5000
DISPLAY_CAP = 20
LOCK_MSG = "progress not recorded: sandbox.duckdb is locked by another process"
PROGRESS_DDL = """
CREATE TABLE IF NOT EXISTS sandbox.main.course_progress (
    module TEXT NOT NULL,
    exercise TEXT NOT NULL,
    status TEXT,
    attempted_at TIMESTAMPTZ,
    PRIMARY KEY (module, exercise)
)
"""


class RunSqlError(Exception):
    pass


@dataclass
class Solution:
    number: int
    check: str
    sql: str
    probes: list[str] = field(default_factory=list)
    note: str = ""


def _is_comment_only(stmt: str) -> bool:
    return all(line.strip().startswith("--") for line in stmt.splitlines() if line.strip())


def _statements(sql: str) -> list[str]:
    return [s.strip() for s in sql.split(";") if s.strip() and not _is_comment_only(s)]


def _nbytes(v: object) -> int:
    n = sys.getsizeof(v)
    if isinstance(v, dict):
        n += sum(_nbytes(k) + _nbytes(val) for k, val in v.items())
    elif isinstance(v, (list, tuple)):
        n += sum(_nbytes(x) for x in v)
    return n


def _is_nan(v: object) -> bool:
    if isinstance(v, float) and math.isnan(v):
        return True
    if isinstance(v, Decimal) and v.is_nan():
        return True
    return False


def _key(v: object) -> tuple:
    if v is None:
        return (0, 0, "")
    if _is_nan(v):
        return (0, 1, "")
    if isinstance(v, dict):
        return (2, 0, tuple(sorted((k, _key(val)) for k, val in v.items())))
    if isinstance(v, (list, tuple)):
        return (3, 0, tuple(_key(x) for x in v))
    if isinstance(v, bool):
        return (1, 0, v)
    if isinstance(v, (int, float, Decimal)):
        return (1, 0, round(float(v), 4))
    return (1, 0, v)


def _canon_rows(columns: list[str], rows: list[tuple]) -> list[tuple]:
    names = [c.lower() for c in columns]
    out = []
    for row in rows:
        paired = sorted(zip(names, row), key=lambda p: p[0])
        out.append(tuple(_key(v) for _, v in paired))
    out.sort()
    return out


def prepare_grading(con: duckdb.DuckDBPyConnection) -> None:
    con.execute("SET memory_limit='2GB'")
    con.execute("SET max_temp_directory_size='2GB'")


def connect_grading(md: bool = False) -> duckdb.DuckDBPyConnection:
    con = sandbox_connect(md=md, fresh=True)
    prepare_grading(con)
    return con


def run_sql(con: duckdb.DuckDBPyConnection, sql: str) -> tuple[list[str], list[tuple]]:
    """Execute raw SQL (no ORDER BY wrapper). Returns (column names, raw rows)."""
    prepare_grading(con)
    stmts = _statements(sql)
    if not stmts:
        raise RunSqlError("no executable SQL")
    expired = threading.Event()
    timer = threading.Timer(TIMEOUT_S, lambda: (expired.set(), con.interrupt()))
    started = time.monotonic()
    timer.start()
    try:
        for stmt in stmts[:-1]:
            if expired.is_set():
                raise RunSqlError("exceeded 10s")
            con.execute(stmt)
        if expired.is_set():
            raise RunSqlError("exceeded 10s")
        cursor = con.execute(stmts[-1])
        desc = cursor.description
        if desc is None:
            return [], []
        columns = [d[0] for d in desc]
        lower = [c.lower() for c in columns]
        if len(set(lower)) != len(lower):
            dup = next(c for c in lower if lower.count(c) > 1)
            raise RunSqlError(f"ambiguous duplicate column labels: {dup}")
        rows: list[tuple] = []
        total = 0
        while True:
            if expired.is_set() or (time.monotonic() - started) > TIMEOUT_S:
                raise RunSqlError("exceeded 10s")
            batch = cursor.fetchmany(FETCH_BATCH)
            if not batch:
                break
            for row in batch:
                total += sum(_nbytes(v) for v in row)
                if total > BYTE_BUDGET:
                    raise RunSqlError("result too large to grade (exceeded 200MB)")
            rows.extend(batch)
        return columns, rows
    except RunSqlError:
        raise
    except duckdb.Error as exc:
        if expired.is_set() or "interrupt" in str(exc).lower():
            raise RunSqlError("exceeded 10s") from exc
        name = type(exc).__name__
        msg = str(exc)
        if "OutOfMemory" in name or "Out of Memory" in msg or "memory_limit" in msg.lower():
            raise RunSqlError("out of memory") from exc
        raise RunSqlError(msg.splitlines()[0][:200]) from exc
    finally:
        timer.cancel()


def grade(
    con: duckdb.DuckDBPyConnection,
    learner_sql: str,
    reference_sql: str,
    sample: int = DISPLAY_CAP,
    ref_con: duckdb.DuckDBPyConnection | None = None,
) -> tuple[bool, str]:
    """Returns (passed, reason). reason is "" on pass, else the first failing rule."""
    try:
        l_cols, l_rows = run_sql(con, learner_sql)
        r_cols, r_rows = run_sql(ref_con or con, reference_sql)
    except RunSqlError as exc:
        return False, str(exc)
    if len(l_rows) != len(r_rows):
        return False, f"row count {len(l_rows)} != {len(r_rows)}"
    l_set = {c.lower() for c in l_cols}
    r_set = {c.lower() for c in r_cols}
    if l_set != r_set:
        return False, f"column names {sorted(l_set)} != {sorted(r_set)}"
    l_canon = _canon_rows(l_cols, l_rows)
    r_canon = _canon_rows(r_cols, r_rows)
    for i, (a, b) in enumerate(zip(l_canon, r_canon)):
        if a != b:
            shown = min(i, sample - 1)
            return False, f"row {i} differs" + ("" if i == shown else f" (first {sample} displayed)")
    return True, ""


def _ensure_progress(con: duckdb.DuckDBPyConnection) -> None:
    con.execute(PROGRESS_DDL)


def record(con: duckdb.DuckDBPyConnection, module: str, exercise: str, status: str) -> None:
    _ensure_progress(con)
    con.execute(
        """
        INSERT OR REPLACE INTO sandbox.main.course_progress
            (module, exercise, status, attempted_at)
        VALUES (?, ?, ?, now())
        """,
        [module, exercise, status],
    )


def progress_rows(con: duckdb.DuckDBPyConnection) -> list[tuple]:
    _ensure_progress(con)
    return con.execute(
        "SELECT module, exercise, status, attempted_at "
        "FROM sandbox.main.course_progress ORDER BY ALL"
    ).fetchall()


def persist_progress(module: str, exercise: str, status: str) -> None:
    try:
        con = sandbox_connect(md=False, fresh=False)
    except duckdb.IOException:
        print(LOCK_MSG)
        return
    try:
        record(con, module, exercise, status)
    except duckdb.IOException:
        print(LOCK_MSG)
    finally:
        con.close()


def load_course() -> list[Module]:
    return parse_course(COURSE_PATH.read_text(encoding="utf-8"))


def load_solutions(module: str) -> dict[int, Solution]:
    path = SOLUTIONS_DIR / f"{module}.sql"
    if not path.exists():
        return {}
    text = path.read_text(encoding="utf-8")
    out: dict[int, Solution] = {}
    current: Solution | None = None
    sql_lines: list[str] = []

    def flush() -> None:
        nonlocal current, sql_lines
        if current is None:
            return
        current.sql = "\n".join(sql_lines).strip()
        out[current.number] = current
        current = None
        sql_lines = []

    for line in text.splitlines():
        if line.startswith("-- exercise:"):
            flush()
            current = Solution(number=int(line.split(":", 1)[1].strip()), check="exact", sql="")
            continue
        if current is None:
            continue
        if line.startswith("-- check:"):
            current.check = line.split(":", 1)[1].strip()
        elif line.startswith("-- probe:"):
            current.probes.append(line.split(":", 1)[1].strip())
        elif line.startswith("-- note:"):
            current.note = line.split(":", 1)[1].strip()
        else:
            sql_lines.append(line)
    flush()
    return out


def _module(code: str) -> Module:
    for m in load_course():
        if m.code == code:
            return m
    raise SystemExit(f"unknown module: {code}")


def cmd_list() -> None:
    for m in load_course():
        if m.code == "D":
            print(f"{m.code}  {m.title}  (reference, no exercises)")
            continue
        print(f"{m.code}  {m.title}")
        for ex in m.exercises:
            print(f"  {ex.number}. {ex.text}")


def cmd_show(code: str) -> None:
    m = _module(code)
    print(f"{m.code} — {m.title}")
    if m.part_focus:
        print(m.part_focus)
    print("\nLearning goals")
    for g in m.goals:
        print(f"- {g}")
    if m.concepts:
        print("\nConcepts")
        for p in m.concepts:
            print(p)
            print()
    sols = load_solutions(code)
    if m.exercises:
        print("Exercises")
        for ex in m.exercises:
            print(f"{ex.number}. {ex.text}")
            print(f"   Hint: {ex.hint}")
            note = sols[ex.number].note if ex.number in sols else ""
            if note:
                print(f"   Note: {note}")
    if m.check_yourself:
        print("\nCheck yourself")
        print(m.check_yourself)


def _print_verdict(ok: bool, why: str) -> int:
    if ok:
        print("PASS")
        return 0
    print(f"FAIL: {why}")
    return 1


def cmd_run(code: str, exercise: int | None, worked: bool, answer: Path, md: bool) -> int:
    m = _module(code)
    answer_sql = answer.read_text(encoding="utf-8")
    if worked:
        if m.worked is None:
            raise SystemExit(f"{code} has no worked solution")
        reference_sql = m.worked.sql
        learner_con = connect_grading(md=md)
        ref_con = connect_grading(md=md)
        try:
            ok, why = grade(learner_con, answer_sql, reference_sql, ref_con=ref_con)
        finally:
            learner_con.close()
            ref_con.close()
        rc = _print_verdict(ok, why)
        persist_progress(code, "worked", "pass" if ok else "fail")
        return rc
    if exercise is None:
        raise SystemExit("pass --worked or an exercise number")
    sols = load_solutions(code)
    if exercise not in sols:
        raise SystemExit(f"no reference solution for {code}-{exercise}")
    sol = sols[exercise]
    learner_con = connect_grading(md=md)
    ref_con = connect_grading(md=md)
    status: str | None = None
    rc = 1
    try:
        if sol.check == "manual":
            try:
                run_sql(learner_con, answer_sql)
            except RunSqlError as exc:
                rc = _print_verdict(False, str(exc))
                status = "fail"
            else:
                print("manual")
                rc = 0
                status = "manual"
        elif sol.check == "probe":
            ok, why = _grade_probe(learner_con, answer_sql, ref_con, sol)
            status = "pass" if ok else "fail"
            rc = _print_verdict(ok, why)
        else:
            ok, why = grade(learner_con, answer_sql, sol.sql, ref_con=ref_con)
            status = "pass" if ok else "fail"
            rc = _print_verdict(ok, why)
    finally:
        learner_con.close()
        ref_con.close()
    if status is not None:
        persist_progress(code, str(exercise), status)
    return rc


_PROGRESS_MARK = {"pass": "✓", "fail": "x", "manual": "m"}


def cmd_progress() -> None:
    try:
        con = sandbox_connect(md=False, fresh=False)
    except duckdb.IOException:
        print(LOCK_MSG)
        return
    try:
        rows = progress_rows(con)
    finally:
        con.close()
    by = {(r[0], r[1]): r[2] for r in rows}
    print("     w 1 2 3 4 5")
    for m in load_course():
        if m.code == "D":
            continue
        cells = [
            _PROGRESS_MARK.get(by.get((m.code, label), ""), ".")
            for label in ("worked", "1", "2", "3", "4", "5")
        ]
        print(f"{m.code:<3}  " + " ".join(cells))


def _grade_probe(
    learner_con: duckdb.DuckDBPyConnection,
    learner_sql: str,
    ref_con: duckdb.DuckDBPyConnection,
    sol: Solution,
) -> tuple[bool, str]:
    if not sol.probes:
        return False, "probe check is missing -- probe: lines"
    try:
        run_sql(learner_con, learner_sql)
        run_sql(ref_con, sol.sql)
    except RunSqlError as exc:
        return False, str(exc)
    for probe in sol.probes:
        ok, why = grade(learner_con, probe, probe, ref_con=ref_con)
        if not ok:
            return False, f"probe {probe!r}: {why}"
    return True, ""


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    sub = ap.add_subparsers(dest="cmd", required=True)

    sub.add_parser("list", help="modules and exercise texts")

    show_p = sub.add_parser("show", help="goals, concepts, exercises with hints")
    show_p.add_argument("module")

    run_p = sub.add_parser("run", help="grade an answer file")
    run_p.add_argument("module")
    run_p.add_argument("exercise", nargs="?", type=int)
    run_p.add_argument("--worked", action="store_true")
    run_p.add_argument("--answer", type=Path, required=True)
    run_p.add_argument("--md", action="store_true")

    sub.add_parser("progress", help="module x exercise grid")

    args = ap.parse_args()
    if args.cmd == "list":
        cmd_list()
    elif args.cmd == "show":
        cmd_show(args.module)
    elif args.cmd == "run":
        raise SystemExit(cmd_run(args.module, args.exercise, args.worked, args.answer, args.md))
    elif args.cmd == "progress":
        cmd_progress()


if __name__ == "__main__":
    main()

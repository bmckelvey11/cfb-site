from pathlib import Path

from learning.sql_course.course_parse import parse_blocks, parse_course

COURSE = Path("learning/sql_course/cfb_sql_course.md").read_text(encoding="utf-8")


def test_parse_course_shape():
    mods = parse_course(COURSE)
    assert [m.code for m in mods] == [
        "A1", "A2", "A3", "A4", "A5", "A6", "A7", "B1", "B2", "B3", "B4", "B5",
        "C1", "C2", "C3", "C4", "C5", "C6", "C7", "C8", "D",
    ]
    assert all(len(m.exercises) == 5 for m in mods if m.code != "D")
    assert all(m.worked is not None for m in mods if m.code != "D")
    assert all(len(m.goals) == 5 for m in mods if m.code != "D")
    assert mods[7].dialect_table.startswith("| Standard SQL")
    assert len(parse_blocks(COURSE)) == 20


def test_module_title_and_part_fields():
    mods = {m.code: m for m in parse_course(COURSE)}
    assert mods["A1"].title == "Orientation"
    assert mods["A1"].part == "A"
    assert "Portable SQL" in mods["A1"].part_focus
    assert "PostgreSQL" in mods["A1"].part_dialect
    assert mods["B1"].part == "B"
    assert "DuckDB" in mods["B1"].part_dialect
    assert mods["A1"].why_betting.startswith("> **Why it matters for betting.")
    assert mods["A2"].why_betting == ""
    d = mods["D"]
    assert d.part == "D"
    assert d.exercises == []
    assert d.worked is None
    assert d.concepts == []
    headings = [h for h, _ in d.reference_sections]
    assert headings == [
        "Layout and formatting",
        "Naming",
        "Grain, CTEs, and structure",
        "Joins and projection",
        "Fan-out and dedupe discipline",
        "NULL and NaN discipline",
        "Dates and timezones",
        "Idempotency, immutability, and provenance",
        "Comments and performance",
        "Anti-patterns, each with the fix",
    ]
    assert all(body.strip() for _, body in d.reference_sections)


def test_course_markdown_fixes():
    assert "qualify warehouse tables as `cfb.core.…" in COURSE
    assert "FROM cfb.core.fact_game" in COURSE
    b5_hint = next(
        line for line in COURSE.splitlines()
        if line.startswith("3. Table `MACRO` `sandbox.main.season_games")
    )
    assert "cfb.core.fact_game" in b5_hint
    assert "least(floor(implied_home_prob * 10) + 1, 10)" in COURSE
    assert "width_bucket(implied_home_prob" not in COURSE
    assert "width_bucket(total" not in COURSE
    a2_5 = next(line for line in COURSE.splitlines() if line.startswith("5. Detect any DOUBLE"))
    assert "`isnan(x)`" in a2_5
    assert "detect NaN with `x <> x`" not in COURSE
    assert COURSE.count("so `x <> x` never fires") == 3
    assert "isnan(x)" in COURSE
    b2_4 = next(
        line for line in COURSE.splitlines()
        if "per `game_id` from `fact_game_line`" in line
    )
    assert "list_distinct(list(provider_key))" in b2_4
    c3_1 = next(line for line in COURSE.splitlines() if line.startswith("1. Convert the z-score"))
    assert "erf" not in c3_1
    assert "Abramowitz" in c3_1
    c8_1 = next(line for line in COURSE.splitlines() if line.startswith("1. Conform `stg.games`"))
    assert "tagged `'both'`" in c8_1


def test_build_slides(tmp_path):
    from learning.sql_course.build_slides import build_all, render_module
    from learning.sql_course.course_parse import parse_course

    paths = build_all(Path("learning/sql_course/cfb_sql_course.md"), tmp_path)
    assert len(paths) == 22
    html = (tmp_path / "A4.html").read_text(encoding="utf-8")
    assert html.count("<section data-markdown>") >= 7
    assert "ROWS BETWEEN" not in html or "A6" in html

    d_html = (tmp_path / "D.html").read_text(encoding="utf-8")
    mods = {m.code: m for m in parse_course(COURSE)}
    d_sections = render_module(mods["D"]).count("<section data-markdown>")
    assert d_sections == 1 + len(mods["D"].reference_sections)  # title + 10
    assert len(mods["D"].reference_sections) == 10
    for heading, _ in mods["D"].reference_sections:
        assert heading in d_html

    b2 = (tmp_path / "B2.html").read_text(encoding="utf-8")
    assert "| Standard SQL" in b2
    assert "QUALIFY" in b2
    assert "cdn.jsdelivr.net/npm/reveal.js@5/" in html


import pytest

from scripts.sql_sandbox import connect as sandbox_connect


@pytest.fixture
def con():
    c = sandbox_connect(md=False, fresh=True)
    yield c
    c.close()


def test_grade_identical_passes(con):
    from learning.sql_course.course import grade

    ok, why = grade(con, "select 1 as a, 2.00001 as b", "select 1 as a, 2.00004 as b")
    assert ok, why


def test_grade_column_set_mismatch(con):
    from learning.sql_course.course import grade

    ok, why = grade(con, "select 1 as a", "select 1 as b")
    assert not ok and "column" in why


def test_grade_row_count_mismatch(con):
    from learning.sql_course.course import grade

    ok, why = grade(con, "select 1 union all select 2", "select 1")
    assert not ok and "row count" in why


def test_grade_column_reorder_passes(con):
    from learning.sql_course.course import grade

    ok, why = grade(con, "select 1 as a, 2 as b", "select 2 as b, 1 as a")
    assert ok, why


def test_grade_duplicate_labels_fail(con):
    from learning.sql_course.course import grade

    ok, why = grade(con, "select 1 as a, 2 as a", "select 1 as a, 2 as a")
    assert not ok
    assert "ambiguous duplicate column labels" in why


def test_grade_catches_difference_past_row_20(con):
    from learning.sql_course.course import grade

    ok, why = grade(
        con,
        "select range as n from range(25)",
        "select case when range = 20 then -1 else range end as n from range(25)",
    )
    assert not ok


def test_grade_null_match_and_mismatch(con):
    from learning.sql_course.course import grade

    same = "select 1 as id, null as x union all select 2, 3.0"
    ok, why = grade(con, same, same)
    assert ok, why
    ok, why = grade(con, same, "select 1 as id, 0 as x union all select 2, 3.0")
    assert not ok


def test_grade_nan_match_and_mismatch(con):
    from learning.sql_course.course import grade

    nan_sql = "select 1 as id, 'NaN'::DOUBLE as x union all select 2, 3.0"
    ok, why = grade(con, nan_sql, nan_sql)
    assert ok, why
    # NaN must not compare equal to NULL
    ok, why = grade(con, nan_sql, "select 1 as id, null as x union all select 2, 3.0")
    assert not ok


def test_grade_struct_match_and_mismatch(con):
    from learning.sql_course.course import grade

    s = "select struct_pack(spread := 3.5, total := 50) as s"
    ok, why = grade(con, s, "select struct_pack(total := 50, spread := 3.5) as s")
    assert ok, why
    ok, why = grade(con, s, "select struct_pack(spread := 3.5, total := 51) as s")
    assert not ok


def test_grade_list_match_and_mismatch(con):
    from learning.sql_course.course import grade

    lst = "select [1, null, 3] as xs"
    ok, why = grade(con, lst, lst)
    assert ok, why
    ok, why = grade(con, lst, "select [1, 0, 3] as xs")
    assert not ok
    ok, why = grade(con, lst, "select [3, null, 1] as xs")
    assert not ok

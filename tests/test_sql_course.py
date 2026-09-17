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

# SQL Course Program Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan phase-by-phase. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Turn `cfb_sql_course.md` into a runnable learning program: slides per module, a CLI that grades exercise answers against the local warehouse, and progress tracking, with the course markdown as the single source of truth.

**Architecture:** One package `learning/sql_course/` holding the course markdown, a shared parser, a slide generator, a runner CLI, and per-module reference solutions. Everything executes through the existing `scripts/sql_sandbox.py` connection (warehouse read-only as `cfb`, scratch in `sandbox`). Reference results are computed live from the local warehouse at grade time, never copied from the course's claimed numbers.

**Tech Stack:** Python 3.14 + duckdb 1.5.5 (already in `.venv`), stdlib only. Slides are single-file HTML using reveal.js from a CDN with client-side markdown rendering, so no markdown library and no npm install.

**Spec:** the course itself, `C:\Users\mckel\Downloads\cfb_sql_course.md` (moves in-repo in Phase 1), plus the prompt that generated it, `docs/sql-course-perplexity-prompt-2026-09-16.md`.

## Global Constraints

- `CFB_DATA_ROOT` must be set; local `data\cfb.duckdb` is source of truth. `--md` only passes through to `sql_sandbox.connect`.
- NEVER write to the `cfb` catalog. Every learner object goes to `sandbox.main.<name>`.
- No new pip or npm dependencies. reveal.js is loaded from a CDN at view time, not installed.
- Data is never committed: progress lives in `data/sandbox.duckdb` (already gitignored).
- Course markdown is the only source of module text. Slides and exercise lists are generated, never hand-edited.
- Only files listed under **Files** are created or modified.

---

## Schema audit (done 2026-09-16)

**Question.** Does the course, written against `md:cfb`, match the local `data\cfb.duckdb` it will actually run on?

**Method.** `scripts/sql_course_schema_audit.py` parses every fenced ```` ```sql ```` block, resolves `schema.table` and `alias.column` references against `information_schema.columns` of the attached `cfb` catalog, executes each block in an in-memory scratch catalog, and compares the returned row count to the `-- rows: N` claim on line 2. Backticked `schema.table[.column]` mentions in prose are checked for existence too. Reproduce:

```bash
.venv/Scripts/python.exe scripts/sql_course_schema_audit.py "C:/Users/mckel/Downloads/cfb_sql_course.md" --out audit.md
```

**Data.** Local `cfb.duckdb` as of 2026-09-16 19:21 (file mtime), DuckDB v1.5.5. Course file dated 2026-09-16.

**Result.**

| metric | value |
|---|---|
| fenced sql blocks | 20 (one worked solution per module A1–C8) |
| blocks matching claimed row count | 17 |
| blocks failing locally | 2 |
| blocks with no numeric claim | 1 (B4, returns 5 buckets locally) |
| distinct prose `schema.table[.column]` refs | 15, all present |
| appendix "verified warehouse facts" re-checked | 10 of 10 match exactly (2012–2026 seasons, 3,747 / 3,745 / 54 games, 47,946 / 7,291 line rows, 86,640 odds rows, 410,845 ticks, 138 FBS, 15 postseason weeks, 44 missing away teams, C4 n=6,492 r=0.3777 slope=0.8517) |

Failing blocks:

| block | line | defect | fix for Phase 1 |
|---|---|---|---|
| B5 | 732 | `CREATE VIEW sandbox.main.v_game_totals AS SELECT … FROM core.fact_game` fails: a view created in the `sandbox` catalog resolves unqualified `core.*` against `sandbox`, not `cfb`. Verified: `FROM cfb.core.fact_game` works. | Course must qualify `cfb.core.…` inside every `CREATE VIEW` / `CREATE MACRO`; the intro "How the sandbox is wired" paragraph should say so. Affects B5 worked solution and exercises B5-2, B5-3. |
| C5 | 1008 | `width_bucket` does not exist in DuckDB 1.5.5 (`duckdb_functions()` has no such name). Also used in C1 exercise 1 and the C5 concepts text. | Replace with `least(floor(implied_home_prob * 10) + 1, 10)`; C1-1 uses `floor(total / 5)`. |

**What this does not support.** Only the 20 worked solutions were executed; the 100 numbered exercises have hints, not solutions, so their runnability is unverified until Phase 4 authors reference solutions. Column checks cover `alias.column` references and backticked prose only; bare column names in single-table blocks are validated by execution, not by name. Nothing was checked against `md:cfb`.

---

## Program shape

```
learning/sql_course/
  cfb_sql_course.md        # source of truth, copied verbatim from Downloads (Phase 1)
  course_parse.py          # markdown -> Module/Exercise/Block dataclasses (Phase 1)
  build_slides.py          # markdown -> slides/<module>.html + slides/index.html (Phase 2)
  course.py                # CLI: list | show | run | progress (Phases 3, 5)
  solutions/
    A1.sql … C8.sql        # reference solutions, one file per module (Phase 4)
  slides/                  # generated, committed (small HTML), regenerated by build_slides.py
scripts/sql_course_schema_audit.py   # exists; Phase 1 switches it to course_parse
tests/test_sql_course.py             # parser, grader, slide-count tests
```

**Runner flow.** `course.py run A3 2 --answer my.sql` loads exercise A3-2, executes `my.sql` in the sandbox, executes the reference from `solutions/A3.sql`, compares, prints PASS/FAIL with the first differing row, and upserts `sandbox.main.course_progress`. `course.py run A3 --worked` grades the learner against the module's worked solution block pulled straight from the markdown, so no solution file is needed for those 20.

**Grading rule** (`course.py:grade`): PASS when (a) row counts equal, (b) column-name sets equal, ignoring order and case, and (c) the first 20 rows of both results after `ORDER BY ALL` are equal, with DOUBLE values rounded to 4 places. Exercises whose answer is prose, intentionally random, or a side effect rather than a result set (marked `-- check: manual` in the solution file: A2-2, A6-5, B5-1, B5-4, B5-5, C2-3, C2-4, C4-4, C6-5) run the learner's SQL for errors only and record `manual`.

**Progress.** Table `sandbox.main.course_progress(module TEXT, exercise TEXT, status TEXT, attempted_at TIMESTAMPTZ)`, primary key `(module, exercise)`, written with `INSERT OR REPLACE`. `course.py progress` prints modules × exercises as a grid of `.`/`✓`/`m`.

**Slides.** One HTML file per module, built from these markdown sections in order: title (module heading + betting one-liner from the syllabus row), Learning goals, Standard → DuckDB table (Part B only), Concepts (split into one slide per paragraph), the worked-solution block as a code slide, Check yourself, Common mistakes, "Why it matters for betting" quote when present. Part D becomes one reference deck with one slide per `##` heading. `slides/index.html` links all 21 decks. reveal.js and its markdown plugin come from `https://cdn.jsdelivr.net/npm/reveal.js@5/` so the Python side only wraps markdown in `<section data-markdown><textarea data-template>` tags. Considered and rejected: Marp (needs `npx` download every run), marimo slides (installed, but 20 generated notebooks is more build than a 60-line wrapper).

---

## Phases

### Phase 1: Course in-repo, shared parser, audit rewired, course defects fixed

**Files:**
- Create: `learning/sql_course/cfb_sql_course.md` (copy of the Downloads file, then the two fixes below)
- Create: `learning/sql_course/__init__.py` (empty)
- Create: `learning/sql_course/course_parse.py`
- Modify: `scripts/sql_course_schema_audit.py` (import `parse_blocks` from `course_parse`, delete its local copy)
- Create: `tests/test_sql_course.py`

**Interfaces (produces):**

```python
@dataclass
class Block:      # a fenced sql block
    block_id: str; module: str; line: int; dialect: str; claimed: int | None; sql: str

@dataclass
class Exercise:
    module: str; number: int; text: str; hint: str

@dataclass
class Module:
    code: str            # "A1" … "C8", "D"
    title: str           # "Orientation"
    part: str            # "A" | "B" | "C" | "D"
    goals: list[str]
    dialect_table: str   # raw markdown table, "" outside Part B
    concepts: list[str]  # one entry per paragraph
    worked: Block | None
    exercises: list[Exercise]
    check_yourself: str
    mistakes: list[str]
    why_betting: str     # the "> **Why it matters" quote or ""

def parse_course(text: str) -> list[Module]: ...
def parse_blocks(text: str) -> list[Block]: ...   # moved from the audit script unchanged
```

- [x] Copy the course: `cp "/c/Users/mckel/Downloads/cfb_sql_course.md" learning/sql_course/cfb_sql_course.md`.
- [x] Apply the two audit fixes in the copy: B5 worked block and hints for B5-2/B5-3 use `cfb.core.fact_game`; intro paragraph gains one sentence "Inside `CREATE VIEW`/`CREATE MACRO` in `sandbox`, qualify warehouse tables as `cfb.core.…`". C5 worked block and C1 exercise 1 replace `width_bucket` as in the audit table.
- [x] Write the failing test first:

```python
from learning.sql_course.course_parse import parse_course, parse_blocks
COURSE = Path("learning/sql_course/cfb_sql_course.md").read_text(encoding="utf-8")

def test_parse_course_shape():
    mods = parse_course(COURSE)
    assert [m.code for m in mods] == ["A1","A2","A3","A4","A5","A6","A7","B1","B2","B3","B4","B5",
                                      "C1","C2","C3","C4","C5","C6","C7","C8","D"]
    assert all(len(m.exercises) == 5 for m in mods if m.code != "D")
    assert all(m.worked is not None for m in mods if m.code != "D")
    assert all(len(m.goals) == 5 for m in mods if m.code != "D")
    assert mods[7].dialect_table.startswith("| Standard SQL")
    assert len(parse_blocks(COURSE)) == 20
```

- [x] Run `python -m pytest tests/test_sql_course.py -v`; expect ImportError.
- [x] Implement `course_parse.py`: walk lines, open a module on `^## ([A-C]\d) — (.+)$` or `^# Part D`, switch section on `^### ` headings, collect `- ` bullets under goals/mistakes, paragraphs under concepts, `^\d\. (.+?) \*Hint: (.+)\*$` under exercises, and reuse `parse_blocks` for worked solutions (first block whose `line` falls inside the module's line range).
- [x] Rewire the audit script to `from learning.sql_course.course_parse import parse_blocks` and rerun it against the in-repo copy.
- [x] **Check:** `python -m pytest tests/test_sql_course.py` passes, and the audit reports `20 blocks: 19 ok, 0 mismatch/error/missing, 1 unverifiable` (B5 and C5 now pass).
- [x] Commit: `feat(learning): move SQL course in-repo with shared parser`

Estimate: about 2 hours.

### Phase 2: Slides

**Files:**
- Create: `learning/sql_course/build_slides.py`
- Create: `learning/sql_course/slides/*.html` (generated: A1…C8, D, index)
- Modify: `tests/test_sql_course.py` (add `test_build_slides`)

**Interfaces:** `render_module(m: Module) -> str` returns a full HTML document; `build_all(course_path: Path, out_dir: Path) -> list[Path]`.

- [x] Test first:

```python
def test_build_slides(tmp_path):
    from learning.sql_course.build_slides import build_all, render_module
    paths = build_all(Path("learning/sql_course/cfb_sql_course.md"), tmp_path)
    assert len(paths) == 22                       # 21 decks + index
    html = (tmp_path / "A4.html").read_text(encoding="utf-8")
    assert html.count("<section data-markdown>") >= 7   # title, goals, ≥1 concept, worked, check, mistakes, why
    assert "ROWS BETWEEN" not in html or "A6" in html    # no cross-module bleed
```

- [x] Run it; expect ImportError.
- [x] Implement: one `TEMPLATE` string with reveal.js CSS/JS `<link>`/`<script>` from `https://cdn.jsdelivr.net/npm/reveal.js@5/dist/` plus `plugin/markdown/markdown.js`; `render_module` yields one `<section data-markdown><textarea data-template>…</textarea></section>` per slide from the Module fields in the order listed under **Slides** above; escape `</textarea>` if it ever appears. Index page is a plain `<ul>` of links with module titles.
- [x] Run `python learning/sql_course/build_slides.py` to regenerate `slides/`.
- [x] **Check:** test passes, and opening `learning/sql_course/slides/B2.html` in a browser shows the Standard → DuckDB table rendered as an HTML table on slide 2 and the `QUALIFY` worked solution as a highlighted code slide.
- [x] Commit: `feat(learning): generate reveal.js slides from the SQL course`

Estimate: about 1.5 hours.

### Phase 3: Runner CLI grading against worked solutions

**Files:**
- Create: `learning/sql_course/course.py`
- Modify: `tests/test_sql_course.py` (add grader tests)

**Interfaces:**

```python
def grade(con, learner_sql: str, reference_sql: str, sample: int = 20) -> tuple[bool, str]:
    """Returns (passed, reason). reason is "" on pass, else the first failing rule."""
def run_sql(con, sql: str) -> tuple[list[str], list[tuple]]:   # column names, rows (ORDER BY ALL applied)
```

CLI: `course.py list` (modules and exercise texts), `course.py show A3` (goals, concepts, exercises with hints), `course.py run A3 --worked --answer my.sql`, `course.py run A3 2 --answer my.sql` (Phase 4 enables the numbered form).

- [x] Grader tests first, using `connect(md=False, fresh=True)` from `scripts/sql_sandbox.py`:

```python
def test_grade_identical_passes(con):
    ok, why = grade(con, "select 1 as a, 2.00001 as b", "select 1 as a, 2.00004 as b")
    assert ok, why
def test_grade_column_set_mismatch(con):
    ok, why = grade(con, "select 1 as a", "select 1 as b")
    assert not ok and "column" in why
def test_grade_row_count_mismatch(con):
    ok, why = grade(con, "select 1 union all select 2", "select 1")
    assert not ok and "row count" in why
```

- [x] Run; expect ImportError.
- [x] Implement `run_sql` as `con.sql(f"SELECT * FROM ({sql.rstrip(';')}) ORDER BY ALL LIMIT {sample}")` plus a separate `count(*)`; `grade` checks count, then `set(map(str.lower, cols))`, then row tuples with floats rounded to 4 places. Multi-statement answers (B5, C7 style) execute all but the last statement first, then grade the last.
- [x] Implement the CLI with `argparse` subparsers; `run --worked` takes the reference from `Module.worked.sql`.
- [x] **Check:** tests pass; `python learning/sql_course/course.py run A1 --worked --answer /tmp/a1.sql` where `a1.sql` is the A1 worked solution prints `PASS`, and the same file with `LIMIT 10` appended prints `FAIL: row count 10 != 3747`.
- [x] Commit: `feat(learning): add SQL course runner with worked-solution grading`

Estimate: about 2 hours.

### Phase 4: Reference solutions for the 100 exercises

**Files:**
- Create: `learning/sql_course/solutions/A1.sql` … `C8.sql` (20 files)
- Modify: `learning/sql_course/course.py` (numbered-exercise form reads `solutions/<module>.sql`)
- Modify: `tests/test_sql_course.py` (add `test_every_solution_runs`)

**Solution file format** (parsed by `course.py:load_solutions(module) -> dict[int, tuple[str, str]]` returning `{n: (check_mode, sql)}`):

```sql
-- exercise: 1
-- check: exact
SELECT table_schema, table_name FROM information_schema.tables WHERE table_schema = 'core' ORDER BY ALL;

-- exercise: 2
-- check: manual
...
```

- [x] Test first: parametrize over all 20 modules; for each numbered exercise, assert a solution exists, `check` is `exact` or `manual`, and the SQL executes without error against `connect(md=False, fresh=True)`.
- [x] Author solutions module by module in course order (A1→C8). Each must follow the exercise text and its hint, use `sandbox.main.` for anything created, qualify `cfb.core.…` inside views and macros, and carry `-- check: manual` only for the nine prose/random/side-effect exercises listed under **Grading rule**. Run the test after each module.
- [x] Extend `course.py run MODULE N` to grade against `load_solutions`.
- [x] **Check:** `python -m pytest tests/test_sql_course.py -k solution` passes for 100 exercises, and `course.py run A4 2 --answer x.sql` passes when `x.sql` is the A4-2 solution.
- [x] Commit per part: `feat(learning): reference solutions for Part A`, then B, then C.

Estimate: about 6 hours total (Part A 1.5, Part B 2, Part C 2.5). This is the long phase and can be split across sessions by part.

### Phase 5: Progress tracking

**Files:**
- Modify: `learning/sql_course/course.py` (`record`, `progress` subcommand)
- Modify: `tests/test_sql_course.py` (add `test_progress_upsert`)

- [x] Test first: with `fresh=True`, `record(con, "A1", "worked", "pass")` twice then `progress_rows(con)` has exactly one row with status `pass`. (2026-09-17)
- [x] Implement `CREATE TABLE IF NOT EXISTS sandbox.main.course_progress(module TEXT, exercise TEXT, status TEXT, attempted_at TIMESTAMPTZ, PRIMARY KEY (module, exercise))` and `INSERT OR REPLACE`. `run` calls `record` after grading with `pass`, `fail`, or `manual`. `progress` prints the grid. (2026-09-17)
- [x] **Check:** test passes; after `course.py run A1 --worked --answer a1.sql`, `python scripts/sql_sandbox.py -c "FROM sandbox.main.course_progress"` shows one `A1 | worked | pass` row, and running it again does not add a second. (2026-09-17)
- [x] Commit: `feat(learning): track SQL course progress in the sandbox`

Estimate: about 45 minutes.

---

## Out of scope

- Any web UI or notebook front end; the CLI and static HTML slides are the whole program.
- Grading prose answers ("explain why…"), randomised outputs (`USING SAMPLE`, bootstrap), `EXPLAIN` output, and `SHOW DATABASES`; these are `manual`.
- Exercises for Part D (the course has none).
- MotherDuck-specific verification beyond passing `--md` through to the sandbox connection.
- Vendoring reveal.js for offline use (add `slides/vendor/` later if needed; the generator only changes two URLs).
- Hints beyond the course's one-liners, spaced repetition, or LLM-generated feedback.
- Fixing anything in the course other than the two audit defects.

## Self-review

- Spec coverage: program shape, per-module runner with count + column set + ordered sample grading, progress in `sandbox.duckdb`, slides for every module's goals/concepts/mistakes and a Part D deck, zero new dependencies, file list, ordered phases with one check each, out-of-scope list: all present.
- Placeholder scan: none.
- Type consistency: `Block`, `Module`, `Exercise`, `grade`, `run_sql`, `load_solutions`, `record`, `build_all`, `render_module` are named identically across phases.

# Plan: SQL Course Program

_Locked via claudex-loop — by Claude + mckel_

## Goal

Turn `cfb_sql_course.md` into a runnable learning program: slides per module, a CLI
that grades exercise answers against the local warehouse, and progress tracking,
with the course markdown as the single source of truth. Reference results are
always computed live at grade time against the local warehouse, never copied from
the course's claimed numbers.

## Approach

One package `learning/sql_course/` holds the course markdown, a shared parser, a
slide generator, a runner CLI, and per-module reference solutions. Everything
executes through the existing `scripts/sql_sandbox.py` connection (warehouse
read-only as `cfb`, scratch in `sandbox`).

1. **Phase 1 — Course in-repo, shared parser, audit rewired, defects fixed.**
   Copy the course markdown in, apply the two audit-found fixes (B5 catalog
   qualification, C5's `width_bucket`), write `course_parse.py` (`parse_course`,
   `parse_blocks`), rewire `scripts/sql_course_schema_audit.py` to import the
   shared parser instead of keeping its own copy.
2. **Phase 2 — Slides.** `build_slides.py` renders one reveal.js HTML deck per
   module from the parsed `Module` fields, plus a Part D reference deck and an
   `index.html`. reveal.js loads from a CDN; no new dependency.
3. **Phase 3 — Runner CLI, worked-solution grading.** `course.py` with `list`,
   `show`, `run --worked`, and `grade`/`run_sql`, exercised against the 20 worked
   solutions embedded in the course markdown.
4. **Phase 4 — Reference solutions for the 100 exercises.** One `.sql` file per
   module in `solutions/`, each exercise tagged with a check mode (`exact`,
   `probe`, or `manual`); extends the runner to grade numbered exercises.
5. **Phase 5 — Progress tracking.** `sandbox.main.course_progress` table,
   `course.py progress` grid.

## Key decisions & tradeoffs

- **Grading gap beyond the plan's original 9 `manual` exercises (Q1, locked).**
  Schema audit + exercise-list recon found 7 more exercises whose answer is a
  bare `CREATE MACRO`/`CREATE TABLE` with no result set: B5-2, B5-3, C8-1
  through C8-4. C2-5 also can't be `exact` — it compares against C2-4's random
  bootstrap. Decision: add a third check mode, **`probe`**. The solution file
  names a follow-up query against the created object; `grade` runs the
  learner's CREATE, then runs the probe on both the learner's and reference's
  connections and diffs *that* result with the normal `exact` rule. C2-5 and
  the original 9 stay `manual`. Rejected: folding all 16 into `manual` — the
  capstone module would ship with zero automated feedback.
  - **Probe syntax corrected (Codex round 1, finding 5).** B5-2 creates a
    *scalar* macro. The probe is a scalar projection —
    `-- probe: SELECT sandbox.main.american_to_prob(-150)` — not a table-valued
    `SELECT * FROM sandbox.main.american_to_prob(-150)`, which DuckDB rejects
    ("Table Function ... does not exist"). B5-3's table macro *is*
    table-valued: `-- probe: SELECT * FROM sandbox.main.season_games(2024)`.
    Solution-file authoring must match the object's kind.
  - **Probe extended to schema, not just data (Codex round 1, finding 6);
    strengthened again in round 2 (finding 4) after a single probe input and
    plain `DESCRIBE` proved too weak to catch a materially wrong
    implementation.** A single-input probe (`SELECT
    sandbox.main.american_to_prob(-150)`) passes a macro that ignores its
    argument and always returns a constant, or one that's only correct for
    negative odds. Plain `DESCRIBE` catches a wrong column type but not a
    missing uniqueness/primary-key constraint the exercise actually cares
    about (C8-2's `bet_id`, C8-3's SCD-2 natural key). Fix:
    - The solution-file format allows **multiple** `-- probe:` lines per
      exercise; all must pass. For B5-2's macro, probes cover a negative-odds
      case, a positive-odds case, and the odds = 0 edge (`-100`, `+150`, `0`).
      For B5-3's table macro, probes cover two different `yr` arguments.
    - For a `CREATE TABLE`-only exercise (C8-2, C8-3), the probe is
      `DESCRIBE sandbox.main.<object>` for column name/type, **plus** — only
      where the exercise text names a key or uniqueness requirement — a second
      probe against `duckdb_constraints()` filtered to that table, so a
      missing `PRIMARY KEY`/`UNIQUE` is caught, not just column shape.
      `grade` recognizes a probe starting with `DESCRIBE` or
      `SELECT ... FROM duckdb_constraints()` and applies the ordinary
      name-aligned comparison to its own result set — no separate code path.
- **Learner/reference isolation (Q2, locked).** Both sides create identically
  named `sandbox.main.<name>` objects. Decision: every `course.py run` opens
  `connect(md=False, fresh=True)` for grading — the learner's SQL and the
  reference SQL each get their own in-memory `sandbox` catalog. No name
  collisions, no run-order dependence, reruns are idempotent. Any exercise that
  conceptually "reuses" an earlier module recomputes what it needs inline in
  its own solution file rather than depending on a prior `run` having executed.
  - **Applies within a module too, not just across modules (Codex round 1,
    finding 9).** C7-2's own exercise text says "from `backtest_result`" — the
    table C7-1's worked solution creates. Under fresh-per-run grading, C7-2's
    *reference solution* must recompute the C7-1 backtest inline (a CTE, not a
    table read), because there is no persisted `backtest_result` in a fresh
    connection. This was already the rule for C8-4 reusing C7; it now applies
    to any exercise whose text names an object built earlier in the same
    module. Learners doing the course interactively will naturally accrete
    state in `data/sandbox.duckdb` via `sql_sandbox.py`'s REPL; but the
    `--answer` file they submit to `course.py run` for grading is held to the
    same self-contained standard as the reference, since it runs in the same
    kind of fresh connection. State this explicitly in Phase 4's authoring
    note and in `course.py show`'s exercise text where it's non-obvious.
  - **Progress persistence does not use the fresh grading connection (Codex
    round 1, finding 3 — direct contradiction in the original lock).** Writing
    `sandbox.main.course_progress` through a `fresh=True` in-memory connection
    means the row vanishes the instant the connection closes, defeating Phase
    5 entirely. Decision: `course.py run` uses two connections — the
    `fresh=True` in-memory one for grading (learner SQL + reference SQL, as
    locked above), and a second, short-lived connection against the real
    `connect(md=False, fresh=False)` (i.e. `data/sandbox.duckdb`) opened only
    to `INSERT OR REPLACE` the one progress row after grading completes, then
    closed. A `duckdb.IOException` from that connection (another process
    holding the file, e.g. an open `sql_sandbox.py` REPL) is caught and
    reported as "progress not recorded: sandbox.duckdb is locked by another
    process" — the grade verdict itself (PASS/FAIL/manual) still prints.
- **Grading correctness fixes (Codex round 1 findings 1 & 2; corrected again
  in round 2 finding 1 after my first fix reintroduced the bug).** The
  original rule compared only the first 20 rows after `ORDER BY ALL`
  (sample-only, round-1 #1) and aligned columns by name-set while comparing
  row values positionally (round-1 #2). My round-1 fix still wrapped queries
  in `SELECT * FROM (<sql>) ORDER BY ALL` before aligning — but that wrapper's
  own `ORDER BY ALL` sorts by the *original* column position, so
  `select 1 as a, 2 as b` vs. `select 2 as b, 1 as a` can still land in
  different row order before alignment happens, and — separately confirmed —
  the wrapper silently renames a genuine duplicate label (`select 1 as a, 2 as
  a`) to `a, a_1`, so duplicate-label detection done *after* wrapping always
  reports zero duplicates. Both reproduced directly in DuckDB 1.5.5. Corrected
  design for `run_sql`/`grade`:
  1. Execute the **raw** SQL, unwrapped (`con.execute(sql.rstrip(';'))`), and
     read `cursor.description` immediately for the true, as-authored column
     labels — before any `SELECT *` re-projection can rename anything.
  2. If `len(set(map(str.lower, columns))) != len(columns)`: fail immediately
     with `"ambiguous duplicate column labels: <name>"`; this check now runs
     against labels DuckDB hasn't touched.
  3. Otherwise fetch all rows (see the size/timeout/memory fix below for what
     bounds this), and for **each row independently**, zip it with the
     lowercased column names, sort by name (column-order-independent
     alignment), and **round every numeric value to 4 places in this same
     step, before any sorting of rows happens** — producing a fully
     canonical, comparison-ready tuple per row.
  4. Build one **canonicalization key** per value, used identically for both
     sorting and equality (round 4 fix, after a round-3 design that kept the
     raw `None`/NaN value alongside a flag still crashed comparing `None`
     against NaN, and — separately — two fetched NaN values compared
     unequal since bare `float('nan') == float('nan')` is `False` in Python):
     `None → (0, 0, "")`; a float NaN → `(0, 1, "")` (distinct rank from
     `None`, so the two null-like cases never collide with each other, but
     both always sort before real values and both compare equal to their own
     kind by ordinary tuple equality); any other scalar, rounded to 4 places
     first if numeric → `(1, 0, value)`. Verified: mixed `None`/NaN/numeric
     rows sort and compare correctly with no exception.
     - **The key must recurse into `LIST`/`STRUCT` values, not treat them as
       opaque scalars (round 5 finding 1).** B3 is a whole module about
       semi-structured data — `struct_pack` results (B3-4) and unnested list
       columns (B3-3, B4-2/B4-3-adjacent) are ordinary, expected exercise
       output, not an edge case. DuckDB returns a `STRUCT` as a Python `dict`
       and a `LIST` as a Python `list`; both are unorderable against each
       other in Python (`TypeError: '<' not supported between dict and
       dict`), and a `list` containing a `None` hits the same original
       None-vs-value crash one level down. Fix: the key function recurses —
       a `dict` becomes `(2, 0, tuple(sorted((k, key(v)) for k, v in
       d.items())))` (sorted by field name so field order can't cause a
       false mismatch); a `list`/`tuple` becomes
       `(3, 0, tuple(key(v) for v in seq))` (position-preserving, since list
       order is meaningful, unlike struct field order); everything else uses
       the scalar rule above. This is the same function calling itself, not
       new machinery.
  5. Sort the list of canonical tuples (rounding happened in step 4, before
     this sort — round-2 rounded after sorting, which let two rows that are
     only distinguishable at full precision get paired with the wrong
     counterpart row post-rounding; reproduced and fixed by moving rounding
     into the per-value key). This Python-level sort replaces the SQL-level
     `ORDER BY ALL` entirely.
  6. Compare row counts, then column-name sets (case-insensitive), then the
     two sorted canonical tuple lists elementwise; report the first
     differing index, capped to the first 20 *displayed* in the FAIL
     message — the 20 is a display cap only, every row is compared.
- **Grading execution gets a real cancellation path and a memory ceiling, not
  just a wall-clock label (Codex round 1 finding 12; corrected in round 2
  finding 5 after my first fix didn't actually bound anything).** A
  Python-side timer that just stops *waiting* on `con.execute()` doesn't stop
  DuckDB's C++ engine from continuing to compute and allocate in the
  background, and nothing bounded memory before any timeout fired at all —
  `fetchall()` on a learner's accidental cross join can exhaust memory in well
  under 10 seconds. Fix, applied only to grading connections
  (`course.py`'s `connect(md=False, fresh=True)` calls, not
  `scripts/sql_sandbox.py`'s interactive REPL, which is unmodified):
  - Immediately after opening a grading connection: `SET memory_limit='2GB'`
    and `SET max_temp_directory_size='2GB'` (down from the interactive
    defaults of 12.5GB / 90% of free disk), so a runaway query hits DuckDB's
    own `OutOfMemoryException` and is caught and reported as
    `FAIL: out of memory` rather than degrading the machine.
  - A timeout thread calls `con.interrupt()` (DuckDB's real query-cancellation
    API, callable from a different thread than the one executing the query)
    after 10 seconds; the interrupted `execute()` raises, caught and reported
    as `FAIL: exceeded 10s`. This actually stops the engine, not just the
    caller's wait.
  - **DuckDB's `memory_limit` does not bound Python-side memory (round 3
    finding 3), and `con.interrupt()` cannot stop Python-level sorting after
    the fetch completes.** My round-3 fix — reject upfront if row count
    exceeds 50,000 — was wrong in a different way (round 4 finding 2,
    reproduced directly against the local warehouse): B3-3's unnest legitimately
    returns 183,942 rows and A4-3's self-join legitimately returns 370,902;
    a flat row cap rejects correct answers to real exercises, and there's no
    row-count threshold that's simultaneously "above every legitimate
    exercise result" and "below a real problem," because the course's own
    exercises already span that range. Separately (round 4 finding 3,
    reproduced), a *row* cap doesn't bound *cell* size — 50 rows of a
    100,000-character string allocated ~5MB in Python under a 1MB DuckDB
    limit that never tripped, so row count and memory cost aren't even
    proportional. Fix: replace the row-count gate with a **byte-budget gate
    on the fetch itself**, which bounds the actual failure mode (Python
    memory) directly instead of proxying through row count: fetch in batches
    via `cursor.fetchmany(5000)` rather than one `fetchall()`; after each
    batch, accumulate a size estimate and abort with
    `FAIL: result too large to grade (exceeded 200MB)` if the running total
    passes 200MB, and re-check the 10s wall-clock budget between batches too
    (a result can finish computing inside DuckDB but still take a while to
    fetch and compare). 400,000 rows of small ints/floats/strings (B3-3,
    A4-3's actual shape) stay well under 200MB; a pathological wide-cell or
    genuinely unbounded result hits the byte budget or the timeout first,
    whichever comes sooner.
    - **The size estimate must recurse, not just measure the container
      (round 5 finding 2).** `sys.getsizeof(v)` alone is shallow — a `list`
      of two 100,000-character strings measured **88 bytes** this way,
      against roughly 200,000 actual bytes, a ~2000x undercount, verified
      directly. Fix: the same recursion shape as the comparison key — a
      helper that adds `sys.getsizeof` of the container itself to the sum of
      the same helper applied to each element (`list`/`tuple`) or to each
      key and value (`dict`), and just `sys.getsizeof(v)` for anything else
      — applied per value in each fetched batch. This reuses the same
      list/struct recursion the comparison key already needs, just measuring
      instead of canonicalizing.
- **"Read-only" is a naming convention, not a security boundary (Codex round
  1, finding 4) — accepted as a documented non-goal, not redesigned.** The
  `cfb` attachment is DuckDB `READ_ONLY`, which stops writes to the warehouse
  catalog; it does not sandbox the process (a learner's SQL can still read
  arbitrary files DuckDB can reach, and B5-4 explicitly teaches
  `COPY ... TO 'games_2024.parquet'`, i.e. filesystem writes are an intended
  exercise, not a leak). This is fine for a single-user tool grading the
  user's own submitted files on their own machine, the same trust level as
  running any script they wrote. Rejected: adding a restricted-output-directory
  jail or disabling external file access — out of proportion to the actual
  threat model here. Documented in Phase 3's module docstring so it isn't
  mistaken for a security control later.
- **Phase 1 check-gate corrected.** The original phrasing ("19 ok, 0
  mismatch/error/missing, 1 unverifiable") is wrong. B4 and C5 both lack a
  numeric `-- rows:` claim (C5's line 2 is prose, `-- rows: (one per non-empty
  decile, <= 10)`, which the audit's `ROWS` regex never matches even after the
  `width_bucket` fix makes the block executable). Correct target: **18 ok, 0
  mismatch/error/missing, 2 unverifiable** (B4, C5).
- **Grader rounding by type, not by "DOUBLE."** DuckDB parses bare decimal
  literals (`2.00001`) as `DECIMAL`, not `DOUBLE`. The rounding rule in `grade`
  rounds any numeric column to 4 places regardless of whether DuckDB reports it
  as `DECIMAL` or `DOUBLE`; the Phase 3 test's literals must actually exercise
  that path (verified: `typeof(2.00001)` → `DECIMAL(6,5)` in this DuckDB build).
- **Part C parser mapping.** Part C modules use `### The idea, then the SQL,
  then the reading` where Parts A/B use `### Concepts`. `course_parse.py` maps
  both headings to `Module.concepts`.
- **Title slide source.** No per-module betting one-liner exists in the course.
  Title slide is the module heading (code + title) plus that Part's row from the
  "Syllabus at a glance" table (focus + dialect).
- **`why_betting` is A1-only.** Only A1 carries a "Why it matters for betting"
  quote in the whole course. `Module.why_betting` defaults to `""`; no fixed
  count of modules is asserted to have it.
- **Part D deck boundary.** The reference deck covers `# Part D` through the
  section immediately before `# Appendix` (line 1302). The appendix ("Verified
  warehouse reference card") is not part of the D deck.
- **Shared `Block` dataclass.** `course_parse.Block` carries the audit's five
  extra fields (`tables`, `columns`, `missing`, `local_rows`, `status`) as
  defaulted, unused-by-the-course-CLI fields, so
  `scripts/sql_course_schema_audit.py` can delete its own `Block` and import the
  shared one unchanged.
- **`Module` interface gains fields the slide/title design needs (Codex round
  1, finding 11).** The original interface (`docs/sql-course-program-plan-
  2026-09-16.md`) has no field for the "title slide = module heading + Part's
  syllabus row" decision above, and no structure for Part D's own titled
  sections (`## Layout and formatting`, `## Naming`, … through `## Anti-
  patterns`). Fix: `Module` gains `part_focus: str` and `part_dialect: str`
  (copied from the matching row of "Syllabus at a glance" during parsing, not
  looked up at render time), and a Part D module carries
  `reference_sections: list[tuple[str, str]]` (heading, body) instead of
  populating `concepts`/`exercises`/etc. — those stay empty for `code == "D"`.
  `test_build_slides` must assert the D deck actually renders one slide per
  `reference_sections` entry (**10**, per the `## ` headings from "Layout and
  formatting" through "Anti-patterns" — corrected in Codex round 2 finding 6
  after my round-1 fix asserted 12, an uncounted guess; verified by direct
  grep: Layout and formatting, Naming, Grain/CTEs/structure, Joins and
  projection, Fan-out and dedupe discipline, NULL and NaN discipline, Dates
  and timezones, Idempotency/immutability/provenance, Comments and
  performance, Anti-patterns), not just that `D.html` exists — otherwise a
  build that silently drops Part D's content still passes the deck-count
  check.
- **Three more course defects get fixed in-repo, same precedent as B5/C5
  (Codex round 1 findings 7 & 10; round 2 finding 2 rejected my first answer
  of "leave the hints, just document the divergence in solution files").**
  Round 1 confirmed three exercise hints reference DuckDB behavior that
  doesn't hold: A2-5's `x <> x` never detects NaN (DuckDB treats `NaN = NaN`
  as true, the opposite of IEEE 754, so `<>` is always false for NaN); B2-4's
  `list_distinct(provider_key)` errors on a scalar column (it takes a list);
  C3-1's `erf` does not exist as a DuckDB function. My first answer — keep the
  course text as-is, note the divergence only in the Phase-4 solution file —
  left the learner following the course's own printed instructions straight
  into a runtime error, with the correction visible only in a file they have
  no reason to open before attempting the exercise. Round 2 is right that this
  under-serves the actual learner. Revised decision: extend the **already-
  established** in-repo-fix mechanism (the Phase 1 checklist already edits the
  copied course markdown for B5 and C5) to these three hints as well — same
  file, same step, same precedent, not a new mechanism:
  - A2-5: the full numbered line is corrected, not just its trailing hint
    clause (round 4 finding 4 — my round-2/3 fixes touched only the *Hint:*
    sentence and left the exercise's own body reading "a value where the
    number does not equal itself," which is the textbook IEEE-754 definition
    of NaN and reads as tacit support for trying `x <> x` again). Corrected
    line: *"Detect any DOUBLE column value that is NaN rather than NULL in
    `stg.game` (e.g. `excitement`) using `isnan(x)`. Hint: DuckDB defines
    `NaN = NaN` as TRUE, unlike IEEE 754, so `x <> x` never fires — use
    `isnan()` instead."*
  - B2-4: hint becomes *"`list_distinct(list(provider_key))` after
    `GROUP BY game_id` — `list_distinct` takes a list, not a scalar column"*.
  - C3-1: hint becomes the course's own inline polynomial approximation of the
    normal CDF (Abramowitz–Stegun), since DuckDB has no `erf`; Concepts gains
    one sentence noting DuckDB lacks a native error function.
  C8-1 is different in kind — `UNION BY NAME` *runs*, it just doesn't satisfy
  ADR-0001's merged-table contract (no row gets tagged `'both'`). This isn't a
  broken-function fix, it's a modelling-correctness gap, so it stays a
  Phase-4-authoring decision rather than a markdown edit: the hint gains one
  clause, *"then resolve any shared game key to a single row tagged
  `'both'`"*, and the reference solution uses a `full outer join` +
  `coalesce` keyed on the shared game identifier, not a literal `UNION BY
  NAME`.
  - **The `x <> x` defect repeats twice more outside A2-5 (Codex round 3
    finding 4).** Part D's "NULL and NaN discipline" section states "detect
    NaN with `x <> x`" and its "Anti-patterns" list repeats the same fix for
    `coalesce(x, 0)` — both independent of A2-5's hint, and both would reach
    the generated Part D reference deck verbatim as false instruction if left
    alone. Both get the same correction as A2-5: replace `x <> x` with
    `isnan(x)` in both Part D passages, plus one clause noting DuckDB departs
    from IEEE 754 here (`NaN = NaN` is true), which is *why* `<>` doesn't
    work — the same fact, not just the same fix, so the two Part D mentions
    and A2-5 read as one consistent correction rather than three
    coincidentally-matching patches.
  - Phase 1's checklist and check gate are updated to cover **six** markdown
    edits (B5, C5, A2-5, B2-4, C3-1, and Part D's two `x <> x` passages —
    counted as one edit since both land in the same fix) plus the C8-1 hint
    clause. The audit's own "what this does not support" note is unaffected —
    none of these are in the 20 audited worked-solution blocks (the audit
    only covers fenced ```` ```sql ```` blocks; these are prose/hint-text
    issues), so no audit gate wording changes.
- **Ambiguous exercises get a documented tiebreak, surfaced to the learner
  before they attempt it, not just recorded in the solution file (Codex round
  1 finding 8; round 2 finding 3 rejected "documented in the solution header"
  as sufficient).** A few exercise texts under-specify the answer (B4-1/B2-5
  ask for "one 2024 game" without saying which; A2-1 asks for "20 games" with
  no `ORDER BY`), so `exact` grading against one reference row order/selection
  can fail an equally-correct learner answer that made a different valid
  choice. My first answer documented the tiebreak only in the solution file's
  header comment — a file the learner has no reason to read before attempting
  the exercise, so a reasonable answer still fails with no visible
  explanation why. Revised: the solution file format gains an optional
  `-- note: <text>` line (alongside `-- exercise:`/`-- check:`/`-- probe:`);
  `course.py show MODULE` prints any exercise's note next to its hint, so the
  tiebreak/required-alias/selection-rule is visible *before* grading, not
  discovered by reading the answer key. Phase 4 sets `-- note:` on every
  exercise where `exact`/`probe` grading depends on something the exercise
  text itself doesn't pin down (B4-1, B2-5, A2-1, and any other case found
  during authoring). Reserve `manual` for exercises whose entire teaching
  point *is* that multiple answers are valid — none of B4-1/B2-5/A2-1 qualify,
  the ambiguity there is incidental wording, not the lesson.

## Toolchain

None. Skill inventory scan (both benches: `~/.claude/skills`, `~/.agents/skills`)
found `test-driven-development` on both — proposing Phase 1/3/4's test-first
steps follow it, since each phase's plan already writes a failing test before
implementation. `sql-expert` (generic Postgres/MySQL/SQLite/SQL Server, not
warehouse-aware) and `duckdive` (MotherDuck interactive-viz generator, not
static reveal.js slides) do not fit this task and are not loaded.

## Assumptions

1. `CFB_DATA_ROOT` set, local `data\cfb.duckdb` is source of truth — confirmed,
   env check (`.venv` Python 3.14.6, duckdb 1.5.5).
2. Course markdown source at `C:\Users\mckel\Downloads\cfb_sql_course.md`, 1,328
   lines, 21 module headings (A1–A7, B1–B5, C1–C8, Part D), 20 worked-solution
   blocks, 100 numbered exercises, all matching `N. text *Hint: …*` — confirmed,
   direct read + grep.
3. `learning/sql_course/PLAN.md` and `PLAN-REVIEW-LOG.md` live under
   `learning/sql_course/`, not repo root — root `PLAN.md` is the already-committed
   warehouse-rationalization plan (`git log -- PLAN.md` → `8961833`). Source:
   [[claudex-loop-plan-md-collision]] memory + git log.
4. `scripts/` is a namespace package; tests do `from scripts.x import y` with no
   `__init__.py` and no `conftest.py`. `pytest.ini` sets `testpaths = tests`,
   default-excludes the `slow` marker. `learning/sql_course/__init__.py` (empty)
   fits this convention. Source: `tests/test_check_an_tick_pin.py`, `pytest.ini`.
5. `CONTEXT.md` and 3 ADRs exist (`docs/adr/0001`–`0003`). No glossary term
   collides with `module`, `exercise`, `worked solution`, or `grade`. Source:
   direct read.
6. Codex reviewer: `codex-cli 0.151.0`, model pinned `gpt-6-astra` in
   `~/.codex/config.toml`, config `sandbox = "elevated"` / `approval_policy =
   "never"` — so the skill's forced `-s read-only` / `-c sandbox_mode="read-only"`
   flags are load-bearing, not redundant with config defaults. Source:
   `codex --version`, `~/.codex/config.toml`.
7. Skill inventory: no threejs/game-style pack relevant; `test-driven-development`
   present on both benches (see Toolchain); `sql-expert` and `duckdive` present
   but don't fit.

## Risks / open questions

- **`grade`'s comparator is the highest-risk piece of this plan.** Five rounds
  of Codex review each found a bug in the *previous* round's fix to it (NULL
  vs. NaN sort/equality, rounding order relative to sorting, row-count vs.
  byte-budget bounding, scalar-only vs. recursive `STRUCT`/`LIST` handling).
  Phase 3's test suite must cover, beyond the three scalar cases already
  specified: a `NULL`-containing column, a NaN-containing column, a `STRUCT`
  result (B3-4 shape), and a `LIST` result (B3-3 shape) — each compared for
  both a correct match and an intentionally wrong answer, so a regression in
  any of these dimensions fails a test before it fails a learner.

- The 100-exercise solution authoring (Phase 4) is unverified until written;
  the `probe` check mode is designed against B5-2/B5-3/C8-1..4 exercise text
  but not yet tested against DuckDB's actual macro/table creation semantics in
  an in-memory `fresh=True` catalog (e.g. whether a `CREATE TABLE MACRO` behaves
  identically under `:memory:` attach vs the on-disk `sandbox.duckdb` used
  interactively). Flag for Phase 3/4 boundary if it doesn't.
- `USING SAMPLE` (C2-3) and `random()`-based bootstrap (C2-4) exercises are
  `manual` by design (nondeterministic); C2-5 compares against C2-4's own
  bootstrap output, so C2-5's solution file must generate its own bootstrap
  inline rather than reading C2-4's, per the standalone-grading decision.

## Out of scope

- Any web UI or notebook front end; the CLI and static HTML slides are the
  whole program.
- Grading prose answers, randomised outputs (`USING SAMPLE`, bootstrap),
  `EXPLAIN` output, and `SHOW DATABASES`; these are `manual`.
- Exercises for Part D (the course has none).
- MotherDuck-specific verification beyond passing `--md` through to the sandbox
  connection.
- Vendoring reveal.js for offline use.
- Hints beyond the course's one-liners, spaced repetition, or LLM-generated
  feedback.
- Fixing anything in the course other than the two audit defects (B5
  qualification, C5 `width_bucket`).
- A "run everything before this exercise first" mode — standalone grading
  makes this unnecessary by design.

---

## Detailed phase plans

See the phase-by-phase file lists, interfaces, checkbox steps, and check gates
in the original plan document: [`docs/sql-course-program-plan-2026-09-16.md`](../../docs/sql-course-program-plan-2026-09-16.md).
The corrections above (grading modes, isolation, check-gate wording, grader
rounding, parser mapping, title slide source, `why_betting`, Part D boundary,
`Block` fields) supersede the corresponding text in that document; everything
else there — file lists, interfaces, checkbox steps, commit messages, time
estimates — stands as written.

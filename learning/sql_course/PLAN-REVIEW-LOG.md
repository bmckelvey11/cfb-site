# Plan Review Log: SQL Course Program

Phases 0-1 (recon + interrogation) complete — plan locked with the user. MAX_ROUNDS=5.

Recon: read `docs/sql-course-program-plan-2026-09-16.md`, `scripts/sql_sandbox.py`,
`scripts/sql_course_schema_audit.py`, the course markdown (1,328 lines), `CONTEXT.md`,
3 ADRs, `pytest.ini`, test import conventions, codex version/config, skill inventory
on both benches. Advisor call surfaced two load-bearing gaps (grading mode for
object-creating exercises; learner/reference isolation) plus five disproved/unverified
plan claims, all verified against source before the interrogation.

Assumptions ledger confirmed by user (research=none) 2026-09-16.

Q1 (grading mode for `CREATE`-only exercises) locked: third check mode `probe`.
Q2 (learner/reference isolation) locked: standalone, `connect(fresh=True)` per run.
Cosmetic batch presented, no vetoes — all defaults accepted.

`PLAN.md` written to `learning/sql_course/PLAN.md`.

## Round 1 — Codex

Reviewer: codex-cli 0.151.0 (config default, `gpt-6-astra`). Round 1's first
attempt failed with a hard model error (`gpt-6-astra requires a newer version
of Codex`); user chose to upgrade the CLI. Upgraded via `npm i -g
@openai/codex@latest`, 0.151.0 → 0.154.0. Re-ran round 1 clean.
Thread: `01a0ad2b-93d1-73a3-97d6-2dc88499cb61`.

Codex ran DuckDB verification queries directly (read-only sandbox) and returned
12 findings, all reproduced with evidence, `VERDICT: REVISE`:

1. P1 — `grade`'s row comparison sampled only the first 20 rows; a wrong 21st+
   row passed. Reproduced.
2. P1 — column-name-set comparison + positional row-tuple comparison
   false-passes a column swap and false-fails a correct reorder. Reproduced.
3. P1 — Phase 5 progress writes through the `fresh=True` grading connection
   the locked Q2 isolation decision mandates, so progress never persists.
   Direct contradiction between two parts of the locked plan. Reproduced.
4. P1 — "read-only" attachment is not a process-level security boundary;
   learner SQL can still read arbitrary files, and B5-4 explicitly teaches
   filesystem writes.
5. P1 — the plan's example probe (`SELECT * FROM
   sandbox.main.american_to_prob(-150)`) calls a scalar macro as a table
   function; DuckDB rejects it.
6. P1 — a data-only probe can't distinguish `INTEGER` vs `VARCHAR` columns on
   an empty table (C8-2/C8-3), since both return the same empty result.
7. P1 — three exercise hints reference broken DuckDB behavior beyond the two
   audit-found defects: A2-5's `x <> x` (DuckDB treats NaN=NaN as true, so
   `<>` never fires), B2-4's `list_distinct(provider_key)` (needs a list, not
   a scalar), C3-1's `erf` (does not exist in DuckDB 1.5.5). All reproduced
   directly against this warehouse's DuckDB build.
8. P1 — some exercises (B4-1, B2-5, A2-1) don't fully specify the correct
   answer, so `exact` grading can fail a different-but-valid learner choice.
9. P1 — standalone/fresh grading (Q2) means a solution can't read an object
   from an earlier exercise in the *same* module either; C7-2's own text says
   "from `backtest_result`" (C7-1's output), which won't exist in a fresh
   connection.
10. P1 — C8-1's hint (`UNION BY NAME` + literal provenance) can't produce a
    `'both'`-tagged row for a game present in both sources; doesn't satisfy
    ADR-0001's merged-table contract.
11. P2 — `Module` interface has no field for the syllabus-row title-slide
    design or Part D's own titled sections; the deck-count test can pass with
    an empty Part D deck.
12. P2 — no timeout/resource bound on learner or reference query execution.

### Claude's arbitration

Accepted 1, 2, 3, 5, 6, 7, 8, 9, 10, 11, 12 — folded into `PLAN.md`'s "Key
decisions & tradeoffs": row/column comparison fixed to compare by name and in
full; a second short-lived persistent connection records progress after the
fresh grading connection closes; probe syntax matches scalar-vs-table-macro
kind; probe gains a `DESCRIBE`-comparison mode for DDL-only exercises; hints
are demoted from "the spec" to "a nudge" for Phase 4 authoring, with a
documented list of where DuckDB reality diverges from the hint text (does not
reopen the two-audit-fix scope boundary — the course markdown itself is
unchanged); ambiguous exercises get a documented deterministic tiebreak rather
than a blanket `manual`; the "reuses a prior module" rule is generalized to
"reuses any earlier exercise, same module or not"; `Module` gains
`part_focus`/`part_dialect`/`reference_sections` fields and the D-deck test
now checks content, not just file existence; grading execution gets a 10s
wall-clock timeout.

Accepted-but-scoped-down 4: documented as a known non-goal (single-user tool,
same trust level as running a script the user wrote) rather than building
filesystem sandboxing or an output-directory jail — the counter-argument
(disproportionate to the actual threat model) is legitimate and stated in
`PLAN.md`.

No findings rejected outright.

## Round 2 — Codex

Same thread (`01a0ad2b-93d1-73a3-97d6-2dc88499cb61`), resumed with
`sandbox_mode="read-only"` forced. Confirmed round 1's #1, #3, #5's syntax,
and #9 as addressed, and accepted #4's scoped-down resolution. `VERDICT:
REVISE` — 2 of my round-1 fixes were themselves wrong, plus 4 more findings:

1. P1 — my round-1 fix for row/column comparison still wrapped queries in
   `SELECT * FROM (<sql>) ORDER BY ALL` before aligning columns by name; that
   wrapper sorts by original column position (so a column-order difference
   can still misalign rows before comparison) and silently renames a genuine
   duplicate label (`a`, `a` → `a`, `a_1`), which defeats the duplicate-label
   check I'd added, since it now runs after the rename. Both reproduced.
2. P1 — my round-1 answer to findings 7/10 (leave course hints as-is, note
   the divergence in the solution file only) leaves the learner following the
   course's own printed instructions straight into a DuckDB runtime error,
   with the fix visible only in a file they have no reason to open first.
3. P1 — grading requirements (tiebreak, required aliases) documented only in
   the solution file header are invisible to the learner before they attempt
   the exercise and get an unexplained FAIL.
4. P2 — a single-input probe passes a macro that ignores its argument or is
   only correct for one sign of input; plain `DESCRIBE` catches column type
   but not a missing uniqueness/key constraint the exercise cares about.
5. P2 — the 10s "timeout" from round 1 only stopped the Python caller from
   waiting; it didn't call DuckDB's actual query-cancellation API, and nothing
   bounded memory before either the timeout or a `fetchall()` could exhaust
   it.
6. P2 — my round-1 fix asserted the Part D deck renders 12 reference
   sections; direct recount of the `## ` headings from "Layout and
   formatting" through "Anti-patterns" gives 10, not 12 — an uncounted guess
   on my part.

### Claude's arbitration

Verified all 6 directly (duplicate-label wrapping behavior, column-order
misalignment, and the Part D heading count, each reproduced/recounted in
DuckDB 1.5.5 / the course markdown) and accepted all 6 — no rejections.
`PLAN.md` updated:

- Row/column comparison redesigned to align by name **before** sorting
  (Python-level canonical-tuple sort replaces the SQL-level `ORDER BY ALL`
  wrapper entirely), and duplicate-label detection now reads the raw,
  unwrapped `cursor.description` before any DuckDB auto-rename can happen.
- Timeout redesigned around `con.interrupt()` (real cancellation, callable
  cross-thread) plus a `memory_limit`/`max_temp_directory_size` cap applied
  only to grading connections, not the interactive `sql_sandbox.py` REPL.
- Reversed the round-1 call on course-hint fixes: A2-5, B2-4, and C3-1 now
  join B5/C5 as in-repo markdown fixes (same Phase 1 mechanism, same
  precedent), rather than leaving broken hints in place with only a
  solution-file comment. C8-1 stays a Phase-4-authoring decision (a modelling
  gap, not a broken-function fix) but its hint gains one clarifying clause.
- Solution-file format gains an optional `-- note:` line, surfaced by
  `course.py show`, so a tiebreak or required-alias requirement is visible to
  the learner before grading, not only in the answer key.
- Probe format extended to multiple `-- probe:` lines (representative inputs,
  all must pass) and, for DDL exercises with a stated key/uniqueness
  requirement, a `duckdb_constraints()` probe alongside `DESCRIBE`.
- Part D reference-section count corrected from 12 to 10, with the section
  list spelled out in `PLAN.md` so the number is traceable, not asserted bare.

## Round 3 — Codex

Same thread. Confirmed round 2's visible-grading-requirements fix, broader
probes, and the corrected Part D count as addressed. `VERDICT: REVISE` — two
more bugs in my round-2 fix, plus a memory gap and an incomplete course-fix
scope:

1. P1 — the new comparison sorts raw Python tuples; a result containing
   `NULL` alongside a non-`NULL` value in the same column raises
   `TypeError: '<' not supported between NoneType and int`. Nullable columns
   and LEFT JOINs make this routine, not an edge case.
2. P1 — rounding still happened *after* the sort (my round-2 description:
   "sort... then compare... rounding..."), which can misalign rows: two
   result sets that are identical once rounded can sort differently at full
   precision, pairing rows incorrectly and producing a false FAIL.
3. P1 — `memory_limit` bounds DuckDB's own engine memory, not the Python
   list `fetchall()` builds, nor the cost of Python-side sorting afterward;
   `con.interrupt()` can't touch either. 100,000 rows measurably allocated
   Python memory even with a DuckDB-side `memory_limit` low enough that it
   should have blocked the query first.
4. P2 — my round-2 course-fix list caught A2-5's own hint but missed that
   Part D repeats the identical false `x <> x` claim twice more, independent
   of A2-5, which would reach the generated Part D deck unfixed.

### Claude's arbitration

Verified all 4 directly (`sorted()` on a tuple containing `None` reproduced
the `TypeError`; a concrete reference/learner pair reproduced the
sort-then-round misalignment and confirmed round-then-sort fixes it; grepped
Part D for the two additional `x <> x` occurrences) and accepted all 4 — no
rejections. `PLAN.md` updated:

- Canonicalization now rounds every numeric value **as part of building each
  row's aligned tuple**, before any sort, with the sort key itself defined to
  place `None`/`NaN` consistently instead of relying on Python's default `<`.
- Added a pre-fetch size gate: if the already-computed row count exceeds
  50,000, skip `fetchall()` entirely and report a distinct
  "result too large to grade" outcome, since neither DuckDB's memory limit
  nor `con.interrupt()` bounds Python-side fetch/sort cost.
- Course-fix list extended to six edits: Part D's "NULL and NaN discipline"
  and "Anti-patterns" sections both get the same `x <> x` → `isnan(x)`
  correction as A2-5, with one added clause on *why* (DuckDB's `NaN = NaN`
  is true, unlike IEEE 754), so all three read as one consistent fix.

## Round 4 — Codex

Same thread. Confirmed round 3's rounding-before-sort fix and the Part D
corrections as addressed. `VERDICT: REVISE` — 4 more findings, including two
places my own fixes introduced new bugs:

1. P1 — the round-3 `(is_missing, value)` key still crashes: when both sides
   of a comparison are flagged missing, Python still compares the second
   tuple element, so `None` vs. NaN as the leftover "value" raises
   `TypeError`. Separately, two independently-fetched NaN values compare
   unequal under bare Python `==` (`float('nan') == float('nan')` is
   `False`), so even same-shaped NaN results could still mismatch.
2. P1 — the round-3 fetch-size gate (50,000 rows) rejects legitimate course
   answers: B3-3's unnest legitimately returns 183,942 rows, A4-3's
   self-join 370,902, both verified against the local warehouse. No
   row-count threshold sits above every real exercise result and below a
   real problem.
3. P1 — a row-count cap doesn't bound cell size: 50 rows of a
   100,000-character string measurably allocated ~5MB in Python under a 1MB
   DuckDB-side limit that never tripped, so row count and Python memory cost
   aren't proportional to begin with.
4. P2 — the A2-5 course fix only touched the trailing *Hint:* clause; the
   exercise's own body still reads "a value where the number does not equal
   itself," the textbook IEEE-754 NaN definition, which still reads as
   support for retrying `x <> x`.

### Claude's arbitration

Verified all 4 directly: reproduced the same-canonicalization-for-sort-and-
equality design (`None`/NaN/numeric mixed rows sort and compare correctly
with no exception, no separate flag+value crash) and ran B3-3/A4-3 against
the local warehouse to confirm the row counts. Accepted all 4 — no
rejections. `PLAN.md` updated:

- Replaced the flag+value key with a single canonicalization function used
  identically for sorting *and* equality: `None → (0,0,"")`, NaN →
  `(0,1,"")` (a distinct rank from `None`, so they never collide with each
  other but each is internally consistent), everything else →
  `(1,0,rounded_value)`. One function, one pass, no crash, no
  sort/equality disagreement.
- Replaced the row-count gate entirely with a byte-budget gate on the fetch
  itself: `fetchmany(5000)` in batches, running a `sys.getsizeof`-based
  total against a 200MB budget (not a row count), re-checking the 10s
  wall-clock timeout between batches too. This bounds the actual failure
  mode (Python memory) instead of proxying through row count, so 400,000
  rows of small values pass while a genuinely oversized or pathological
  result is caught.
- A2-5's course-markdown fix now rewrites the full exercise line, not just
  the hint clause, so the body and hint agree.

## Round 5 — Codex (final round, MAX_ROUNDS=5)

Same thread. Confirmed round 4's scalar NULL/NaN fix, rounding fix, the
row-cap removal, and the full A2-5 correction as addressed. `VERDICT: REVISE`
— 2 more findings:

1. P1 — the canonicalization key from round 4 only handles scalars. B3 is a
   whole module about semi-structured data: `struct_pack` results (B3-4) and
   unnested list columns (B3-3) are ordinary expected exercise output, not
   an edge case. DuckDB returns a `STRUCT` as a Python `dict` and a `LIST`
   as a `list`; comparing two dicts with `<` raises `TypeError`, and a list
   containing `None` hits the original None-vs-value crash one level down.
   Both reproduced.
2. P1 — the round-4 byte-budget gate measures containers shallowly
   (`sys.getsizeof`), not their contents: a list of two 100,000-character
   strings measured 88 bytes against ~200,000 actual bytes, a roughly
   2000x undercount. Reproduced directly.

### Claude's arbitration

Verified both directly (dict/dict comparison raising `TypeError`, nested-None
list crashing, and the 88-byte-vs-200KB size gap). Accepted both — no
rejections; both are correct generalizations of fixes already in `PLAN.md`
(the same key function recursing into `list`/`dict`, the same recursion shape
reused for size estimation instead of canonicalization), not new open
questions. `PLAN.md` updated accordingly.

## Resolution: MAX_ROUNDS reached without APPROVED

Per the skill's hard rule, the review loop terminates at `MAX_ROUNDS=5`
regardless of verdict — this is not being disguised as convergence. Five
rounds ran, every round returned concrete, reproduced findings, and every
finding across all five rounds was accepted (0 rejected) after direct
verification against DuckDB 1.5.5 and, where relevant, the local warehouse.
No point in this review reached a genuine Claude/Codex disagreement requiring
a tiebreak — each finding was either a real gap in the original interrogated
plan or a real bug in my own prior fix, and each was folded into `PLAN.md`
before the next round. The five rounds did surface a real pattern: rounds 3
through 5 each found a bug in the *previous* round's fix to the grading
comparator (NULL/NaN handling, rounding order, size bounding), suggesting
`grade`'s comparator is the highest-risk piece of this plan and deserves
above-average test coverage in Phase 3 beyond what the plan already specifies
— recommend the Phase 3 test suite include NULL, NaN, `STRUCT`, and `LIST`
cases explicitly (not just the three scalar cases in the original plan),
since that is exactly the progression the five review rounds walked.

No unresolved disagreement to hand to the user. What's open: whether a sixth,
manual Codex pass is worth running given diminishing findings (round 5's two
issues were narrower than round 1-4's), or whether to proceed to
implementation with the current `PLAN.md` and let Phase 3's expanded test
suite (per the recommendation above) catch anything a sixth round might
still find.

# Models organization plan

**Date:** 2026-09-16
**Question:** How should the modelling code in this repo be organized, and what is the
safe sequence to get there?
**Scope:** `models/`, `research/`, and the root `scripts/` files those two import. Out of
scope: `cfb_system_maker/` (its own unit, own instructions), `cfbd-python/` (vendored),
`models/over_zero/site/` (nested git repo, see Hazards).

## Method

Read the tree under `models/` and `research/`; read the five unit `CLAUDE.md` files,
`CONTEXT.md`, and `PRODUCT.md`; then ran five checks that decide the ordering:

1. `git check-ignore` on `models/over_zero/data`, `.../site`, and the loose tarballs.
2. `grep -rn sys.path` across both trees — 40 hits, two distinct idioms (see Finding 2).
3. Sibling-import grep across `research/spread/scripts/*.py` — 31 edges.
4. `Get-ScheduledTask -TaskName 'CFB-*'` — what Windows actually has registered.
5. `python -m pytest --collect-only -q` — baseline **952 collected, 6 deselected**.

## Findings

### 1. The organizing axis is lifecycle, not subject

Subject separation is already fine: totals, over-zero, spread, Greenline. What is missing
is a consistent split between **live** code, **research** code, and **superseded** code.
Every unit gets this wrong in a different direction:

| Unit | Shape today | Problem |
| --- | --- | --- |
| `models/totals/` | package + `__main__` CLI, tests in root `tests/` | none — this is the reference shape |
| `research/spread/` | 20 scripts, 14 docs | **production lives under `research/`** (`weekly_slate.py` is "run the model") |
| `models/over_zero/` | 38 `.py` across 8 subtrees, incl. `research/b1..b7` | **research lives under `models/`**, and `v1/v2/v3` are live, not frozen |
| `research/totals/` | 9 scripts, 8 docs | two unrelated strands sharing one flat `scripts/` + `docs/` |

### 2. Two sys.path idioms, with opposite move costs

- **`research/spread/` is cheap to *relocate*, expensive to *split*.** Every script does
  `sys.path.insert(0, Path(__file__).parent)`. Move the directory whole and nothing inside
  it breaks — the inserts are self-relative. But that property holds only because the
  scripts sit together: the moment a split puts importer and imported in different
  directories, every crossing edge needs a second insert. Step 5 is a split, so it pays
  that cost; it is still the cheaper of the two units because the fix is additive (one
  extra insert) rather than a rewrite of an existing hardcoded path.
- **`models/over_zero/` is expensive to move.** 20 files hardcode the literal strings
  `v1` or `v2` in a path expression — `parent.parent / "v2"`,
  `REPO / "models" / "over_zero" / "v1"`, `parents[3]`. These are both name-sensitive and
  depth-sensitive. Renaming or re-nesting `v1`/`v2` breaks all of them, silently, at
  import time rather than at move time.

This inverts the naive priority. Do spread first; leave over_zero's version dirs alone.

### 3. The `eval_` prefix is a lie — four of them are production libraries

`weekly_slate.py` (the model that is actually run weekly) imports
`eval_prediction_tracker_models`, `eval_combination_sweep`, and `collect_line_timing`.
`predict_upcoming.py` imports the first two plus `build_prediction_tracker`. Per
`MEMORY.md`, `eval_version_b.py` is the script that decides. So the production closure is:

```
weekly_slate  predict_upcoming  collect_line_timing  pt_rollover
collector_health  build_prediction_tracker
eval_prediction_tracker_models  eval_combination_sweep  eval_version_b
```

Everything else under `research/spread/scripts/` is a genuine study:
`eval_accuracy_weighted`, `eval_ats_vs_breakeven`, `eval_by_spread_bucket`,
`eval_line_movement`, `eval_ridge_curve`, `eval_timing_decay`, `eval_line_shopping`,
`model_publish_times`, `check_pt_line_is_close`, `version_b_by_week`,
`migrate_book_set_version`.

**Any split done by filename prefix ships a broken weekly slate.** The split must follow
the import closure above.

### 4. `v1/` is production, not an archivable frozen copy

`models/over_zero/scripts/best_line_slate.py` — the live slate behind the
`CFB-OverZero-Slate` task — does `sys.path.insert(0, REPO / "models" / "over_zero" / "v1")`
and imports `censoring_bias` and `run_on_project_data` from it. `v3` imports from `v2`.
`monitor/`, `saturation_bias/`, and `floor_bias_1h/` all import from `v2`.

So none of `v1`, `v2`, `v3` can be archived. They are the model library under a
version-numbered name.

### 5. Three breakage surfaces per move, one of which is outside the repo

1. **Sibling imports** — 31 edges in spread, 20 sys.path hacks in over_zero.
2. **Tests** — `tests/` hardcodes unit paths, e.g.
   `parents[1] / "research" / "spread" / "scripts"` in `test_spread_accuracy_weighted.py`
   and `test_spread_collector_health.py`; `spec_from_file_location` in
   `test_prediction_tracker.py` and `test_collect_line_timing.py`;
   `models/over_zero/scripts/pick_history.py` in `test_over_zero_pick_history.py`.
3. **Windows Task Scheduler** — absolute paths baked into registered tasks, not in the
   repo at all:

   | Task | Pinned path |
   | --- | --- |
   | `CFB-AN-History`, `CFB-PT-Snapshot` | `research\spread\scripts\collect_line_timing.cmd` |
   | `CFB-OverZero-Slate` | `models\over_zero\scripts\over_zero_slate.cmd` |

   Both `.cmd` files also derive `REPO` as `%~dp0..\..\..` — three levels up from their own
   location — and then re-join the full path to their `.py`. Moving a `.cmd` breaks it
   twice over, and the failure surfaces in October as a silent gap in the collector, not
   at move time.

## Target shape

Mirror `models/totals/`. Three zones, one meaning each:

```
models/<subject>/       live: what runs weekly, importable, has a CLI entry point
research/<subject>/     studies: dated, one-off, cite-once; docs live beside them
archive/<subject>/      superseded: retained for audit, never cited as current
```

Root `tests/` stays the single flat suite — that is already the convention and works.
`archive/` already exists with exactly the "retain, never cite" rule in root `CLAUDE.md`.

**`models/` is a package; the new subdirectories are not.** `models/__init__.py` exists and
`models/totals/` has its own, which is why `python -m models.totals` works — the reference
shape is a reference because it is *importable*, not because of where it sits. Neither
`models/over_zero/` nor a new `models/spread/` has an `__init__.py`, and both use bare
sibling imports resolved through `sys.path`. Moving spread under `models/` therefore does
**not** make it `models.spread`; it produces a third directory that is neither package nor
path-independent.

This plan accepts that. `models/spread/` and `models/over_zero/` stay script-land with
sys.path inserts, and `models/` means "live code" rather than "importable package" —
`models.totals` is then the exception, not the rule. Converting either to a real package
is a separate job (see What this plan does not support). The alternative is to fold
packaging into Step 5, which roughly doubles it and couples a layout change to an import
rewrite; not recommended in the same commit.

Per subject:

| Subject | Live | Research | Notes |
| --- | --- | --- | --- |
| Totals model | `models/totals/` | — | already correct, no change |
| Over-zero | `models/over_zero/` (`v1`–`v3`, `monitor/`, `scripts/`, `saturation_bias/`, `floor_bias_1h/`) | `research/over_zero/` ← move `models/over_zero/research/` | version dirs stay put (Finding 2) |
| Spread | `models/spread/` ← the 9-file production closure | `research/spread/` keeps the 11 studies + `docs/` | biggest change, cheapest to do |
| Greenline grading | — | `research/totals/greenline/` | nested under totals, per the 2026-09-16 decision |

## Hazards — do not touch

- `models/over_zero/site/` — nested git repo, gitignored whole, pushes to a separate
  `sites` remote that needs the user's auth. A reorg breaks the deploy path. Leave it.
- `cfbd-python/` — vendored upstream.
- `.planning/` and `archive/` history — old paths there are correct as history.
- Pre-existing dead code — mention it, do not delete it (root `CLAUDE.md` §3).
- `models/over_zero/data/` — gitignored via the global `data/` rule; not a violation.

## Sequence

Cheap and reversible first; import-bearing last. Each step is its own commit, moves kept
separate from content edits (root `CLAUDE.md`).

**Step 0 — clear the tree.** ~24 modified files and a deleted `CODEX-HANDOFF.md` are
currently uncommitted. Land or stash them first; `git mv` on a dirty tree makes the diff
unreadable.
*Gate:* `git status` clean.

**Step 1 — hygiene, zero risk.** Add to `.gitignore`: `models/over_zero/*.tar.gz` (10
untracked redpanda bundles, 67 MB), `__pycache__/`, `graphify-out/` if not already.
Decide whether `models/over_zero/docs/backtest_bets.csv` is a documentation artifact
(keep) or working data (ignore) — it is currently tracked and not ignored.
*Gate:* `git status` shows no untracked noise; no tracked file removed.

**Step 2 — docs consolidation, zero code risk.** Move the 11 dated `.md` files in
`models/over_zero/docs/` that are finished studies into `research/over_zero/docs/`; leave
`MODEL_GUIDE.md` and `ROI_HITRATE.md` with the live unit. Same for the three chat-history
dumps — those are archive material, not docs.
*Gate:* no `.py` touched.

**Step 3 — `models/over_zero/research/` → `research/over_zero/`.** 9 dated study dirs.
They reach back into the unit via `REPO / "v1"` / `REPO / "v2"` where `REPO` is computed
from their own depth, so each moved file needs its path expression re-pointed at
`models/over_zero/`. Small, mechanical, 8 files.
*Gate:* run one script from each moved dir (`b4_features/probit_features.py`,
`2026-09-10_spread_magnitude/spread_magnitude.py`) and diff the output against the
`RESULTS.md` already committed beside it.

**Step 4 — nest Greenline: `research/totals/{scripts,docs}` → `research/totals/greenline/`.**
See Decision above for the target and the full list of surfaces. Order within the step:
`git mv` the 9 scripts and the 3 review docs plus `figs/`; bump `parents[3]` → `parents[4]`
in all 9; move `docs/README.md` up to `research/totals/README.md` and rewrite its two link
tables; fix `research/totals/CLAUDE.md`, root `docs/README.md`, the 9 usage docstrings, and
the emitted path in `greenline_bet_stats.py:158`.
*Gate:* `python research/totals/greenline/scripts/<name>.py --self-check` passes for all
nine — every one of them takes `--self-check`, which is why this step needs no new harness.
Then re-run `greenline_season_review.py --figs` and confirm the three PNGs land beside the
moved docs and the review's image links still resolve.

**Step 5 — split spread into `models/spread/` + `research/spread/`.** The big one.
Move the 9-file production closure from Finding 3 to `models/spread/`; the 11 studies stay.
Because both groups use `sys.path.insert(0, parent)`, the studies that import production
modules (`eval_line_movement` → `eval_prediction_tracker_models`, etc.) each need one
added path insert pointing at `models/spread/`. Update the two test files that hardcode
`research/spread/scripts` and the two that use `spec_from_file_location`.
Rename the `eval_`-prefixed production modules only if doing it in the same commit is
provably safe — otherwise leave the names and note the lie in the unit `CLAUDE.md`.
*Gate:* `python -m pytest` back to 952/6, plus a pinned-input slate diff.

The slate gate needs its inputs pinned or it proves nothing. `weekly_slate.py` takes
`--snapshot` for the Prediction Tracker side, but the odds columns are not pinnable: both
`_oddsapi()` and the Pinnacle reader glob their ingest directory and take `snaps[-1]`, the
newest file on disk. Three scheduled tasks write into those directories
(`CFB-Odds-Snapshot` every 6 h and Saturdays, `CFB-Odds-Snapshot-Saturday`,
`CFB-Pinnacle-Snapshot` daily at 06:15). So either:

- run both captures with `--snapshot <pinned file> --no-books`, which drops the book
  columns from the comparison but makes it deterministic; or
- run before and after back to back inside a window where no collector fires, and record
  the `oa_as_of` stamp on both to prove the same snapshot was read.

Without one of those, a diff cannot distinguish move-breakage from fresh odds.

**Step 6 — the two `.cmd` wrappers.** Only after Step 5 is green. For each: move the file,
fix its `%~dp0..\..\..` depth, fix the `.py` path it invokes, then
`Set-ScheduledTask` the registered action to the new absolute path, then fire one manual
run and read `$CFB_DATA_ROOT\logs\`.

Note that `CFB-OverZero-Slate` is registered **unquoted** — its action is a bare
`C:\...\over_zero_slate.cmd`, unlike the other five tasks, whose paths are quoted. Any new
path containing a space fails there and only there. Quote it while re-registering.

*Gate:* `Get-ScheduledTask -TaskName 'CFB-*'` shows the new paths and a manual run exits 0
with a fresh log entry. If any doubt, leave the `.cmd` files where they are — a thin
wrapper in the old location costs nothing and this is the failure mode that hides until
October.

**Step 7 — instructions.** Update the root `CLAUDE.md` Units table (it will gain
`models/spread/` and, per the open question, `research/greenline/`), write the two new
nested `CLAUDE.md` files, and point `AGENTS.md` at them.
*Gate:* every path named in every `CLAUDE.md` resolves.

## Verification gates

Run before Step 0 and after Step 7, plus the per-step gates above:

```bash
python -m pytest                                        # baseline: 952 collected, 6 deselected
python -m models.totals backtest --line ou_open --permute
python models/over_zero/v1/demo_reproduce.py            # guards the sibling-import numerics
for f in research/totals/greenline/scripts/*.py; do python "$f" --self-check; done
```

The `demo_reproduce.py` gate matters because `models/over_zero/CLAUDE.md` warns that the
historical copies use local sibling imports and that path changes must preserve numerical
behavior. A moved path that still imports can still change results.

`pytest.ini` deselects slow tests by default, so a silently-dropped test file is invisible
unless the collected count is compared.

## Decision: Greenline nests under totals

**Settled 2026-09-16: `research/totals/greenline/`, not a sibling unit.**

An earlier draft of this plan recommended promoting Greenline to its own top-level
`research/greenline/` unit, on the grounds that vendor evaluation is a different subject
from totals modeling. That recommendation is withdrawn. Greenline evaluation *is* totals
work — it grades a totals board — and `research/totals/` already exists as a real unit
with its own `CLAUDE.md` and a row in the root Units table. Splitting it out would create
a fourth research unit to hold nine scripts and trade one navigational problem for another.

Correcting the earlier draft: `research/totals/` is **not** missing from the Units table
and **does** have a `CLAUDE.md` — both were added by the 2026-09-16 docs pass. The stale
claim came from `docs/README.md`, whose "one status question this pass does not settle"
paragraph predates that promotion. That paragraph should be marked settled in Step 7.

The problem that remains is internal, and `research/totals/docs/README.md` already names
it exactly: two strands, "with nothing shared between them", sharing one flat `scripts/`
and one flat `docs/`. The fix is to give strand 1 its own subtree.

### Target

```
research/totals/
  CLAUDE.md               keep; re-point its script and doc paths
  README.md               moved up out of docs/ — it indexes the unit, not one strand
  greenline/              strand 1: vendor-pick evaluation
    scripts/              the 9 greenline_* / grade_ / match_ scripts
    docs/                 the 3 greenline-*.md reviews + figs/
  docs/                   strand 2 only: fbs-totals-*, research-prompts/fbs-totals/
```

### The one real hazard

Every Greenline script resolves the repo root by **depth**:

```python
sys.path.insert(0, str(Path(__file__).resolve().parents[3]))   # research/totals/scripts/x.py → repo root
```

Nesting one level deeper makes `parents[3]` resolve to `research/totals/` instead of the
repo root, and `from cfb_paths import INGEST` fails. **All 9 scripts need `parents[3]` →
`parents[4]`.** This is the same depth-sensitivity that makes over_zero expensive
(Finding 2); it is cheap here only because there are nine files and the edit is uniform.

The sibling imports (`from match_greenline_books import ...`,
`from greenline_season_review import ...`) use `sys.path.insert(0, parent)` and survive,
because all nine move together.

### Everything else that names these paths

| Surface | What breaks |
| --- | --- |
| `research/totals/docs/README.md` | relative links `../scripts/greenline_*.py` (10 of them) and `figs/` |
| `research/totals/CLAUDE.md` | the pipeline listing and `docs/greenline-season-review-2026-09-16.md` |
| root `docs/README.md` | lines 12, 145–147, 173, and the stale status paragraph at 177 |
| `greenline-totals-season-2026-09-16.md` | `figs/*.png` — survives if `figs/` moves with it |
| `greenline_season_review.py --figs` | writes into `figs/` beside `--out`; relative, survives |
| 9 script docstrings | usage lines read `python research/totals/scripts/...` |
| `greenline_bet_stats.py:158` | emits its own path **into generated markdown** — stale provenance in future review docs if missed |

No test references it (`tests/` has no `research/totals` path) and no scheduled task runs
it — the six `CFB-*` tasks do not include Greenline. So this step has neither of the two
nastiest breakage surfaces, which is why it sits early in the sequence.

## What this plan does not support

- It does not claim the reorganization improves any model's accuracy. It is a
  maintainability change; every gate above is a *no-change* gate.
- It does not convert `models/over_zero/` or `models/spread/` from script-land to a
  package. That is a larger job, gated on Finding 2, and is not required for the lifecycle
  split. The consequence is that `models/` after this plan means "live code", not
  "importable package" — `models.totals` remains the only true package under it.
- It does not resolve whether `v1`/`v2`/`v3` should be renamed to something meaningful.
  They cannot be renamed cheaply (20 hardcoded references) and renaming is not what the
  lifecycle problem needs.
- It has not been executed. No file has been moved. The counts above are from
  2026-09-16 and will drift as the working tree lands.

## Reproducing the findings

The five checks under Method are one-liners, not a script — they are inventory reads, not
analysis:

```bash
grep -rn "sys.path" models/ research/ --include=*.py | grep -v __pycache__
grep -rn "^import eval_\|^from eval_\|^import collect_line_timing" research/spread/scripts/*.py
grep -rn "spread/scripts\|over_zero" tests/*.py
python -m pytest --collect-only -q | tail -1
```

```powershell
Get-ScheduledTask -TaskName 'CFB-*' | ForEach-Object { $n=$_.TaskName; $_.Actions | ForEach-Object { "$n :: $($_.Execute) $($_.Arguments)" } }
```

If Step 5 is executed, the import-closure computation gets a real script at
`scripts/audit_import_closure.py` — it is the one piece here worth re-running.

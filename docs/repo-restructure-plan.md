# Repo restructure plan

**Status:** executed 2026-08-31. Final verification passed before checkout rename.
**Goal:** scope each unit so its context stops bleeding into the others, and get data out of git.
The finished local checkout is `C:\Users\mckel\dev\cfb` (renamed from `cfb-site`).

Two problems, one cause: every unit's instructions and docs load on every turn, and
`over_zero/data/` was committed because `.gitignore` only ignores root-anchored `/data/`.

## Execution recommendation

**Use Codex as the primary executor.** This job is mostly guarded filesystem work, git
renames, path rewrites, and repeated test runs against a dirty Windows checkout. Codex
should execute one step at a time, stop on any failed gate, and preserve unrelated local
changes.

Use Claude for one focused review after Step A. The context-scoping result depends on
Claude's own root and nested `CLAUDE.md` loading behavior, so Claude should confirm that a
fresh session sees the small root file and loads only the relevant unit instructions.
Claude should review that result, not independently rerun the data moves or code-tree
renames.

Recommended handoff:

1. Codex executes Step 0 and Step A, then records file sizes and changed instruction paths.
2. Claude opens a fresh session and verifies root versus nested `CLAUDE.md` scope.
3. Codex addresses any Step A finding, then executes B through E with each verification
   gate and commit boundary intact.

Success is measurable:

- Root `CLAUDE.md` 14,838 B → ≤3,000 B.
- `git ls-files | grep -E '\.(csv|json|jsonl)$'` drops from 990 files / 178 MB to fixtures only.
- `python -m pytest` green after every step.
- One data root (`CFB_DATA_ROOT`), one home per unit, one archive nobody cites.
- Local checkout opens and passes tests from `C:\Users\mckel\dev\cfb`.

## Units

| Unit | Tree | Test coverage |
|---|---|---|
| System maker (Flask + backtest + scrapers) | `cfb_system_maker/` | 36 test files |
| Totals model | `cfb_totals_model/` | 3 test files |
| Over zero (Arscott / floor-bias) | `over_zero/` | **none** |
| Spread research (prediction tracker) | scattered: `docs/prediction-tracker-*`, `scripts/eval_*` | none |
| Warehouse / data pipeline | `cfb_paths.py` + `CFB_DATA_ROOT` | `test_core_agreement.py` |

## Target layout

```
cfb/
├── CLAUDE.md                  ≤3K: shared plumbing + precedence + unit index
├── README.md                  human entry point
├── cfb_paths.py               shared, stays at root (all trees import it top-level)
├── pytest.ini, requirements*, launch.bat
├── cfb_system_maker/          + CLAUDE.md          (see C2 for the optional move)
├── models/
│   ├── totals/                ← cfb_totals_model/ + CLAUDE.md
│   └── over_zero/             ← over_zero/        + CLAUDE.md
├── research/
│   └── spread/                + CLAUDE.md
│       ├── docs/              ← docs/prediction-tracker-*, prereg-*, research-prompt-*
│       └── scripts/           ← scripts/eval_*, build_prediction_tracker.py, ...
├── docs/                      shared only: warehouse, design-system, data-coverage
├── scripts/                   shared tooling only: audit_*, promote_to_motherduck
├── tests/
└── archive/                   superseded. never cited. see rule below.
```

Data moved into the repo directory on 2026-08-31. It is still never committed -- the
`data/` rule in `.gitignore` matches at any depth:

```
C:\Users\mckel\dev\cfb\data\      (CFB_DATA_ROOT, 14 GB)
├── cfb.duckdb
├── raw/
│   ├── prediction_tracker/       ← prediction-tracker/raw/ncaa*.csv
│   └── (lines_2026_week*.json)   ← over_zero live-season pulls
└── processed/
    └── over_zero/                ← over_zero/data/processed/*
```

Data and code do not share a parent. Different size class, different backup needs, and
keeping data physically outside any git tree makes the `over_zero/data/` mistake
structurally impossible to repeat.

---

# Step 0 — pre-work

Blocking. Do not start A until these are clear.

1. **Commit or stash the 21 dirty entries.** 13 are inside packages that move in Step C.
   Renames must be pure-rename commits with zero content edits or git loses rename
   detection and blame.
2. **Resolve the worktree** at `.claude/worktrees/zen-albattani-a22e2f` (detached HEAD,
   holds a full mirror of the old layout). `git worktree list`, salvage or remove.
3. **Classify the root scratch files.** Untracked, so neither the archive policy nor the
   supersession rule reaches them; unclassified they survive the reorg and re-clutter
   root on day one.

   | File | Disposition |
   |---|---|
   | `_tmp_canvas_to_html.py`, `_tmp_count_an.py`, `_tmp_local_an.py`, `_tmp_local_backfill.py`, `_tmp_local_games.py` | scratch → delete, or move to `scripts/` if still used |
   | `scripts/_tmp_describe_stg.py` | same |
   | `app.txt`, `2026-08-28 10-22-03.txt`, `.flask-*.log` | scratch → delete (already gitignored) |
   | `consolidation.md`, `REMINDERS.md`, `SCHEMA_AUDIT.md` | classify: live doc, or archive |
   | `data_fields.csv` (48 K) | classify: reference doc, or archive |
   | `cfb-site.code-workspace` | keep, gitignored |

---

# Step A — docs and instruction files

No test surface. Fully reversible. This is the step that buys the stated goal.

## A1. Declare precedence, one owner per file

Today five instruction files total 26,668 B and all load every turn. Overlapping
authority is the bleed.

| File | Owner of | Target size |
|---|---|---|
| `CLAUDE.md` | shared plumbing, precedence, unit index | ≤3 K |
| `AGENTS.md` | pointer to `CLAUDE.md`, nothing else | ≤0.5 K |
| `.claude/CLAUDE.md` | GSD workflow overlay only | unchanged |
| `CONTEXT.md` | current work-in-flight | unchanged |
| `PRODUCT.md` | product intent, human-facing | unchanged |
| `README.md` | human entry point | unchanged |

State precedence explicitly at the top of root `CLAUDE.md`, and have each file say what
it does *not* own.

## A2. Shrink root `CLAUDE.md`

Root keeps only what is true regardless of which unit you touch:

- What the repo is (2–3 lines) and the unit index (table above).
- `CFB_DATA_ROOT` / `cfb_paths` resolution.
- Do not edit `cfbd-python/` (vendored upstream).
- No-lookahead principle (applies to every model).
- MotherDuck is a manual mirror; local file is source of truth.
- Instruction-file precedence.
- Archive rule (A4).

Everything else pushes into a nested `CLAUDE.md`:

| Section today | Goes to |
|---|---|
| Commands (CLI), pipeline/architecture, scraper conventions, `normalize._first`, frozen dataclasses, token resolution, running stats, coach style, sidecar `_meta`, design system | `cfb_system_maker/CLAUDE.md` |
| Totals-model harness, `ou_open` citation rules, leaked-era warning | `models/totals/CLAUDE.md` |
| Over-zero notes, run-from-that-cwd rule | `models/over_zero/CLAUDE.md` |
| Prediction-tracker / spread findings and pre-registrations | `research/spread/CLAUDE.md` |

Nested `CLAUDE.md` loads on top of root when Claude touches that subtree. Note the
mechanism only cuts *added* context — if root stays 14.8 K, files moved and nothing was
fixed. The ≤3 K target is the actual deliverable of this step.

## A3. Give research a home

`research/spread/` collects the ~25 prediction-tracker docs and their scripts. Its
`CLAUDE.md` carries the findings that currently sit in root: the panel cannot beat the
close (50.31% ATS vs 52.38% breakeven), the pre-registrations, and what is still open.

## A4. Archive by supersession

**Rule:** a doc is stale when a later doc answers the same question. Not recency —
`sports-insights-systems-combined-guide.md` is from July and still reference.

Archived docs move to `archive/<original-path>` and keep their git history.
`archive/README.md` states: *superseded, retained for audit trail, never cite as current.*
Root `CLAUDE.md` repeats the rule so agents do not quote from it.

First-pass classification — **confirm before moving**, this is the part where care matters:

| Doc | Superseded by | Call |
|---|---|---|
| `docs/PROJECT_MAP.md` | `.planning/PROJECT.md` | archive (root `CLAUDE.md` already band-aids this with a "stale" note — that is an archive move, not a note) |
| `docs/roadmap-v2-2026-08.md` | `.planning/ROADMAP.md` | archive |
| `docs/bet-history-analysis.md` | `bet-history-analysis-2023-2025.md` | archive |
| `docs/prediction-tracker-model-eval-plan.md` | `-addendum.md` + `-findings.md` | likely archive — confirm |
| `.planning/` (113 files) | historical phase records | leave in place, do not rewrite paths |
| `graphify-out/` (275 files) | gitignored, regenerable | leave, regenerate after C |

**Verify A:** root `CLAUDE.md` ≤ 3,000 B; each unit has a `CLAUDE.md`; `archive/README.md`
exists and the rule is stated in root.

---

# Step B — data

Runs before C. Untracking 990 files and renaming trees in one commit makes any breakage
unattributable. B also has its own verification that C's test suite cannot provide —
`over_zero` has zero tests and zero imports.

## B1. Fix `.gitignore` first

`/data/` is root-anchored. That is the bug: it caught repo-root `data/` and missed
`over_zero/data/`, and it will miss the next tree too. Change to unanchored `data/` with
explicit un-ignores for the committed fixtures:

```
data/
!tests/fixtures/
!cfb_system_maker/examples/
```

Do this before any file moves so the new layout cannot re-accumulate.

## B2. Classify by provenance, not size

| Class | Files | Action |
|---|---|---|
| Acquired, **verified** in warehouse | `over_zero/data/raw/1H-raw/` (139 MB), `actionnetwork_odds.csv` (26 MB) | `git rm --cached`, delete from disk |
| Acquired source, not derivable | `prediction-tracker/raw/ncaa*.csv` (25 files, 2001–2025) | move to `CFB_DATA_ROOT/raw/prediction_tracker/` |
| Acquired, live season | `over_zero/data/raw/lines_2026_week*.json` | move to `CFB_DATA_ROOT/raw/` |
| Derived, builder exists | `1h_lines.csv` (`combine_to_csv.py`), `1h_games.csv` (`build_1h_games_csv.py`) | move to `CFB_DATA_ROOT/processed/over_zero/` |
| Derived, **no builder found** | `games_with_1h.csv`, `games_2025.csv`, `half_lines_2025.csv` | move, copy-verify before removing — orphaned derived data behaves like source |
| Append-only record | `ledgers/totals_clv_ledger.jsonl` | stays tracked, it is a record not data |
| Test fixture | `tests/fixtures/`, `cfb_system_maker/examples/` | stays tracked, correct as-is |

### Containment evidence for the delete row

Verified against `C:\Users\mckel\data\cfb\cfb.duckdb` on 2026-08-31:

- 2025 scoreboard game ids, `over_zero` vs `raw.actionnetwork_scoreboard` payload:
  **910 = 910**, zero missing, zero extra.
- 910 `history_*.json` files vs `raw.actionnetwork_history`: **0 missing**.
- 38 ids absent from `stg.actionnetwork_history` are **2-byte `{}` files** — nothing to
  stage, nothing lost.
- `actionnetwork_odds.csv` vs `raw.actionnetwork_odds`: **200,560 = 200,560** rows,
  identical column list.
- Warehouse is a strict superset: 10,868 history payloads across 2015–2026 vs 910 for 2025.

Also note `1H-raw/scoreboard/` holds 15 byte-identical duplicates of files one level up,
and `lines_2026_week1.json` / `lines_2026_week1_20260826.json` is the same
duplicate-with-date-suffix pattern. Both die with the move.

### B2a. Rescue the builders before deleting `1H-raw/`

**B is not a pure move.** Two builders live *inside* the directory the delete row removes:

- `over_zero/data/raw/1H-raw/combine_to_csv.py` → writes `1h_lines.csv`
- `over_zero/data/raw/1H-raw/build_1h_games_csv.py` → writes `1h_games.csv`

Neither imports `cfb_paths`. Both compute paths as `__file__`-relative arithmetic
(`RAW_DIR.parent.parent / "processed" / ...`), so after the data move those paths point at
a directory that no longer exists — and would silently recreate in-repo `over_zero/data/`,
the exact failure mode B removes. `build_1h_games_csv.py` also reads `1H-raw/scoreboard/`,
the duplicate subdir that dies with the move.

Before deleting anything:

1. Move both builders to `models/over_zero/scripts/`.
2. Repoint them at `cfb_paths` (`RAW`, `PROCESSED`) instead of `__file__` arithmetic.
3. Point `build_1h_games_csv.py` at the warehouse (`raw.actionnetwork_scoreboard`) or at
   `CFB_DATA_ROOT/raw/`, not the dupe subdir.
4. Run both, confirm outputs match the current `processed/` CSVs byte-for-byte.

Only then run the `git rm --cached` + delete. These are content edits, so B is a small
series of commits, not one rename commit.

Corollary for C1: "`over_zero` → 0 import lines" is true of *imports*. The `__file__`-relative
path arithmetic is a second kind of coupling and it does not survive the data move — which
is why it is handled here in B rather than in C.

## B3. No history rewrite

`.git` is 28 MB — the blobs compressed well and have not bloated history. `git rm --cached`
stops the growth. Do **not** reach for `filter-repo`, especially with a live worktree.

## B4. Harden `cfb_paths.py`

`DATA_ROOT` falls back to `Path(__file__).parent / "data"` when `CFB_DATA_ROOT` is unset.
With everything externalized that fallback silently recreates in-repo `data/` — the exact
failure mode being removed. Make it fail loudly instead. `cfb_paths.py` stays at repo root;
all four trees import it as a top-level module, resolving via cwd on `sys.path`.

**Verify B:** `git ls-files` shows no `over_zero/data` or `prediction-tracker/raw`;
`python -m pytest` green; one `over_zero` script runs end-to-end and resolves its paths;
`python -m cfb_system_maker sample --data-dir <tmp>` still works.

---

# Step C — code trees

Pure-rename commits, zero content edits, `python -m pytest` as the gate.

## C1. Move models and research (cheap)

| Move | Import lines to rewrite |
|---|---|
| `cfb_totals_model/` → `models/totals/` | **4** (`scripts/compare_lines.py`, 3 test files) |
| `over_zero/` → `models/over_zero/` | **0** — all its `sys.path` inserts are `__file__`-relative and survive the move |
| `docs/prediction-tracker-*` + `scripts/eval_*` → `research/spread/` | 0 (no package) |

Also update: `pytest.ini` if testpaths change, `python -m` strings in `CLAUDE.md`,
`launch.bat`, and roughly 15 live docs that cite paths. Do not sed `.planning/` (113 files,
historical), `graphify-out/` (regenerable), or `.claude/` + `.solopreneur/` + `.remember/`
(agent state, not docs — leave alone).

### C1a. Splitting `scripts/`

`scripts/` is shared tooling *and* spread-research scripts in one directory. Nine files
import `cfb_paths` as a top-level module, which resolves only because repo root is on
`sys.path` — true when run from repo root, false once they sit two levels deep and get run
from their own directory.

| Stays in `scripts/` | Moves to `research/spread/scripts/` |
|---|---|
| `audit_coverage.py`, `audit_endpoints.py`, `promote_to_motherduck.py`, `analyze_coach_styles.py`, `build_coach_style_clusters.py` | `eval_combination_sweep.py`, `eval_prediction_tracker_models.py`, `eval_recency_screen.py`, `build_prediction_tracker.py`, `collect_line_timing.py`, `predict_upcoming.py`, `build_research_bundle.py`, `akm_winner_bound.py` |

Decide one rule and state it in root `CLAUDE.md`: **all scripts run from repo root**
(cheapest — the `cfb_paths` import keeps working unchanged), or each script bootstraps
`sys.path` itself. Do not leave it implicit.

`compare_lines.py` is the sharp case — the only file importing `cfb_totals_model`, and it
also exists in the fork being archived in D. Reconcile the two versions before moving it.

**Verify C1:** `python -m pytest` green; `python -m models.totals backtest --line ou_open`
runs; one `over_zero` script runs.

## C2. Move the system maker (optional — read the cost first)

`cfb_system_maker/` → `apps/system_maker/` costs **~57 files** of import rewrites (36 test
files plus scripts; the package has zero relative imports, so every internal reference is
absolute and must change).

That is 14× the cost of C1, for the one tree that is the repo's namesake and already has
its own directory. **Recommendation: skip C2.** The bleed being fixed is in `docs/` and the
instruction files, and A2 fixes that regardless of where the package sits. If you want the
symmetry anyway, run it as its own commit after C1 is green so a failure is attributable.

---

# Step D — external sprawl

Outside the repo, where nested `CLAUDE.md` scoping cannot reach.

| Path | Finding | Action |
|---|---|---|
| `C:\Users\mckel\dev\cfb-totals-model` | separate git repo, 3 commits, clean tree, last commit 2026-08-27. Its `cfb_totals_model/` package is superseded — **every file differs** from the in-repo copy, which is newer (2026-08-28) | **salvage its `README.md`, `TODO.md`, `docs/` first** (the in-repo package has none), then move the repo to `C:\Users\mckel\dev\_archive\` |
| `C:\Users\mckel\dev\cfb` | empty; this is the requested final checkout path | delete the empty directory so Step E can rename into it |
| `C:\Users\mckel\OneDrive\cfb_data`, `OneDrive - 150 Out\CFB` | API-key text files, not data | leave |

**Verify D:** no `cfb_totals_model` package outside `models/totals/`.

---

# Step E — rename the local checkout

Run last, after the nested worktree is resolved and every earlier step is green. This is a
filesystem rename, not a git content rename. The GitHub repository name remains `cfb-site`
unless that separate rename is requested later.

Before renaming:

1. Confirm `git status --short` is clean and `git worktree list` contains only the main
   checkout.
2. Confirm `C:\Users\mckel\dev\cfb` is absent after Step D.
3. Update live instructions and launch examples that depend on the checkout name, including
   root `README.md` (`cd cfb`) and any active absolute `C:\Users\mckel\dev\cfb-site`
   references. Do not rewrite historical `.planning/` records or archived documents merely
   to modernize their old paths.
4. Close terminals, editors, servers, and agents whose working directory is inside
   `cfb-site`.

From `C:\Users\mckel\dev`:

```powershell
Rename-Item -LiteralPath 'C:\Users\mckel\dev\cfb-site' -NewName 'cfb'
Set-Location -LiteralPath 'C:\Users\mckel\dev\cfb'
```

Reopen the project from its new path. Update local editor/workspace shortcuts if they still
point at `cfb-site`; those machine-local files do not belong in git.

**Verify E:** `git status --short` is clean; `git worktree list` reports
`C:\Users\mckel\dev\cfb`; `python -m pytest` is green; `CFB_DATA_ROOT` resolves to
`C:\Users\mckel\dev\cfb\data` (moved there 2026-08-31); no live code or current
instructions contain the old absolute checkout path.

---

# Order and rollback

```
0 pre-work  →  A docs  →  B data  →  C1 code  →  [C2 optional]  →  D external  →  E checkout rename
```

Each step is its own commit (or small series) and independently verifiable. A is reversible
by `git revert`. B is reversible only for tracked files — the deleted 165 MB is recoverable
from git history until the commit is old, and from the warehouse permanently. C is pure
renames, revert-safe. E is reversed by closing tools and renaming the directory back from
`cfb` to `cfb-site`; it does not alter git history.

Out of scope: `pyproject.toml` / packaging (the repo has never needed an install step;
adding one is a new failure mode, not a saving), `cfbd-python/`, and any change to the
warehouse schema or MotherDuck promote flow.

# Plan: Move the data root out of the repo tree

_Locked via claudex-loop — by Claude + mckel, 2026-09-21._
_Codex-reviewed: 4 rounds, APPROVED. Log: [review log](2026-09-21-data-root-move-review-log.md)._

## Goal

Move the 15 GB working-data directory from `C:\Users\mckel\dev\cfb\data` to
`C:\Users\mckel\data\cfb`, and first close the reason the move is dangerous: **31 unsafe resolvers (plus one existing guard receiving a marker upgrade) resolve the
data root without adequate protection**, so a wrong, stale, or unset
`CFB_DATA_ROOT` produces a wrong-location success rather than a failure.

The move itself is trivial — one volume, so a directory rename. The work is the sweep.

Primary motivation: `git clean -xdf` currently deletes the entire data root, warehouse
included. Confirmed, not inferred — `git clean -xdn` lists `data/cfb.duckdb`, `data/raw`,
`data/graphql`, `data/processed`, `data/ingest` alongside ordinary scratch.

This reverts `aa97625` (2026-08-31), which moved the data *from* `C:\Users\mckel\data\cfb`
*into* the repo. Background:
[`docs/data-location-2026-09-21.md`](../../data-location-2026-09-21.md) (commit `7d1fd23`).

## Approach

**Sweep first, cut over last.** Every code, test and doc change lands while the old root
is still valid and everything still works. The physical move is the final step, by which
point nothing is left that could silently resolve to the wrong place.

This reverses the ordering originally locked in Q2. Codex round 1 finding 6 was correct:
moving first leaves 23 live sites that a single manual script run could use to recreate
`<repo>\data` — the exact failure the change exists to prevent, occurring inside the
change. The cost of sweeping first is that the guard cannot be proved by a real
wrong-root until the cutover; verification checks 5-7 test it directly instead, with a
bogus root, which is stronger than waiting.

### Commit 1 — the sweep ✅ **DONE 2026-09-21, `d237275`**

Landed as committed. Scope grew from 31 to **35** during execution: the resolver scan
found four test skip-guards resolving `Path("")` and
`scripts/rebuild_pregame_features.py:23` (`default=Path("data")`), none of which four
rounds of review had enumerated. Verified: 1147 passed, 1 skipped, phase-1 scan clean,
all three guard negatives exit 3 creating nothing, `test_browser_smoke` runs for real.

Carved out of seven files that also held unrelated uncommitted work; the staged tree was
proved independently in a throwaway worktree before committing.

1. Add the **root marker and guard** (see Key decisions). Create `.cfb-data-root` in the
   current root first, so nothing breaks mid-commit.
2. Convert the **9 Python fallback/no-env sites** onto the established `cfb_paths` shim.
3. Convert the **13 Python direct-env-reader files** (14 sites) onto the same shim.
4. Add the **three-condition guard to 9 `.cmd` wrappers** — unset, marker-missing,
   marker-is-a-directory.
5. Convert the **2 test files** off repo-relative `Path("data")`.
6. Fix the **`README.md` command block** — 10+ commands prescribe `--data-dir data`.
7. Fix the **`cfb_system_maker/CLAUDE.md` command block** — **16** commands prescribe
   `--data-dir data` (added round 2).
8. Route **`CFB_DATA_DIR`** through the marker-validated resolver instead of letting it
   bypass `DATA_ROOT` (added round 2).
9. Make **`prune_motherduck_orphans.py` fail closed** — anchor tables present **and** an
   exact local↔remote `meta.warehouse_version` match before any orphan classification (see
   its section below; round 2, strengthened round 3).
10. Fix the **`README.md:108` `CFB_DATA_DIR` row**, which documents a default of `data`.
11. Point **`basic-betting.py` and `Untitled.ipynb`** at `cfb_paths.DB_PATH`.
12. **Refresh or quarantine the three `.claude/worktrees/*` checkouts**, which hold
    pre-sweep wrappers (added round 2).
13. Verify: full test suite, checks 1, 3, 5, 6, **13**, and the phase-1 forbidden-pattern
    scan (check 4). **Nothing has moved yet, so a regression here is cheap.**

### Commit 2 — the cutover

Steps 14-17 are a quiesce sequence; nothing may write to the root from 15 onward.

14. **Disable the eight `CFB-*` task triggers first**, persisting their prior enabled state
    **to a file outside the data root** (see Task-state recovery). Disabling before waiting
    is the order — the reverse leaves a window for a new task to start.
15. Wait for every running `CFB-*` task and its child processes to exit.
16. Stop the app and every kernel — Flask, marimo, Spyder, Jupyter, any `duckdb` CLI.
17. `CHECKPOINT`, then close cleanly. The `.wal` disappears and `cfb.duckdb` changes size.
18. **Capture the pre-move manifest now** — after the last write, immediately before the
    rename. Capturing it earlier (as the round-1 plan did) races the checkpoint, which
    rewrites the very files being measured.
19. **Preflight:** source exists, destination does **not** exist, destination's parent
    exists. `Move-Item` into an existing directory nests instead of replacing.
20. `Move-Item C:\Users\mckel\dev\cfb\data C:\Users\mckel\data\cfb`.
21. **Compare the post-move manifest — before anything runs.** This is the only window in
    which byte-for-byte equality is meaningful; a canary run mutates `logs/`.
22. Repoint the Windows User environment variable. Open a new shell.
23. Fix `.claude/launch.json` and the **four** location-stating living docs.
24. **Enable the canary task alone** — `CFB-PT-Snapshot`, **regardless of its prior state**,
    since a canary skipped because the task happened to be disabled proves nothing. Run
    check 7 in full. Only on success restore every task, canary included, to its recorded
    state.
25. Run the full verification table.

## Key decisions & tradeoffs

### The guard checks a marker file, not just existence

Codex round 1 finding 7: `is_dir()` passes on an **accidentally recreated** old root. An
empty-but-present root is the worst case — `prune_motherduck_orphans.py` decides what to
delete from MotherDuck based on what exists locally, so "nothing is local" reads as
"everything remote is an orphan."

A marker file solves that and the bootstrap objection with one mechanism:

```bat
if "%CFB_DATA_ROOT%"=="" (
  echo CFB_DATA_ROOT is not set; refusing to guess a data root. 1>&2
  exit /b 3
)
if not exist "%CFB_DATA_ROOT%\.cfb-data-root" (
  echo CFB_DATA_ROOT="%CFB_DATA_ROOT%" is not an initialized CFB data root. 1>&2
  exit /b 3
)
if exist "%CFB_DATA_ROOT%\.cfb-data-root\" (
  echo CFB_DATA_ROOT="%CFB_DATA_ROOT%" marker is a directory, not a file. 1>&2
  exit /b 3
)
```

The third condition is not redundant. `if exist` in batch matches directories, so the
Python-side `.is_file()` fix covers Python only — `task_ledger.cmd` and the other wrappers
would accept a *directory* named `.cfb-data-root` and write without ever reaching Python
validation (round 3 finding 3). The trailing backslash is the batch idiom for "is a
directory". A marker-directory negative test covers this.

```python
DATA_ROOT = Path(_configured_root).expanduser().resolve()
if not (DATA_ROOT / ".cfb-data-root").is_file():
    raise RuntimeError(
        f"CFB_DATA_ROOT={DATA_ROOT} is not an initialized CFB data root "
        f"(no .cfb-data-root marker). Create the directory and touch the marker."
    )
```

`.is_file()`, not `.exists()` — a *directory* named `.cfb-data-root` would satisfy
`.exists()` (round 2 finding 6).

Why this over a bare existence check: a recreated `<repo>\data` has no marker, so it fails
loud instead of silently accepting. Why this over deferring validation to entry points: 14
sites in `models/` bypass `cfb_paths` today and would bypass a deferred check too —
converting them to the shim is what puts them behind the guard, and the guard has to be at
import to catch them.

**The marker is a guard, not an identity proof.** It stops the realistic failure — an
empty directory that exists because something recreated it — and nothing more. It does not
survive someone deliberately copying the marker, and no file-content scheme would be worth
the machinery. The destructive operation is therefore guarded independently.

### `prune_motherduck_orphans.py` must fail closed on version identity

`prune_motherduck_orphans.py:84` is today a bare set difference —
`orphans = [row for row in remote if (row[0], row[1]) not in local]` — with no validation
that the local warehouse is the right one, or complete. Point it at an empty or
half-rebuilt root and every remote table classifies as an orphan.

"Expected schemas and tables are present" (the round-2 proposal) is not enough: a stale or
partly rebuilt warehouse passes it and still deletes everything else remote. The stronger
check uses machinery that already exists — `promote_to_motherduck.py:117` writes
`meta.warehouse_version` to the target and, per its own comment at line 66, stamps the
source too, so both sides carry a comparable version.

Required before any orphan classification:
1. Anchor tables present locally (`core.fact_game`, `core.fact_game_line`, `stg.an_scoreboard`).
2. **Exact local↔remote `meta.warehouse_version` match.** Mismatch aborts — it means the
   local file is not the warehouse the remote was promoted from.

Tested against three cases: empty warehouse, partial warehouse, version mismatch. Each
must refuse to drop anything.

**Bootstrap:** `cfb_paths.py:5-9` already raises at import when the variable is unset, and
`cli.py:10` imports it at module level, so a fresh clone already requires the variable
today. The marker narrows one real case: a variable pointing at an intended-but-uncreated
path, which `save_raw_json`'s `mkdir(parents=True)` currently bootstraps. That becomes one
documented step — create the directory, touch the marker — recorded in `README.md`.

### Delete fallbacks; do not repoint them

Repointing preserves the defect at a new address.
`research/spread/scripts/collect_line_timing.cmd:16-19` is the existing counter-example.

### All 31 unsafe resolvers

The `cfb_paths` contract is only real if callers go through it. The 14 direct readers in
`models/` fail loud on *unset* (bracket access raises `KeyError`) but receive no marker
check, so a stale-but-set root passes straight through them — which is precisely the Task
Scheduler failure mode in Risk 1.

### Two commits, sweep then cutover

Different concerns, and the repo's git rule says group by concern. Commit 2 is
**operationally reversible, not git-revertible** — the 15 GB rename and the environment
variable live outside version control, so `git revert` alone restores nothing. Reversing it
means: rename back, reset the variable, then revert the commit. Keep a scripted cutover
transcript so the reverse is mechanical rather than recalled (round 2 finding 11).

### Task-state recovery

Steps 14-24 leave the eight scheduled tasks disabled. Any failure in between — a failed
preflight, a manifest mismatch, an interrupted shell — leaves them disabled silently, and
the next morning's data simply never arrives.

Persist the prior enabled state to a file **outside the data root** (it is about to move)
and outside the repo working tree (a `git clean` is the thing being defended against) —
the scratch directory, or `%LOCALAPPDATA%`.

**Restore only from a coherent state.** "Restore on every failure path" is wrong after the
rename: a failure between steps 20 and 22 leaves the filesystem moved and the environment
variable still pointing at the old root, and re-enabling tasks there means eight jobs
firing against a disagreement. The marker stops them writing to the wrong place, but they
exit 3 and the data silently stops arriving (round 3 finding 4).

The rule is:

| Failure point | Action |
| --- | --- |
| Before step 20 (nothing moved) | restore tasks from the state file — the old root is intact and coherent |
| After step 20 | **either** complete the forward cutover (steps 22-23) **or** roll the filesystem back and reset the variable. Restore tasks only once one of those holds |
| Neither achievable | **leave every task disabled and fail loudly** — a visible outage beats eight jobs running against a split state |

## The 31 unsafe resolvers (+1 guard upgrade)

### `.cmd` repo-relative fallbacks (8) — all `set "CFB_DATA_ROOT=%REPO%\data"`

| file:line | invoked by |
| --- | --- |
| `scripts/refresh_cfbd.cmd:24` | `CFB-CFBD-Daily` |
| `scripts/pull_odds.cmd:20` | `CFB-Odds-Snapshot`, `CFB-Odds-Snapshot-Saturday` |
| `scripts/pull_oddspapi.cmd:19` | `CFB-Pinnacle-Snapshot` |
| `scripts/pull_massey.cmd:21` | `CFB-Massey-Weekly` |
| `models/over_zero/scripts/over_zero_slate.cmd:17` | `CFB-OverZero-Slate` |
| `scripts/tv_grid.cmd:16` | manual |
| `scripts/refresh_upcoming.cmd:11` | manual |
| `scripts/task_ledger.cmd:16` | manual |

Five carry `REM CFB_DATA_ROOT is inherited from the user environment` directly above a
fallback that contradicts it.

`research/spread/scripts/collect_line_timing.cmd:16-19` (`CFB-AN-History`,
`CFB-PT-Snapshot`) already refuses on unset — it needs only the new marker check. **9 `.cmd`
files touched.**

### Python `os.environ.get(..., <repo-relative>)` fallbacks (7)

`actionnetwork_flatten.py:44`, `massey_flatten.py:29`, `massey_ranks.py:33` — all
`Path(__file__).resolve().parent.parent / "data"`.

`mirror_duckdb_to_sqlite.py:12`, `build_coach_style_clusters.py:186`,
`promote_to_motherduck.py:39`, `prune_motherduck_orphans.py:43` — all bare `"data"`, so
**cwd-relative**. `prune_motherduck_orphans` is the dangerous one, per above.

### No environment variable consulted at all (2)

| file:line | current |
| --- | --- |
| `scripts/gen_db_summary.py:8` | `Path(__file__).resolve().parents[1] / "data" / "cfb.duckdb"` |
| `scripts/analyze_wind_totals.py:198` | `ap.add_argument("--data-dir", default="data", type=Path)` |

### Direct `os.environ["CFB_DATA_ROOT"]` readers — 14 sites, 13 files (added round 1)

All under `models/over_zero/`: `floor_bias_1h/floor_bias_1h.py:48`,
`research/b3_snapshots/drift_from_raw.py:29`, `research/b4_features/probit_features.py:20`,
`research/b5_team_sigma/team_sigma.py:17`,
`research/b6_high_total_under/test_high_total_under.py:34`,
`research/b7_mid_total_under/test_mid_total_under.py:55`,
`scripts/best_line_slate.py:58,64`, `scripts/build_weekly_results.py:55`,
`scripts/pick_history.py:25`, `scripts/verify_site_refresh.py:21`,
`v1/predict_week.py:22`, `v1/run_on_project_data.py:28`, `v2/models_v2.py:44`.

### Replacement pattern for all 22 Python files

Already used by **83 files** across `scripts/`, `research/` and `models/`:

```python
REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO))
from cfb_paths import DATA_ROOT  # noqa: E402
```

(Adjust `.parent` depth per file — `models/over_zero/v1/` needs three.)

### Also in scope

| file | change | commit |
| --- | --- | --- |
| `cfb_paths.py:11` | marker assertion | 1 |
| `tests/test_browser_smoke.py:16,19` | `"data/..."`, `create_app("data")` → `cfb_paths` | 1 |
| `tests/test_search_benchmark.py:39` | `DATA_DIR = Path("data")` → `cfb_paths.DATA_ROOT` | 1 |
| `README.md:20-73` | **10+ commands** prescribing `--data-dir data` | 1 |
| `cfb_system_maker/CLAUDE.md:25-` | **16 commands** prescribing `--data-dir data` (round 2) | 1 |
| `cfb_system_maker/cli.py:929` | route `CFB_DATA_DIR` through the marker-validated resolver | 1 |
| `scripts/prune_motherduck_orphans.py` | fail closed unless expected local schemas/tables exist | 1 |
| `.claude/worktrees/*` (3) | refresh or quarantine — they hold pre-sweep wrappers | 1 |
| `README.md:108` | `CFB_DATA_DIR` row documents default `data` | 1 |
| `basic-betting.py:16`, `Untitled.ipynb` | open repo-root `cfb.duckdb` → `cfb_paths.DB_PATH` | 1 |
| Windows **User** env var | → `C:\Users\mckel\data\cfb` | 2 |
| `.claude/launch.json` "Exports (static)" | absolute path; **file is already dirty** | 2 |
| `README.md:107` | documents root default as `<repo>/data` | 2 |
| `CLAUDE.md:38` | "Working data is `C:\Users\mckel\dev\cfb\data`" | 2 |
| `cfb_system_maker/docs/data-flow-guide.md:39` | "`CFB_DATA_ROOT` points at `data/`" | 2 |
| `cfb_system_maker/CLAUDE.md:88` | "Warehouse working copy" states `C:\Users\mckel\dev\cfb\data` (round 3) | 2 |

## Toolchain

None. The skill inventory scan matched nothing meaningful for a filesystem move plus a
mechanical sweep.

## Assumptions

Confirmed with the user, 2026-09-21. Items 15-18 added after Codex round 1.

1. Root `PLAN.md` is **occupied** — tracked, holds the 2026-09-08 loop, marked "do not
   execute from here." This plan lives in `docs/superpowers/plans/` beside 16 others. That
   directory has no `README.md` and `tests/test_docs_index.py:25` globs non-recursively, so
   no index row is required. — *source: `git ls-files`, `PLAN.md:1-5`*
2. Docs-aware mode on — `CONTEXT.md` and `docs/adr/` exist. This plan introduces no new
   domain terms, so no glossary edit and no ADR. — *source: files present*
3. Codex reviewer: `gpt-5.6-sol`, codex-cli 0.154.0, reasoning effort `high` for the loop
   (passed per-call, config left at `low`). — *source: `~/.codex/config.toml`*
4. The defect is unguarded root resolution. `cfb_paths.py:5-9` already raises on unset; the
   15 fallback sites defeat it and the 14 direct readers bypass it. — *source: verified at
   each file:line*
5. Same-volume rename — C:, 179 GB free, no reparse points. — *source: `Get-Volume`,
   `fsutil`, `du`*
6. Blast radius proven — `git clean -xdn` lists the warehouse and every data subtree.
   — *source: dry run*
7. Destination OneDrive-safe — KFM claims only Desktop, Documents, Pictures. Re-check if
   KFM changes. — *source: `HKCU:\...\User Shell Folders`*
8. All eight `CFB-*` tasks run as `mckel` / `Interactive`, call `.cmd` wrappers by absolute
   path inside the repo (not moving), set no data path and no `WorkingDirectory`. **Task
   definitions** need no edits; the **wrappers they call** do. — *source: `Get-ScheduledTask`*
9. DuckDB persists absolute paths in view definitions
   ([duckdb#2342](https://github.com/duckdb/duckdb/issues/2342),
   [#5868](https://github.com/duckdb/duckdb/issues/5868)). Live catalog: **1 user view, zero
   path-bearing**. `core.v_game` is table-only; `scrape_sbr_ncaaf_lines.py:375` uses
   `temp view`, session-scoped. Macros, secrets and attached catalogs still to be scanned at
   step 11 per round-1 finding. — *source: `duckdb_views()`*
10. Read-only access works while a writer holds the database. — *source: this session*
11. Clean close auto-checkpoints and removes the `.wal`; `FORCE CHECKPOINT` aborts running
    transactions and must not be used. — *source:
    [DuckDB CHECKPOINT docs](https://duckdb.org/docs/lts/sql/statements/checkpoint)*
12. No repo `conftest.py`, no symlinks or junctions, `env.env` holds no data-path
    references, `cfb_system_maker/` is fully `cfb_paths`-derived (`cli.py:44`,
    `web.py:473`). — *source: repo sweep*
13. `data/worktrees` (71 MB) is deploy tarballs with **zero references**; unrelated to the
    git worktrees at `.claude/worktrees/`. Moves with the rest. — *source: repo sweep*
14. **`CFB_DATA_DIR` is latent, not active — but it is still an unguarded bypass.**
    `cli.py:929` is `os.environ.get("CFB_DATA_DIR", DATA_DIR_DEFAULT)` and `cli.py:44` sets
    `DATA_DIR_DEFAULT = str(DATA_ROOT)` — `cfb_paths`-derived. The variable is unset at both
    scopes, so the web command resolves correctly today; Codex's round-1 "Critical" was
    overstated, because it requires someone to set the variable first. But round 2 was right
    that leaving a conditional resolver which skips the marker check contradicts the goal.
    **Resolution:** keep the override, route it through the marker-validated resolver
    (commit 1, step 8), and fix the wrong `README.md:108` documentation. — *source:
    `cli.py:44,929`, both env scopes checked*
15. **Bootstrap already requires the variable.** `cfb_paths.py` raises at import when unset
    and `cli.py:10` imports at module level, so a fresh clone cannot run today without it.
    The marker narrows one case — a variable pointing at an uncreated path, which
    `save_raw_json`'s `mkdir(parents=True)` currently bootstraps. — *source: `cli.py:10,82-87`,
    `enrich.py:53`*
16. **No CI.** `.github/workflows/` does not exist, so the marker assertion has no pipeline
    to break. — *source: directory absent*
17. **`--collect-only` does not prove a test runs.** Verified empirically: `pytest -m slow
    tests/test_search_benchmark.py --collect-only -q` collects all 3 tests and shows no
    skip, with the data present. — *source: this session*
18. **Three `.claude/worktrees/*` checkouts hold stale copies** of the `.cmd` wrappers and
    Python fallbacks. They are detached-HEAD worktrees, gitignored at `.gitignore:14`. —
    *source: `git worktree list`, repo sweep*

## Risks / open questions

1. **Task Scheduler may launch tasks with a stale `CFB_DATA_ROOT`.** Windows environment
   changes do not reach running processes or services, and the scheduler service started at
   boot ([MS Q&A](https://learn.microsoft.com/en-us/answers/questions/4042217/task-scheduler-and-environment-variables));
   whether it re-reads `HKCU\Environment` per launch was not settled. A stale value is
   *set*, just wrong — the **marker check is what catches it**, because the old root will
   not exist after the cutover. Verification must inspect which root a task actually wrote
   to, not that it exited 0. If stale: log off and back on, or reboot.
2. **`aa97625` never records why the data was moved into the repo.** An unrecorded
   constraint may resurface. Check 7 is most likely to expose one.
3. **The three active worktrees keep pre-sweep wrappers.** Launching anything from them
   without the environment set can recreate a worktree-local `data/`. Handled as commit-1
   step 12, not left as a warning — each is refreshed or quarantined, and scanned before
   cutover (round 2 finding 10).
4. **`launch.json` is dirty.** Reconcile before commit 2.
5. **Task-state loss on an aborted cutover.** The prior enabled state is persisted outside
   both the data root and the working tree. Restoration is **conditional on a coherent
   state**, not automatic on every failure — see the table in Task-state recovery. Before
   the rename, restore freely. After it, restore only once the cutover is complete or the
   filesystem and variable have been rolled back together; if neither holds, leave the tasks
   disabled and fail loudly. A silent "all tasks disabled" is how tomorrow's data quietly
   stops arriving, but eight jobs firing against a split state is worse.

## Verification

Checks 1-6 and 11 run after commit 1 (before anything moves). All run after commit 2.

| # | Check | Passes when |
| --- | --- | --- |
| 1 | `python -c "import cfb_paths; print(cfb_paths.DB_PATH)"` in a fresh process | prints the expected root for that commit |
| 2 | `python -m pytest` | passes |
| 3 | **Run** the two slow tests with a parsed report: `pytest -m slow tests/test_search_benchmark.py tests/test_browser_smoke.py -rs` | asserts an **expected executed count with zero skips**. Both a `--collect-only` run (assumption 17) and a plain exit 0 are false greens — `test_browser_smoke.py:5` is a module-level `importorskip` and the file also calls `pytest.skip` at runtime, so a fully-skipped run exits 0 |
| 4 | Forbidden-pattern scan, **phase-specific**. Phase 1: executable fallbacks only — `%REPO%\data`, `%~dp0..\data`, `os.environ.get("CFB_DATA_ROOT", ...)`, `Path("data")`, `--data-dir data`. Phase 2 adds the location literals — `dev\cfb\data` and its JSON-escaped form | zero **unapproved** hits against a phase-specific allowlist. A single all-phases scan cannot pass: after commit 1 the commit-2 files still hold the old path by design, `CFB_DATA_DIR` is retained deliberately, and `"data/` matches ~40 out-of-scope docstrings (round 2 finding 3) |
| 5 | Unset `CFB_DATA_ROOT` in a scratch shell, run `scripts/tv_grid.cmd` | exits 3, creates nothing |
| 6 | Point `CFB_DATA_ROOT` at an empty temp directory, run the same | exits 3 on the **marker** check, creates nothing — this is the recreated-old-root case |
| 7 | **Canary, fully specified.** Temporarily enable `CFB-PT-Snapshot` **regardless of its prior state**; record its prior `LastRunTime` and its log's size; `schtasks /run`; **wait for the task and its children to exit**; then compare | `LastRunTime` is **newer** than the recorded value, `LastTaskResult` is 0, and the log under `C:\Users\mckel\data\cfb\logs` grew. Then restore the task's original enabled state. Three traps this closes (round 3 finding 5): a conditional canary proves nothing if the task happened to be disabled; querying the result immediately reads the *previous* run's state; "log exists" is meaningless because the old logs moved with the tree |
| 8 | `Test-Path C:\Users\mckel\dev\cfb\data` after check 7 | `False` |
| 9 | **Full manifest**, captured at step 18 and compared at step 21 — **before any canary run**: every relative path and its size, including the 7 root-level loose files (`cfb.duckdb`, `cfb.duckdb.lock`, `sandbox.duckdb`, `cfblabs_coaches.csv`, `games_2024.parquet`, `ourlads_schemes.csv`, `cfb` — a 12,288-byte file, not a directory) and `.cfb-data-root` | exact equality. Ordering matters: check 7 mutates `logs/`, so comparing after it would contradict this check (round 2 finding 4). Per-file name+size is sufficient proof for a **same-volume rename**, which cannot alter contents — hashing 15 GB would defend a threat model that does not apply here |
| 10 | Warehouse identity in a **fresh process** against the new path: 343 tables (core 37, meta 3, raw 119, stg 184), `stg.an_scoreboard` 10,868, `stg.an_history` 162,297, `core.fact_game_line` 48,186 rows / 16 `provider_key`, `core.fact_game` 34,645 | exact match to the 2026-09-21 11:52 baseline |
| 11 | DuckDB catalog scan for the old absolute root across **views, macros, secrets and attached catalogs** | **Pre-move:** zero old-root references in *stored objects*. The main catalog's own path necessarily contains the old root before the cutover — the database file is still there — so a blanket "zero hits" cannot pass and would be a false failure. **Post-move:** zero hits anywhere |
| 12 | `git clean -xdn` | no `data/` entry |
| 13 | **Targeted guard tests** (new, commit 1). `CFB_DATA_DIR` set to a valid root, an invalid path, and a marker-less directory. `prune_motherduck_orphans` against an empty warehouse, a partial warehouse, and a version mismatch. A marker that is a *directory*, against a `.cmd` wrapper and against Python | the **valid** `CFB_DATA_DIR` case **succeeds**; every invalid, marker-less, partial, mismatched and directory-marker case rejects. A guard test that only proves rejection would pass a resolver that rejects everything. Generic `pytest` and the pattern scan prove none of this — a guard with no negative test is an assumption (round 3 finding 6) |

Checks 3, 5, 6, 7 and 9 are the load-bearing ones. 5 and 6 prove the guard fires without
needing a move; 7 is the only check that can catch an inherited-environment problem; 9 is
the only one that proves 15 GB actually arrived.

## Out of scope

- **Backups.** 15 GB, single volume, no backup script. Real gap, unchanged by this move,
  its own work.
- **Removing `CFB_DATA_DIR`** — documentation corrected, the override left in place per
  assumption 14.
- **Deleting `data/worktrees`** — moves with the rest; cleanup is a separate decision.
- **The archived hardcode** at `archive/spread-margin-era/scripts/diag_weight_concentration.py:46`.
  Archive rule says retain, don't rewrite.
- **Docstring and `--help` prose** mentioning `data/raw/...` (~40 hits). Inaccurate
  documentation; breaks nothing. Distinct from `README.md`'s executable command block,
  which is in scope.
- **A `launch.json` resolver wrapper** — rejected in round 1. `.claude/launch.json` is
  machine-specific by construction; a wrapper adds a moving part to the least consequential
  item in the change.
- **Re-litigating the destination.** `C:\Users\mckel\data\cfb` is settled.

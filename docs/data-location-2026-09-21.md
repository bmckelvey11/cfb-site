# Where `data/` should live — recommendation

**Question.** `CFB_DATA_ROOT` currently points at `C:\Users\mckel\dev\cfb\data`, inside
the git worktree. Should the 15 GB working-data directory stay there or move outside the
repo, and if it moves, where to?

**Recommendation: move it out, to `C:\Users\mckel\data\cfb`.** Same volume, so the move
is a directory rename (instant, not a 15 GB copy) and the rollback is the symmetric
rename. One authoritative env var changes; two `.cmd` fallbacks and one `launch.json`
path need hand edits.

**Method.** Inventoried the directory's size and contents, every reader and every setter
of `CFB_DATA_ROOT` in the tree, the machine's volumes and OneDrive roots, and the prior
art in `docs/`. Point-in-time: 2026-09-21, `master` at `d393cb7`.

---

## What is actually there

| Path | Size |
| --- | --- |
| `data/raw` | 6.5 GB |
| `data/cfb.duckdb` (+ 32 MB `.wal`, a `.lock`) | 5.0 GB |
| `data/graphql` | 2.6 GB |
| `data/processed` | 766 MB |
| `data/ingest` | 153 MB |
| `data/worktrees` | 71 MB |
| everything else (`exports`, `logs`, `audit`, `systems`, loose CSV/parquet) | < 3 MB |
| **total** | **15 GB** |

One volume on this machine: `C:` , 1.02 TB, 179 GB free. There is no second disk, so
placement is not a capacity decision — both candidates sit on the same SSD. The decision
is entirely about blast radius and tool boundaries.

## Why it should not stay inside the repo

1. **`git clean -xdf` deletes all of it.** `.gitignore:1-2` is an unanchored `data/`, so
   `-x` sweeps ignored files and takes the whole 15 GB, including the 5 GB warehouse.
   This is one keystroke from a routine "clear the untracked junk" impulse — and the
   tree is currently carrying ~35 dirty entries and a dozen untracked scratch files, the
   exact state that invites a `clean`. Nothing else in this analysis matters as much as
   this line.
2. **The repo's own restructure plan already said data belongs outside, and data used to
   live there.** `docs/repo-restructure-plan.md` (2026-08-31, executed) documents the
   layout as `C:\Users\mckel\data\cfb\` and gives the reason: "keeping data physically
   outside any git tree makes the `over_zero/data/` mistake structurally impossible to
   repeat." Later the same day, `aa97625` moved the 14 GB in the other direction —
   `C:\Users\mckel\data\cfb` → `C:\Users\mckel\dev\cfb\data` — and reworded the shared
   rule in `CLAUDE.md` from "outside every git tree" to the current in-repo wording. So
   this is not a new convention: it is a revert to the path the data occupied three
   weeks ago.
3. **Three git worktrees live under `.claude/worktrees/`, inside the repo.** Anything that
   walks the tree — a recursive grep that does not honour `.gitignore`, an IDE or
   notebook indexer, antivirus — walks 15 GB of JSON. `.spyproject/`, `__marimo__/`, and
   `.ipynb_checkpoints/` are all present in root, and none of those indexers read
   `.gitignore`.
4. **Data and code have different backup needs and different size classes.** They should
   not share a parent for the same reason they do not share a lifecycle.

Counter-argument, stated fairly: in-repo is one less path to remember, and a relative
`data/` fallback "just works" in a fresh clone. That convenience is real, and it is what
the reversing commit bought. It is not worth a one-keystroke path to losing the warehouse.

## Where, specifically

`C:\Users\mckel\data\cfb`

- Matches the path `repo-restructure-plan.md` documents and the one `aa97625` moved the
  data out of — no new convention to argue about, and the `<project>` level leaves room
  for the sibling `cfb-site` tree. The directory does **not** exist today; `aa97625`
  emptied it and the move recreates it. Do not expect to find siblings there.
- **Not** under either OneDrive root on this profile (`~\OneDrive`,
  `~\OneDrive - 150 Out`). A 5 GB DuckDB inside a synced folder thrashes upload and can
  be corrupted mid-write by the sync client. This is the one placement mistake worth
  naming explicitly.
- Same volume as the repo, so the move is `Move-Item` on a directory: a rename, not a
  copy.

## Everything that has to change

The code side is already clean: **no hardcoded data paths in live tracked Python.** Every
reader goes through `cfb_paths.py`, which requires `CFB_DATA_ROOT` and raises without it.
(One survivor, `archive/spread-margin-era/scripts/diag_weight_concentration.py:46`, still
hardcodes the *old* `C:/Users/mckel/data/cfb/processed` — it is archived dead code and
the move would coincidentally repair it.) That is what makes this cheap. The setters:

| # | Place | Current | Action |
| --- | --- | --- | --- |
| 1 | Windows **User** environment variable | `C:\Users\mckel\dev\cfb\data` | set to `C:\Users\mckel\data\cfb`; authoritative |
| 2 | `scripts/refresh_upcoming.cmd` | `if "%CFB_DATA_ROOT%"=="" set "CFB_DATA_ROOT=%REPO%\data"` | delete the fallback |
| 3 | `scripts/task_ledger.cmd` | `if "%CFB_DATA_ROOT%"=="" set "CFB_DATA_ROOT=%~dp0..\data"` | delete the fallback |
| 4 | `.claude/launch.json`, "Exports (static)" | `"--directory", "data/exports"` | absolute path to the new root; **currently dirty in the working tree — reconcile that first** |

Items 2 and 3 are the subtle hazard and the reason "just change the env var" is not the
whole job. After the move, if the environment variable is ever missing from a shell,
those two fallbacks silently point at a now-empty `<repo>\data`, and the code underneath
will happily **create** it rather than fail. The loud failure that `cfb_paths.py` gives
everything else is exactly what these two opt out of. Delete them; do not repoint them.
`research/spread/scripts/collect_line_timing.cmd:16` already does the right thing —
`echo CFB_DATA_ROOT is not set; refusing to guess a data root` and exit — so copy that
block into the other two rather than inventing a form.

Living docs that assert the old location and must change in the same commit as the move:

- `CLAUDE.md:38` — "Working data is `C:\Users\mckel\dev\cfb\data`"
- `cfb_system_maker/docs/data-flow-guide.md:39` — "`CFB_DATA_ROOT` points at `data/`"

## Procedure

Ordered because step 1 is a data-loss guard, not a formality.

1. **Close every DuckDB handle.** `data/cfb.duckdb.wal` (32 MB) and `data/cfb.duckdb.lock`
   both exist right now. Stop the Flask app, any marimo/Spyder/Jupyter kernel, and any
   open `duckdb` CLI. Confirm the lock is released, then checkpoint and close cleanly.
2. **Move the whole `data/` directory in one rename** so `.duckdb`, `.wal`, and `.lock`
   never separate. Moving the `.duckdb` alone, or moving it with a live WAL, loses data.
3. Set the User environment variable to the new root. Open a **new** shell — the old one
   keeps the stale value.
4. Apply edits 2–4 from the table, plus the two living-doc lines.
5. Verify: `python -c "import cfb_paths; print(cfb_paths.DB_PATH)"`, then `python -m pytest`.
6. Confirm `C:\Users\mckel\dev\cfb\data` does not reappear. If it does, a fallback survived.

Rollback is the symmetric rename plus resetting the variable.

## What this does not establish

- **Nothing here measures a performance difference.** Same volume, same filesystem; the
  argument is blast radius and tool boundaries, not speed. No I/O benchmark was run.
- **It does not claim the in-repo choice was a mistake at the time, and it did not recover
  why that choice was made.** `aa97625` is a careful commit — it verified the warehouse
  byte-identical afterwards and swept every stale path — but its message describes the
  move without stating a reason for it. If an unstated constraint drove it (a worktree
  problem, a path length limit, a drive that went away), that constraint is not recorded
  anywhere found here and could resurface during the move. This recommends reverting on a
  risk argument against an unknown rationale, not correcting a known error.
- **It does not audit scheduled tasks.** `scripts/task_ledger.cmd` and the `pull_*.cmd`
  wrappers inherit the variable from the user environment, so a Task Scheduler entry
  running as this user picks up the change. At least two tasks are in scope:
  `aa97625` names **CFB-AN-History** and **CFB-PT-Snapshot** as running
  `collect_line_timing.cmd`, and that wrapper now refuses to run without
  `CFB_DATA_ROOT` — so if either task carries its own environment block rather than
  inheriting, it fails loudly after the move. Enumerate them against
  `docs/autostart-audit-2026-09-15.md` before assuming inheritance.
- **There is no backup.** 15 GB, single volume, no backup script anywhere in `scripts/`.
  That gap is unchanged by this move and is a separate piece of work.

**Reproduce:** no script — this is an inventory, not a computation. The four setters were
found with `grep -rn CFB_DATA_ROOT` restricted to `--include=*.cmd --include=*.json` and
the User-scope value with
`[Environment]::GetEnvironmentVariable('CFB_DATA_ROOT','User')`.

# CFB Repo Consolidation Plan

Handoff doc for Claude Code. Written 2026-08-28 from a review of the actual folders.
Revised 2026-08-28 after agent council: drop pip `cfbd`, never delete source
repos, fix ledger + `clv.py` paths, do not edit `over_zero/v1/`, name pandas /
scikit-learn, Blake gate before merge.
Run Claude Code from `C:\Users\mckel\dev\cfb-site`; the sibling folders under
`C:\Users\mckel\dev\` must be reachable. Suggested kickoff: "Read CONSOLIDATION.md
and start Phase 1 at Step 0. Stop at the end of each step and report."

## Goal

One private repo for all college-football work. `cfb-site` becomes the hub;
`cfb-totals-model` and `over-zero` move into it. Relocating the data out of the
repo is Phase 2, done only after Phase 1 is green.

## Ground rules

- Work on a branch (`consolidate`, cut from `master`). Commit after every numbered
  step. Never force-push.
- Never delete the old repo folders (`cfb-totals-model`, `over-zero`, `paper_models`).
  They get renamed to `*.archive` at the end. Never `Remove-Item` a source repo.
- Do not edit anything under `over_zero/v1/` — it is a frozen reference implementation.
- Leave `cfbd-python/` alone in Phase 1. Do not delete it or `pip install cfbd`.
- Never commit `data/`, `env.env`, `.venv/`, or any `.duckdb` file.
- Move first, improve later. Do not refactor, reformat, or "clean up" code while
  relocating it — one change at a time, so a failure has one possible cause.
- Stop and ask Blake when: a requirements version conflicts, a deletion isn't
  clearly safe, a test fails for a reason you can't explain, or `git status` in a
  source repo shows uncommitted work.
- Environment: Windows 11, PowerShell, VS Code. Use forward slashes in git commands.
  Blake is a beginner programmer — plain-English commit messages and explanations.

## Current state (verified 2026-08-28)

### `cfb-site` — the hub

- GitHub `bmckelvey11/cfb-site`, branch `master`. Assumed private — confirm.
- `cfb_system_maker/` package: data layer (`cfbd_client.py`, `duckdb_load.py`,
  `scrapers.py`, `storage.py`), Flask app (`web.py`), models (`v1_model.py`,
  `models.py`), `clv.py`, `betlog.py`.
- `tests/` (~30 files), `docs/`, `scripts/`, `pytest.ini`, `requirements.txt`,
  `requirements.lock`, `launch.bat`, `CLAUDE.md`, `CONTEXT.md`, `TODO.md`.
- `data/` is gitignored: `cfb.duckdb`, `raw/`, `processed/`, `systems/`,
  `search_runs/`. `env.env` (gitignored) holds the CFBD API key.
- `cfbd-python/` is the vendored CFBD OpenAPI client (pydantic v1), loaded by
  path injection in `cfbd_client.py:_load_cfbd_module`. ~662 files are already
  tracked in cfb-site; a leftover nested `.git/` still sits inside the folder.
  `requirements.txt` line 1 is `-r cfbd-python/requirements.txt`. Leave it.
- `scripts/rename_videos.py` and `scripts/rename-by-regex.ps1` are video tools,
  not CFB. A copy of `rename_videos.py` also sits at `C:\Users\mckel\dev\`.

### `cfb-totals-model` — small, local-only git, no remote

- `cfb_totals_model/`: `cli.py`, `clv.py`, `data.py`, `inference.py`, `model.py`,
  `__init__.py`, `__main__.py`.
- `tests/`: `test_clv.py`, `test_inference.py`, `test_model.py`.
  `docs/`: `MODEL.md`, `EARLY-WEEKS-ANALYSIS.md`.
- `data/clv_ledger.jsonl` (bet ledger — must stay tracked), `compare_lines.py`,
  `README.md`, `TODO.md`, `requirements.txt`, `pytest.ini`.
- `data.py` already reads cfb-site's data through a relative path:
  `DEFAULT_DATA_ROOT = Path(__file__).resolve().parents[2] / "cfb-site" / "data"`.
- `clv.py` has a second path that must move with the ledger:
  `DEFAULT_LEDGER = Path(__file__).resolve().parents[1] / "data" / "clv_ledger.jsonl"`.

### `over-zero` — Arscott (2022) censoring-bias / Floor Bias research

- GitHub `bmckelvey11/over-zero`, branch `master`. Was public; Blake is switching
  it to private.
- Originally extracted *from* cfb-site (its first commit says so). Script-style,
  not a package: `v1/` (frozen), `v2/`, `v3/`, `monitor/`, `floor_bias_1h/`,
  `saturation_bias/`, `research/b1..b7`, `docs/`, `run_v1.bat`, `REVIEW.md`.
- Scripts find each other with
  `sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "v2"))` —
  relative to their own file, so the folder keeps working anywhere as long as it
  moves intact.
- `data/` IS tracked here (unlike cfb-site). It holds files that exist nowhere
  else — 1H lines, ActionNetwork odds 2018–2025, weekly 2026 line snapshots — plus
  copies of cfb-site's `games_*.json` / `lines_*.json` / `games.csv`. Loaders read
  this local `data/`.
- `requirements.txt`: numpy, scipy, statsmodels, matplotlib. `env.env` gitignored.

### `paper_models` — stale duplicate of over-zero

- Same remote, same history, behind origin. Redundant unless it holds uncommitted
  work. As of 2026-08-28 evening: behind 5 commits, untracked `.solopreneur/`.
  Do not delete. Archive at Step 4 after Blake confirms.

## Decisions already made

1. `cfb-site` is the repo. Do not create a new empty repo.
2. Everything is private. over-zero is archived on GitHub after the merge is
   verified — never deleted.
3. The totals model is dissolved into cfb-site's structure (plain copy; its git
   history stays behind in the archived folder).
4. over-zero comes in intact as `over_zero/` via `git subtree add`, history preserved.
5. Data stays exactly where it is during Phase 1.
6. Optional: rename `cfb-site` → `cfb-master` (matches `golf-master`). Blake
   decides. If yes: rename on GitHub too (it redirects the old URL) and
   `git remote set-url origin <new url>`.
7. Vendored `cfbd-python/` stays in Phase 1. Replacing it with pip `cfbd` is a
   later, separate branch — not part of this merge.

## Target layout

```
cfb-site/
├── cfb_system_maker/    # existing: data layer + web app + v1 model
├── cfb_totals_model/    # from cfb-totals-model
├── over_zero/           # from over-zero, intact: v1/ v2/ v3/ monitor/ research/ docs/ data/
├── ledgers/             # tracked bet ledgers (new)
├── tests/               # everything, one pytest run
├── docs/
├── scripts/
├── data/                # gitignored — unchanged in Phase 1
├── requirements.txt     # merged
└── README.md
```

## Phase 1 — Merge

### Step 0: Preconditions

1. In `cfb-site`, `cfb-totals-model`, and `over-zero`: `git status --short` must
   print nothing. If it prints anything, stop and list the files for Blake.
   Hub WIP must be committed or stashed **on `master`** before the next item —
   do not carry it onto `consolidate`. Totals-model untracked files
   (`.cursor/`, `data/`, `explore.py`, `graphify-out/` as of 2026-08-28) must
   be handled the same way.
2. In `over-zero`: `git fetch`; confirm local `master` is not behind `origin/master`.
3. In `paper_models`: `git status`. If dirty or behind origin, stop and ask.
   Do not delete this folder. After Blake confirms, rename it at Step 4:
   `Rename-Item ../paper_models ../paper_models.archive`.
4. Security check (over-zero was public): in `over-zero`, run
   `git log --all --oneline -- env.env`. If it prints anything, the CFBD key was
   pushed at some point — tell Blake to rotate it. Do not proceed silently.
   (Checked 2026-08-28: that filename was not in history. Still tell Blake if
   a later run prints anything.)
5. In `cfb-site`: `git checkout master`, then `git checkout -b consolidate`.
   Only do this after item 1 is clean.

### Step 1: Bring in the totals model

1. Copy `../cfb-totals-model/cfb_totals_model/` → `cfb_totals_model/` (skip `__pycache__`).
2. In `cfb_totals_model/data.py`: change `DEFAULT_DATA_ROOT` to
   `Path(__file__).resolve().parents[1] / "data"`. Update the module docstring, which
   still says "sibling repo". This is **not** the only code change — see item 7
   for the ledger path in `clv.py`.
3. Copy the three tests into `tests/` with a `test_totals_` prefix:
   `test_totals_clv.py`, `test_totals_inference.py`, `test_totals_model.py`.
   (`tests/test_clv.py` already exists — the prefix avoids the collision.) Compare
   the two `pytest.ini` files and merge anything totals needs into cfb-site's.
4. Docs: `docs/MODEL.md` → `docs/totals-model.md`,
   `docs/EARLY-WEEKS-ANALYSIS.md` → `docs/totals-early-weeks.md`. Fix relative links
   inside them. Fold the totals `README.md` into the top of `docs/totals-model.md`.
5. `compare_lines.py` → `scripts/compare_lines.py`. Check its imports and paths.
6. Append the totals `TODO.md` to cfb-site's `TODO.md` under `## Totals model`.
7. Ledger: `data/clv_ledger.jsonl` → `ledgers/totals_clv_ledger.jsonl`. cfb-site
   gitignores `data/`, so leaving it there would silently untrack it. In
   `cfb_totals_model/clv.py`, change `DEFAULT_LEDGER` to
   `Path(__file__).resolve().parents[1] / "ledgers" / "totals_clv_ledger.jsonl"`.
   Search `cfb_totals_model/` for `clv_ledger` and update every other reference
   in the same commit.
8. Merge `requirements.txt` (dedupe; ask on version conflicts). The hub file is
   missing totals' `pandas` and `scikit-learn` — add both explicitly. Totals'
   numpy is unpinned; hub has `numpy>=1.26,<3` — keep the hub pin unless Blake
   says otherwise. Add `out/` to `.gitignore`. `pip install -r requirements.txt`
   in cfb-site's `.venv`. If `requirements.lock` is a `pip freeze` output,
   regenerate it once at the end of Step 2, not mid-Step 1.
9. Verify: `python -m pytest` (bare `pytest` has no `pythonpath` here);
   `python -m cfb_totals_model --help`;
   `python -m cfb_totals_model backtest --line ou_open --min-prior-games 3`.
   Do **not** run `snapshot` or `clv` as the smoke test — those write the ledger.
10. Commit: "Import cfb-totals-model as cfb_totals_model package".

### Step 2: Bring in over-zero (subtree, history preserved)

1. Working tree must be clean (subtree refuses otherwise). Then:

   ```
   git subtree add --prefix=over_zero ../over-zero master
   ```

   No `--squash` — we want the full history.
2. Verify: `git log --oneline -5 -- over_zero` shows over-zero's commits. Then
   `cd over_zero; python monitor/score_game.py 28 40.5` (its data came with the
   subtree). Optionally `python v3/run_v3.py` for a full run.
3. `.gitignore`: change the line `data/` to `/data/`. Without the leading slash it
   matches a folder named `data` at any depth, so new files in `over_zero/data/`
   would silently go untracked. Already-tracked files are unaffected either way.
4. `env.env`: `over_zero/v1/predict_week.py` already checks `CFBD_API_KEY` /
   `CFBD-API` / `BEARER_TOKEN` before reading `over_zero/env.env`. Do **not**
   edit `v1/` to point at the hub `env.env`. Set the env var from the hub key
   (or a shell that already has it). Add one line to `over_zero/README.md`:
   token comes from `CFBD_API_KEY`, not a second `env.env` copy.
5. Merge over-zero's `requirements.txt` into cfb-site's (`statsmodels`, `scipy`,
   `matplotlib`). Install. Ask on conflicts.
6. Check `over_zero/run_v1.bat` and every `over_zero/**/README.md` for run
   commands: "run from the repo root" now means "run from `over_zero/`". Add one
   line at the top of `over_zero/README.md` — merged from the over-zero repo on
   2026-08-28, run commands from this folder — and an `## over_zero` section in
   cfb-site's `README.md` linking to it.
7. Tool-state folders (`.remember/`, `.superpowers/`) may come along. Leave them.
8. Verify: `python -m pytest` (over_zero has no pytest suite; cfb-site + totals
   must pass), plus the `score_game.py` smoke test again from `over_zero/`.
9. Commit: "over_zero: post-merge path and gitignore fixes".

### Step 3: Cleanups

1. Leave `cfbd-python/` untouched. Do not delete it, do not `pip install cfbd`,
   do not strip the nested `.git` in this merge. Nested-`.git` cleanup is a
   later one-line commit if Blake wants it.
2. Move `scripts/rename_videos.py` and `scripts/rename-by-regex.ps1` to
   `../vid_programs/`. Diff `scripts/rename_videos.py` against `../rename_videos.py`
   first; keep the newer one and tell Blake which.
3. Full verification: `python -m pytest`; start the Flask app (`launch.bat` or
   `python -m cfb_system_maker web`) and load one page;
   `python -m cfb_totals_model --help`;
   `cd over_zero; python monitor/score_game.py 28 40.5`.
4. Stop and report. Do not merge or push until Blake says so.
5. Commit: "Move non-CFB video scripts to vid_programs".

### Step 4: Finalize

Blake approves first. Then:

1. Merge `consolidate` into `master`, push (no force). Optional extra gate:
   push `consolidate`, clone it into a temp folder, install, run
   `python -m pytest` and the two smoke tests, then merge.
2. Rename `../cfb-totals-model` → `../cfb-totals-model.archive`,
   `../over-zero` → `../over-zero.archive`, and (after Blake confirms)
   `../paper_models` → `../paper_models.archive`. Do not delete.
3. Blake: archive `over-zero` on GitHub (Settings → Archive). Already private.
4. Optional rename to `cfb-master` (Decisions #6).

### Rollback

- Phase 1 lives on a branch. `git checkout master` abandons it;
  `git branch -D consolidate` removes it.
- The source folders are untouched until Step 4, so nothing is lost by starting
  over. `paper_models` is archived at Step 4, never deleted.
- To undo a subtree add after committing: `git revert -m 1 <merge-commit>`, or
  reset the branch.

## Phase 2 — Move data outside the repo

**Status (2026-08-28 evening): DONE.** Executed across two sessions (Cursor did
Step 1's path module + over_zero conversion + the physical move of `raw/`,
`processed/`, `graphql/`, `cfb.duckdb`; Claude Code finished the tail): repo
`data/` leftovers removed after verifying byte-identical/empty at the new root,
`web.py`'s `create_app` default + `launch.bat` + 4 scripts
(`analyze_coach_styles`, `audit_coverage`, `audit_endpoints`,
`build_coach_style_clusters`, `mirror_duckdb_to_sqlite`) converted off the bare
`"data"` default, `CFB_DATA_ROOT` set at User scope to
`C:\Users\mckel\data\cfb`. Verified: 605 tests pass, CLI backtest + totals-model
+ over_zero `score_game` smokes green, web app serves `/` with data found.
Remaining for Blake: add `C:\Users\mckel\data\` to the rclone backup set
(step 4 below); restart any Flask window started before the move (it holds the
old relative path). Terminals opened before the env var was set need a restart
to see it.

Separate session. Only after Phase 1 is merged and green.

Why: one canonical data location that other projects and rclone backups point at,
with no copying files between repos (the habit that produced over-zero's duplicate
`data/`). Note the data is already outside the repo as far as git is concerned —
this is a filesystem move plus a change to how code finds the folder.

Mechanism: one environment variable, one path module, fallback to `./data` so a
fresh clone still works with nothing set.

```python
# cfb_paths.py — repo root
import os
from pathlib import Path

DATA_ROOT = Path(os.environ.get("CFB_DATA_ROOT", Path(__file__).resolve().parent / "data"))
DB_PATH   = DATA_ROOT / "cfb.duckdb"
RAW       = DATA_ROOT / "raw"
PROCESSED = DATA_ROOT / "processed"
```

Set once, then restart the terminal and VS Code:

```powershell
[Environment]::SetEnvironmentVariable("CFB_DATA_ROOT", "C:\Users\mckel\data\cfb", "User")
```

Steps:

1. Add `cfb_paths.py`. Convert loaders one project at a time, running tests after
   each — do not move any files yet:
   - `cfb_system_maker`: search for `"data"`, `cfb.duckdb`, `Path(__file__)`.
     Likely spots: `duckdb_load.py`, `storage.py`, `scrapers.py`, `web.py`.
   - `cfb_totals_model/data.py`: `DEFAULT_DATA_ROOT` → `cfb_paths.DATA_ROOT`.
   - `over_zero`: its script folders don't import from the repo root, so have
     `v2/models_v2.py` (`load_from_raw`), v1's `RAW_DIR`, and `monitor/` read
     `CFB_DATA_ROOT` directly with the same fallback. Games/lines JSON come from the
     shared root; over_zero's unique snapshots stay in `over_zero/data/`.
2. Move `data/cfb.duckdb`, `data/raw/`, `data/processed/` →
   `C:\Users\mckel\data\cfb\`. Set the env var. Run everything again.
3. Once over_zero reads the shared root, `git rm` the duplicated `games_*.json` /
   `lines_*.json` / `games.csv` from `over_zero/data/`. Keep the 1H lines,
   ActionNetwork odds, and weekly snapshots — they are the only copy.
4. Blake: add `C:\Users\mckel\data\` to the rclone backup set.

The rule for what goes where: if the scraper can rebuild it, it lives outside the
repo; if losing its version history would hurt, it stays in git.

DuckDB caution: one writing process at a time. Anything that only reads should
open with `duckdb.connect(str(DB_PATH), read_only=True)`; only the scraper/loader
writes. If "share with others" ever means another machine or a MotherDuck dive,
that is a MotherDuck mirror (same pattern as Greenview), not a local folder.

## Out of scope — later

- Replace vendored `cfbd-python/` with pip `cfbd`, or strip its leftover nested
  `.git`. Fresh-clone install still depends on the tracked vendor tree plus
  `-r cfbd-python/requirements.txt`.
- Consolidate the two `clv.py` modules and two ledgers (`betlog.py` +
  `totals_clv_ledger.jsonl`) into one shared module.
- Rename the `cfb_system_maker` package (large import churn; not worth it now).
- Same data-root pattern for `golf-master` (`C:\Users\mckel\data\golf\`).

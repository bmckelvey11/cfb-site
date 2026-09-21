# Plan Review Log: Move the data root out of the repo tree

Plan: [`2026-09-21-data-root-move.md`](2026-09-21-data-root-move.md)

Phases 0-1 (recon + interrogation) complete — plan locked with the user. MAX_ROUNDS=5.

## Phase 0 — recon

Brownfield. Codebase explored directly plus one parallel sweep agent. Research gate set to
`web` by the user; four targeted searches run.

Findings that changed the plan:

- The setter inventory grew from **4 sites to 17**. The original analysis doc counted only
  the setters reachable from the env var; the sweep found 8 `.cmd` fallbacks (not 2),
  7 Python `os.environ.get(..., <repo-relative>)` fallbacks, and 2 sites consulting no
  environment variable at all. Every one verified at `file:line` by hand afterwards.
- **83 files already use the correct `cfb_paths` import shim.** The 9 Python offenders are
  stragglers off a dominant convention, not a missing one — which made the sweep cheap
  enough to fold into scope.
- DuckDB persists absolute paths in view definitions and such views break on a move
  (duckdb#2342, #5868). Checked the live catalog: 1 user view, zero path-bearing. A
  plausible plan-breaker, eliminated rather than assumed.
- Windows may launch scheduled tasks with a **stale** `CFB_DATA_ROOT`. Research did not
  settle whether Task Scheduler re-reads `HKCU\Environment` per launch. This is the one
  failure mode the fallback deletion does not cover, and it drove Q1's answer.

Assumptions ledger: 14 entries, all sourced. Confirmed by the user without correction.

## Phase 1 — interrogation

Load-bearing questions asked: 2. One demoted.

**Q1 — Should the guard assert the data root *exists*, or only that `CFB_DATA_ROOT` is
non-empty?**
→ **Assert existence.** The pattern being propagated (`collect_line_timing.cmd:16`) catches
only *unset*. Stale and typo'd values are populated-but-wrong, and the next line in each
wrapper `mkdir`s the bad path and reports success. Existence assertion converts every
silent-wrong-location failure into a loud one, and is the only thing that catches the
stale-scheduler risk.

**Q2 — Fix all 17 sites, or only what the move breaks?**
→ **All 17, in two commits.** Commit 1 is what the move requires to be safe; commit 2 is
the straggler sweep. Decisive factor: `prune_motherduck_orphans.py:43` falls back to a
cwd-relative `"data"` and decides what to *delete* from MotherDuck based on what it finds
locally — an empty root means "everything is an orphan."

**Q3 — Fix the two silently-skipping tests? → demoted to cosmetic.** `pytest.ini` sets
`addopts = -m "not slow"` and both tests are `slow`-gated, so neither runs in the default
suite today. Worst case is an opt-in benchmark that skips instead of running. Real, but no
default workflow breaks, so the "if we guess wrong" was too weak for a load-bearing slot.
Folded into commit 2.

Cosmetic batch (6 items) presented as recommendations; no vetoes. Notable: root `PLAN.md`
is tracked and occupied by the 2026-09-08 loop, so this plan and log were written to
`docs/superpowers/plans/` instead — matching 16 existing plans there.

## Phase 2 — Codex review

Reviewer: `gpt-5.6-sol`, codex-cli 0.154.0, `model_reasoning_effort` raised to `high` for
the round. Thread `01a0c4d7-c1f8-7321-b858-cc064ee78903`, read-only sandbox.

### Round 1 — Codex

`VERDICT: REVISE` — 16 findings, 7 marked Critical. Verbatim summary line: *"17-site list
is not complete enough. Move direction is sound; procedure is unsafe."*

Critical:
1. Cutover starts with live writes — plan waits for the rebuild before disabling future
   triggers, so another task can start in the gap and baseline counts can shift.
2. Tasks never get re-enabled — step 3 disables eight, no step restores them, and
   verification check 7 runs `schtasks /run` against a disabled task.
3. "17 sites" excludes direct environment readers that bypass `cfb_paths.py`.
4. `CFB_DATA_DIR` remains an active second root via `cli.py:929`.
5. Living instructions recreate repo data — `README.md` and nested `CLAUDE.md` prescribe
   `--data-dir data`; the plan's "two living docs" claim is false.
6. Move-before-sweep ordering creates the exact failure window the plan claims to close.
7. Existence is not identity — any directory passes the guard, including an accidentally
   recreated old root; with `prune_motherduck_orphans.py` that means valid remote tables
   classify as orphans.

Required: import-time assertion breaks fresh-clone/CI bootstrap; verification contains
false greens (`--collect-only` does not evaluate runtime `skipif`, the `grep` misses
`%REPO%\data` / `Path("data")` / `CFB_DATA_DIR`); warehouse counts do not prove the 15 GB
tree moved; `Move-Item` lacks preflight and the rollback is not git-revertible;
`launch.json` absolute path is a second source of truth; `basic-betting.py` and
`Untitled.ipynb` open the stray repo-root `cfb.duckdb`; the DuckDB audit checked views
only, not macros or secrets; the three `.claude/worktrees/*` copies retain stale wrappers.

### Claude's response — Round 1

Every factual claim was checked against the files before disposition.

**Accepted (13).** Findings 1, 2, 5, 6, 7 and all Required items except the `launch.json`
wrapper. Three were worse than Codex stated:

- **Finding 3 understated.** Codex named 7 direct readers; there are **14 sites across 13
  files**, all in `models/` — `best_line_slate.py:58,64`, `predict_week.py:22`,
  `models_v2.py:44`, `pick_history.py:25`, the `research/b3`–`b7` series, and others. They
  use *bracket* access (`os.environ["CFB_DATA_ROOT"]`), so they fail loud when the variable
  is unset — a different defect class from the 15 fallbacks. The real problem is that they
  bypass `cfb_paths` and therefore receive no existence assertion, so a stale-but-set root
  passes straight through. Site count corrected 17 → 31.
- **Finding 5 substantiated, line refs wrong.** `README.md:13` and
  `cfb_system_maker/CLAUDE.md:20` do not say what Codex claimed. But `README.md:20-73`
  carries **10+ commands** prescribing `--data-dir data`, and `README.md:107` documents the
  `CFB_DATA_ROOT` default as `<repo>/data`. The plan's "two living docs" claim was false.
- **False green confirmed empirically.** Ran `pytest -m slow
  tests/test_search_benchmark.py --collect-only -q`: collects all 3 tests with no skip
  shown, with the data present. It would read identically after the move with the `skipif`
  firing. Verification check 4 as written proves nothing.

**Rejected (2), with reasons.**

- **`CFB_DATA_DIR` as Critical — overstated.** `cli.py:929` is
  `os.environ.get("CFB_DATA_DIR", DATA_DIR_DEFAULT)` and `cli.py:44` sets
  `DATA_DIR_DEFAULT = str(DATA_ROOT)`, which is `cfb_paths`-derived. The variable is unset
  at both User and Machine scope, so the web command resolves to the canonical root today.
  Codex's "value `data` routes web app back into repo" requires someone to set it first.
  Downgraded from Critical to a documentation fix: `README.md:108` claims the default is
  `data`, which is wrong.
- **`launch.json` guarded wrapper — rejected.** `.claude/launch.json` is machine-specific
  by construction. Introducing a wrapper script so a dev-convenience static file server can
  resolve an environment variable adds a moving part to the least consequential item in the
  change. An absolute path there is honest about what the file already is.

**Promoted back to the user.** Finding 6 (sweep before move) reverses the commit ordering
locked in Q1/Q2. Codex's argument is stronger than the one used to lock it: after commit 1
the 14 bypassers and 9 Python fallbacks are still live, so a single manual script run in
the gap recreates `<repo>\data` — the precise failure the change exists to prevent,
occurring inside the change. Claude's position is that Codex is right. Not flipped
unilaterally, because the user locked it.

User chose **sweep first**. Plan restructured: commit 1 is the full sweep with the old root
still valid, commit 2 is the cutover.

### Round 2 — Codex

`VERDICT: REVISE` — 11 findings, 2 Critical. Codex confirmed six round-1 fixes landed
(ordering, trigger-disable sequence, the 14-site enumeration, notebook paths, move
preflight / task-state recording / catalog scan / fresh-process verification) and accepted
the `launch.json` wrapper rejection as reasonable.

1. **Critical** — `cfb_system_maker/CLAUDE.md` holds ~15 executable `--data-dir data`
   commands, missed entirely.
2. **Critical** — the manifest is captured before all writers stop; `CHECKPOINT` itself
   rewrites `cfb.duckdb` and the `.wal`, so the baseline races the thing it measures.
3. Forbidden-pattern scan cannot pass as written — after commit 1 the commit-2 files retain
   the old path by design, `CFB_DATA_DIR` is retained deliberately, and `"data/` matches the
   out-of-scope docstrings.
4. Check 7 requires `logs` to grow; check 9 demands exact byte equality including `logs`.
   Direct contradiction.
5. `CFB_DATA_DIR` rejection only partly valid — not Critical while unset, but still an
   active conditional resolver that bypasses the marker-validated root whenever set.
6. Marker proves intent, not identity — `.exists()` accepts a *directory* named
   `.cfb-data-root`; destructive pruning still trusts whatever local catalog is present.
7. Task recovery unsafe — a failure between steps 10 and 17 leaves all tasks disabled, and
   step 17 enabled everything before the canary proved the environment.
8. Subtree totals omit root-level loose files and the marker.
9. The slow-test command can exit 0 after skipping — `test_browser_smoke.py:5` is a
   module-level `importorskip`.
10. Stale worktrees remain a warning with no procedural step.
11. Count and rollback wording inconsistent.

### Claude's response — Round 2

**Accepted (9, plus 2 partial).** Findings 1-5, 7, 9, 10, 11 in full.

- **Finding 1 — Claude was wrong in round 1.** This file was raised in round 1 and rejected
  because Codex cited `cfb_system_maker/CLAUDE.md:20`, which is a pytest line. Checking the
  cited line instead of the file was the error: `grep -c -- "--data-dir data"` returns
  **16**. Added to commit 1. (The other half of Codex's claim — that the file also carries
  the old absolute root — does not hold; no such string is present.)
- **Finding 2** — steps reordered so the manifest is captured *after* checkpoint-and-close
  and immediately before the rename.
- **Finding 4** — resolved by ordering rather than exclusion: the manifest is now compared
  at step 21, before the canary runs at step 24, so `logs/` is still pristine when equality
  is asserted.
- **Finding 8, partial.** Root-level loose files accepted — the manifest now names all
  seven plus `.cfb-data-root`. Content hashing rejected: a same-volume rename cannot alter
  file contents, so per-file name+size is sufficient proof, and hashing 15 GB would defend a
  threat model that does not apply.
- **Finding 6, partial.** `.exists()` → `.is_file()` accepted. The "validated identifier"
  content scheme rejected as machinery that still fails against a deliberately copied
  marker. The real exposure is the destructive operation, so `prune_motherduck_orphans.py`
  now **fails closed** independently of the root guard — it refuses to classify any remote
  table as an orphan unless the expected local schemas and tables are present. That protects
  MotherDuck whether or not the root resolves correctly, which the marker alone never could.
- **Finding 5, reconciled.** Round 1's "Critical" downgrade stands on severity — the
  variable is unset, so nothing is broken today. Round 2's point that an unguarded
  conditional resolver contradicts the goal is accepted. Resolution: keep the override,
  route it through the marker-validated resolver, fix the wrong documentation.

### Round 3 — Codex

`VERDICT: REVISE` — 7 findings, 1 Critical. Both round-2 partial rejections upheld:
*"Hashing rejection is sound: same-volume rename plus full path/size manifest is enough.
Marker identifier rejection also sound if destructive prune gets stronger independent
validation."*

1. `cfb_system_maker/CLAUDE.md` **does** carry the old absolute root, under "Warehouse
   working copy".
2. **Critical** — the proposed prune guard is still weaker than fail-closed. "Expected
   schemas and tables exist" passes a stale or partly rebuilt warehouse, which then deletes
   every other remote table.
3. The `.is_file()` fix covers Python only — batch `if exist` matches directories, so a
   wrapper accepts a directory named `.cfb-data-root` and never reaches Python validation.
4. "Restore tasks on every failure path" is unsafe after the rename — it can re-enable jobs
   while filesystem and environment disagree.
5. The canary is conditional and underspecified — no proof runs if the task was already
   disabled, and an immediate result query reads the prior run.
6. The new guards have no targeted negative tests.
7. Nit — `data\cfb` is a 12,288-byte file, not a directory.

### Claude's response — Round 3

**All seven accepted.** No rejections this round.

- **Finding 1 — Claude was wrong about this file twice.** Round 1 rejected it on a wrong
  line number without grepping. Round 2 accepted the `--data-dir` half but stated the
  absolute-root half "does not hold" — that conclusion came from a grep whose backslashes
  were consumed by the shell, so it silently matched nothing. `cfb_system_maker/CLAUDE.md:88`
  contains the old root verbatim. Added to commit 2's doc list, which is now four docs.
- **Finding 2 — Codex's fix is better than Claude's and uses existing machinery.**
  Verified: `promote_to_motherduck.py:117` writes `meta.warehouse_version` to the target and
  its line-66 comment confirms it stamps the source too, so both sides carry a comparable
  version. `prune_motherduck_orphans.py:84` is a bare set difference with no validation at
  all. The guard is now anchor tables **plus an exact local↔remote version match**, tested
  against empty, partial and version-mismatched warehouses.
- **Finding 3** — third batch condition added using the trailing-backslash idiom, with a
  marker-directory negative test.
- **Finding 4** — "restore on every failure path" replaced with a state table: restore
  freely before the rename; after it, only once the cutover is complete or the filesystem
  and variable are rolled back together; if neither, leave tasks disabled and fail loudly.
- **Finding 5** — canary now force-enabled regardless of prior state, with prior
  `LastRunTime` recorded, a wait for the task and children to exit, and a requirement that
  `LastRunTime` be **newer** plus result 0 plus log growth.
- **Finding 6** — verification check 13 added for the guard negatives.

### Round 4 — Codex

**`VERDICT: APPROVED`.** *"Plan now sound enough to implement. No genuine blocker
remains."*

Codex re-verified against live files rather than the plan's tables: `cfb_system_maker/CLAUDE.md:88`
carries the old absolute path and is now covered; `promote_to_motherduck.py` stamps matching
local and remote `warehouse_version`; `prune_motherduck_orphans.py` currently performs the
unsafe bare set difference and the planned anchor/version guard closes it; `data\cfb` is a
12,288-byte file; the batch directory-marker condition is valid; **the resolver enumeration
shows no new live omission**.

Five minor items, explicitly classed as "execution-time wording/allowlist corrections, not
architectural or safety blockers" — all applied before sign-off:

1. Check 13 said "each rejects", but the **valid** `CFB_DATA_DIR` case must *succeed*;
   otherwise the test would pass a resolver that rejects everything.
2. Commit 1's run list did not name check 13.
3. Pre-move check 11 could not pass as written — the main catalog's own path necessarily
   contains the old root before the cutover, so a blanket "zero hits" is a false failure.
   Split into pre-move (zero in *stored objects*) and post-move (zero anywhere).
4. Risk 5 still said tasks restore "on every failure path", contradicting the coherent-state
   table added in round 3.
5. Step 4 still called the batch change a "two-line guard"; it now has three conditions.

## Resolution

Converged in **4 rounds** of `MAX_ROUNDS=5`. Findings 16 → 11 → 7 → 0 blockers; Criticals
7 → 2 → 1 → 0.

What the loop changed, beyond what the pre-loop plan contained:

- **Scope**: 4 sites → 31 unsafe resolvers plus one guard upgrade. The 14 direct
  `os.environ["CFB_DATA_ROOT"]` readers in `models/`, the 16 `--data-dir data` commands in
  `cfb_system_maker/CLAUDE.md`, and the 10+ in `README.md` were all invisible to the
  original analysis.
- **Ordering**: move-first → sweep-first, closing the window where the change could cause
  the failure it exists to prevent.
- **Guard**: "is the variable set?" → marker file, `.is_file()` in Python and a
  directory-rejecting third condition in batch.
- **MotherDuck**: the destructive prune gained an independent fail-closed guard on
  `meta.warehouse_version` identity — protection that does not depend on the root being
  correct at all.
- **Verification**: three checks were false greens (`--collect-only`, "log exists", a
  blanket pattern scan) and two contradicted each other (log growth vs. byte equality).
  Rebuilt and reordered.

Three Claude errors the loop caught, all on the same file: `cfb_system_maker/CLAUDE.md` was
rejected in round 1 on a mis-cited line number without grepping, then half-accepted in
round 2 on a grep whose backslashes the shell consumed. It holds 16 executable commands and
the old absolute root, and would have survived the entire change untouched.

User signed off. Claude implemented; a fresh read-only Codex session cross-inspected.

## Post-build inspection

Commit under review: `d237275`. Reviewer: a **new** Codex thread, not the Phase 2 one, so
it saw the code cold rather than through its own plan critiques. One round.

It found a **P0 that Claude's own verification had missed**, and the reason is the finding:

> "The claimed '1147 passed' must have run against the dirty working tree, not commit
> `d237275`."

Correct. Every test run during the build used the working tree. The commit was carved out
of it, so the two were never the same artifact, and nothing checked the one that shipped.

| # | Finding | Disposition |
| --- | --- | --- |
| P0 | `tests/test_core_agreement.py` imports `MEDIAN_PROVIDER`, absent from the committed `normalize.py` — the committed suite cannot collect | **Accepted.** The file was staged wholesale as "pure mine"; it carried in-progress median-line work coupled to an unstaged `normalize.py`. Restored to pre-commit state plus only the resolver change. |
| P1 | The prune guard call landed **inside a SQL string literal** | **Accepted.** Splitting a merged hunk changed its added-line count, shifting every later hunk target. Restaged from the working tree, with the call verified as a real `ast.Expr` rather than trusting the diff. |
| P1 | `floor_bias_1h.py` evaluates `DATA_ROOT` 14 lines before importing it — `NameError` on import | **Accepted.** `ast.parse` accepts that ordering; only importing catches it. All 24 converted modules are now import-checked, not merely compiled. |
| P1 | The sweep missed live resolvers and the scan cannot see them — three script defaults, eight `--data-dir data` operator messages in web templates, HTML and notebooks excluded, no pattern for `ROOT / "data"` or `default="data/cfb.duckdb"` | **Accepted.** Widened to `.html`/`.ipynb`, added both patterns, anchored the `/ "data" /` pattern to a repo-root variable so docs asset directories are not flagged. Seven more live resolvers fixed. |
| P1 | The version guard does not prove the local warehouse is *still* the promoted state — an in-place rebuild leaves the stamp valid | **Accepted as a limitation, not fixed.** The anchor+version gate raises the bar from "any directory" to "a complete warehouse matching the promoted stamp"; closing the remaining window needs promote/prune to agree on a freshness token, which is its own change. Recorded here rather than silently left. |
| P1 | Explicit `--data-dir` still bypasses marker validation on every non-`web` command, contradicting README's "every entry point refuses to run" | **Accepted, outstanding.** Real overclaim. Guarding `--data-dir` repo-wide is a separate change; the README wording and the guard should land together. |
| P1 | `rebuild_pregame_features.py` passes `--pregame --target-seasons` to a script that defines but never reads them | **Rejected as out of scope.** Verified pre-existing: `rebuild_pregame_features.py` was not dirty at session start, so that call predates this work. Real, and reported to the user, but not this change's to fix. |

Claude also found, while fixing the above, that **`tests/test_tv_grid.py` cannot collect on
`master` for the same reason** — `scripts/tv_grid.py` (`ddd3c4b`) imports `median_line` from
the unstaged `normalize.py`. Older, someone else's, reported not fixed.

Fixes landed in `0316be1`, verified in a throwaway worktree built **from the index**: 1118
passed, 1 skipped, phase-1 scan clean, zero import-ordering bugs. The two remaining
failures (`test_sql_course[B5]`, `test_system_versions`) reproduce on clean `HEAD` with none
of these changes.

**Process lesson, recorded because it caused the P0:** verifying a carved commit against the
working tree proves nothing about the commit. The throwaway-worktree check existed and was
run on the *staged tree* before committing — but only for compile and a subset of tests, not
the full suite. It now runs the full suite.

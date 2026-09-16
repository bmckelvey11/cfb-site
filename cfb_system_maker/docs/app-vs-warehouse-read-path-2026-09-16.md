# Should the Flask system maker read `cfb.duckdb` instead of the processed files?

**Answer: no, not the app's read path.** Two findings settle it, one platform-hard and one
scope-hard. A narrower version of the idea — retiring the `core` tables nobody reads — stays
open and is not addressed here. Corrected 2026-09-16: an earlier draft of this page said
`core.fact_game` had no reader. It has two.

Date: 2026-09-16. Reproduce the swap finding with `scripts/check_duckdb_swap_lock.py`.

## The question

Today the app reads `data/processed/games.csv` (13 columns, 13,936 rows, 1.3 MB) and
`data/processed/features.json` (62 MB), plus raw CFBD JSON indexed in-process by
`enrich.py`. It never opens the warehouse
([data-flow-guide.md §5](data-flow-guide.md)). Meanwhile `build_core` builds `fact_game`,
`fact_game_line` and `fact_game_team` that no consumer reads. The duplication invites the
question: point the app at `cfb.duckdb` and delete a derivation path?

## Finding 1 — a long-lived reader breaks the nightly rebuild (Windows)

`build_duckdb` stages the rebuild at `cfb.duckdb.building` and finishes with
`tmp_path.replace(db_path)` (`cfb_system_maker/duckdb_load.py:582`). On Windows `os.replace`
fails when another process holds the destination open, and DuckDB holds the file open at
`read_only=True` as well as read-write.

Measured 2026-09-16 on Windows 11, `scripts/check_duckdb_swap_lock.py`:

```
BLOCKED -- a long-lived reader breaks the rebuild swap.
  PermissionError: [WinError 5] Access is denied: ...live.duckdb.building -> ...live.duckdb
```

So a Flask process holding a warehouse connection makes step 5 of the 05:00 refresh fail —
every night the app is running, which is every night. Workarounds exist (open and close per
request, or per query) but they trade the premise away: a 5.3 GB file opened per request is
not the cheap read the move was supposed to buy, and the app would still be unreadable or
stale through the ~15-minute rebuild window that holds the exclusive lock.

This is the discriminator. It is not about database size.

## Finding 2 — `games.csv` is the trivial 2% of the move

The app's features do not exist in the warehouse. `features.json` carries 118 features per
game, built by `enrich.py` from ~20 raw JSON files per season plus four GraphQL dumps
(`game`, `gameWeather`, `gameLines`, `gameTeam`). Eight sampled feature families checked
against `duckdb_core.py`:

| Feature family | Present in `core`? |
|---|---|
| `pregame_win_prob` | no |
| `havoc_*_rate` | no |
| `returning_ppa` | no |
| `coach_style_cluster` | no |
| `running_ats_pct` | no |
| `recruiting_points` | no |
| `*_explosiveness` | no |
| `prior_srs_rating` | no |

Zero of eight. "Move the app to DuckDB" therefore means *rewriting the enrich feature
registry in SQL*, not repointing a CSV read. It would also have to reproduce the
`result_lookahead` tagging the no-lookahead rule depends on, which `core` has no machinery
for. `games.csv` — the part that looks like the migration — is 1.3 MB of the 63 MB the app
actually reads.

## What this does *not* support

- **Not an argument that `core` is worthless.** `research/spread` and the Prediction Tracker
  build read `stg`; the over-zero board reads `raw`. Only the *app's* read path is settled
  here.
- **Not a measurement of app startup cost.** Whether parsing 62 MB of JSON is slow was not
  measured. `web.py` fingerprints both files by size+mtime (`_data_fingerprint`) and memoizes
  backtests on that identity (`_cached_backtest`), so the parse is not per-request — but if
  boot time is the actual complaint, that is a separate investigation and DuckDB is not its
  answer.
- **Not a live divergence report.** The `games.csv` vs `core.fact_game_line` DraftKings
  disagreement described at `duckdb_core.py:238` is already fixed: `_provider_key` delegates
  to `normalize.provider_key`, and `normalize.py:53-56` records the measurement that closed
  it. The comment is rationale for why the delegation must stay, not an open bug.
- **Not an evaluation of deriving `games.csv` from `core.fact_game`.** That variant keeps the
  app on files while single-sourcing the derivation, but it puts the app's only data source
  downstream of refresh step 5 — the step that OOM'd on 2026-09-11 and silently dropped the
  Action Network tables. It trades a drift risk for an availability risk and was not costed.

## Still open

Which `core` facts are actually unread, measured 2026-09-16 by grepping the repo for each
table name outside `duckdb_core.py`, the audit scripts and the worktrees:

| Table | Reader |
|---|---|
| `core.fact_game` | `research/spread/scripts/eval_version_b.py:155`, `research/totals/scripts/grade_greenline.py:179` |
| `core.fact_game_line` | none (mentioned only in `normalize.py`'s rationale comment) |
| `core.fact_game_team` | none |
| `core.fact_game_odds` | none (mentioned only in `refresh_cfbd.py:224`) |
| `core.fact_game_historical` | none |

So the unread set is the four below `fact_game`, not the whole layer. Either give them a
reader or retire them; carrying unread Kimball facts is the real cost the original question
was circling. Not decided here.

Both readers of `fact_game` are short-lived script runs that `connect(..., read_only=True)`
and exit — the pattern Finding 1 permits. Neither holds the file across a rebuild.

[data-flow-guide.md §5](data-flow-guide.md) lists neither of them in its "Who reads what"
table, and says a `build_core` bug reaches nothing. That is now false for `fact_game`: it
reaches the version-B spread eval and Greenline grading. The table needs both rows.

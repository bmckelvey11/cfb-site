# CFBD Betting-Line Floor

**Confirmed floor: 2013** — the earliest season for which the CFBD `BettingApi.get_lines`
endpoint returns usable spread/total data. This is the practical history floor for the
backtester (DATA-01, D-01/D-02).

The evidence — an API probe plus the warehouse, with which book posted each era — is the
dated record [`cfbd-lines-coverage-2026-09-17.md`](cfbd-lines-coverage-2026-09-17.md),
which supersedes the 2026-06-13 on-disk snapshot this doc used to carry. What fills lines
before 2013 is [`pre-2013-lines-sources-2026-09-17.md`](pre-2013-lines-sources-2026-09-17.md).
This doc keeps only the living part: how the code treats a season without usable lines.

## The binding constraint is line coverage, not game coverage

Games are available back to 1992, but betting lines are the limiting factor. Under the
D-02 rule below, a season with games but no usable lines contributes **no rows**, so the
effective history floor equals the line-coverage floor (2013), not the game-coverage floor.

## D-02: require a usable line

`normalize.median_line` returns `None` when a game's `lines` list is empty or when no
line carries a spread or over/under (`_select_line` now serves only `duckdb_core`'s per-book
selection). Such games are dropped — they produce 0 GameRecords.
This keeps backtests clean and is why pre-floor seasons (e.g. 2012) cleanly contribute 0 rows.

This behavior is locked by tests in `tests/test_normalize.py`
(`test_line_less_game_contributes_zero_records`, `test_all_unusable_lines_contribute_zero_records`,
`test_usable_line_contributes_one_record`).

## "Backfill earlier" is a data-availability question, not a code change

The fetch and build paths are fully parameterized by `--season` (`nargs="+"`), with no
hardcoded floor year anywhere in `cli.py`, `web.py`, or `backtest.py`. Adding earlier
seasons requires only that CFBD return usable lines for them — no code change.

## Closure

The "backfill earlier than 2013" requirement (DATA-01, D-01 "as far back as lines allow")
is closed by **verification**, not an unbounded search:

1. A live re-confirmation probe (plan **03-03**) re-checks the current CFBD API against a
   bounded sweep (~2008–2013), in case CFBD backfilled pre-2013 lines since the 2026-06-13
   snapshot.
2. Pre-2013 seasons are backfilled via `fetch` → `build` → `enrich` **only if** that probe
   returns usable lines. If the probe confirms 2013, no backfill is possible against CFBD
   (the only wired source), and the floor stands as documented here.

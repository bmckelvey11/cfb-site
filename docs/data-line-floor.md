# CFBD Betting-Line Floor

**Confirmed floor: 2013** — the earliest season for which the CFBD `BettingApi.get_lines`
endpoint returns usable spread/total data. This is the practical history floor for the
backtester (DATA-01, D-01/D-02).

## Evidence (on-disk, verified 2026-06-13)

| Season | Games on disk | Line rows | Rows w/ any provider line | Usable consensus rows |
|--------|---------------|-----------|---------------------------|-----------------------|
| 2012   | 805           | 805       | **0**                     | **0**                 |
| 2013   | 813           | 813       | 813                       | 806 (consensus, numberfire, teamrankings) |

- The built `data/processed/games.csv` already spans **2013–2025 (12,964 games)**;
  `features.json` `_meta` reports 12,964 games. Verified on-disk.
- Games exist much earlier (1992, 1998, 2001–2004, 2007–2025), but the `lines_*.json`
  set starts at 2012 and 2012 is empty of actual line children.

## The binding constraint is line coverage, not game coverage

Games are available back to 1992, but betting lines are the limiting factor. Under the
D-02 rule below, a season with games but no usable lines contributes **no rows**, so the
effective history floor equals the line-coverage floor (2013), not the game-coverage floor.

## D-02: require a usable line

`normalize._select_line` returns `None` when a game's `lines` list is empty or when no
line carries a spread or over/under. Such games are dropped — they produce 0 GameRecords.
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

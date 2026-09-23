# Pregame replay: 2024 week 6, and whether the "open" has a clock

**Question.** Can a historical week be rebuilt from data that existed at each game's
kickoff? And does any line field we hold carry a real capture time, or is
`overUnderOpen` / `core.fact_game_line.total_open` only a label?

**Answer.** The replay can be rebuilt for 2024 week 6. The line has no clock:
`overUnderOpen` is a vendor label for the first number a book showed, captured at an
unknown time. The only real per-quote clock in the warehouse,
`stg.an_history_tick.updated_at`, starts 2026-04-02 and has zero rows for 2024. So a
2024 open can be scored as a **forecast** of the points total, but not as a
**price** at decision time.

Reproduce:

```text
python -m scripts.pregame_replay_audit --season 2024 --week 6
```

Script: [`scripts/pregame_replay_audit.py`](../scripts/pregame_replay_audit.py).
Leakage test: [`tests/test_pregame_replay.py`](../tests/test_pregame_replay.py).
Manifest: `data/processed/pregame_replay/replay_2024_w06.json` (gitignored; the
manifest holds the sha256 of every input file and of the script).

## Method

- **Population.** 2024 regular-season week 6 rows of `data/processed/games.csv`:
  102 games.
- **Decision time.** Each game's own kickoff. `games.csv` has no kickoff column, so
  kickoff is `startDate` from `data/raw/games_<season>.json`, the same source
  `models/middle/data.py` `_read_game_dates` uses. No week-6 game has
  `startTimeTBD`.
- **What a game may see.** Only rows whose kickoff is strictly earlier than its own.
  A same-week game tied at the same kickoff is future data. So is the game's own
  result. A row with no kickoff is never visible. Summed over the 102 decisions,
  5,543 same-week rows were excluded this way. Tied Saturday kickoffs account for
  most of that count.
- **Market number.** ESPN Bet `overUnderOpen` from `data/raw/lines_2024.json`. One
  fixed book, with no fallback to another book, no close, and no imputation.
  - It was chosen on coverage, before any scoring. ESPN Bet posted 49 opens this
    week and Bovada 48, and all 48 of Bovada's games are among ESPN Bet's 49.
    DraftKings posted none.
  - `models/middle` instead ranks Bovada first and falls back across books. That is
    a different rule and was not used.
- **Train mean.** The mean of `home_points + away_points` over every `games.csv`
  game with a kickoff strictly before the week's first kickoff, 2024-10-03 23:00Z.
  That is 10,888 games, from 2013-08-29 through 2024-09-29. It is fit on the past
  only and never on week 6.
- **Scoring.** Both baselines forecast the points total. The score is mean
  absolute error (MAE). The interval is a game-level percentile bootstrap, 10,000
  resamples, seed 20240606. `games.csv` `total` is a closing line, so the script
  renames it `close_total` and neither baseline reads it.

## Numbers

| Forecast | Games | MAE (points) | 95% interval |
| --- | ---: | ---: | --- |
| ESPN Bet open label | 49 | 15.07 | 12.26 – 17.91 |
| Train mean (55.85), same 49 games | 49 | 15.08 | 12.33 – 17.80 |
| Train mean (55.85), all week-6 games | 102 | 15.01 | 13.10 – 16.95 |

- **Which games have an open.** All 49 games with an open are FBS vs FBS. All 53
  without one are games not played between two FBS teams. So the 102-game row
  covers a different population from the market row. Compare the first two rows
  only.
- **Line clock evidence.** Every CFBD line dict for these games has exactly these
  keys: `awayMoneyline`, `formattedSpread`, `homeMoneyline`, `overUnder`,
  `overUnderOpen`, `provider`, `spread`, `spreadOpen`. None of them is a time.
  - The game-level `startDate` is kickoff, not a quote time.
  - `core.fact_game_line` has no time column either.
  - `stg.an_history_tick.updated_at` (Action Network) runs from 2026-04-02 to
    2026-09-22. It has 0 rows between 2024-09-26 and the last week-6 kickoff, and it
    is a different source in any case.

## What this changes downstream

- Any model scored against `ou_open` / `total_open` may claim **forecast skill
  against a labeled vendor number**. That is the whole claim.
- It may not claim to beat a price that was available at a known time. That rules
  out bet grading, price-based returns, and closing-line comparisons on these
  seasons. A price that cannot be reconstructed at decision time is a hard gate in
  [`model-evaluation-standard.md`](model-evaluation-standard.md).
- CFBD lines also carry no over/under odds, so a totals price is missing twice over:
  it has no clock and no juice.

## What this does not support

- **Not evidence that the open has no skill over a mean.** The first two rows
  differ by 0.01 points on one week of 49 games, and their intervals are about 5.5
  points wide. One week cannot separate the two forecasts. A paired, multi-week
  comparison would be needed, and it was not run here.
- **Not a statement about other weeks, seasons, or books.** Coverage of opens
  varies by book and era (see
  [`cfbd-lines-coverage-2026-09-17.md`](cfbd-lines-coverage-2026-09-17.md)).
- **Not a tuned baseline.** The train mean pools all divisions and all seasons back
  to 2013, even though scoring has drifted (see
  [`total-points-distribution-2026-09-17.md`](total-points-distribution-2026-09-17.md)).
  It is a floor, not a model.
- **Not an audit of the totals harness.** `models/middle` reads the same
  `overUnderOpen` field, so the clock finding applies to it. Its backtest was not
  re-run or re-scored.

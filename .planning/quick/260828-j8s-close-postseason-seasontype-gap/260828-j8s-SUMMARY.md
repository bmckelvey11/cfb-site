---
id: 260828-j8s
slug: close-postseason-seasontype-gap
date: 2026-08-28
status: complete
commits: [cf5fe68, 70fcdc2]
---

# Summary — postseason is in the dataset

`--season-type` defaulted to `regular` on `fetch` and `scrape` while CFBD's own default is
`both`. Flipped it, re-scraped the 13 SEASON-mode endpoints that accept the parameter, and
rebuilt. **`games.csv` 13,014 -> 13,515 (+501)**; every bowl and playoff game 2012-2025 is
now present, along with 586 priced postseason lines.

## What shipped

- `cli.py` (both `fetch` and `scrape`), `cfbd_client.fetch_games_and_lines`,
  `scrapers.scrape` — default `regular` -> `both`.
- `_scrape_season_week` pinned to `regular` regardless of caller, with the probe numbers in
  its docstring and a regression test (`test_season_week_ignores_season_type_and_stays_regular`).
- `docs/data-coverage.md` — the `seasonType` section rewritten from open gap to
  closed-for-13 / deferred-for-6.

## The finding that changed the plan

The plan said "flip the defaults." Flipping them everywhere would have been a regression.
SEASON_WEEK endpoints restart postseason week numbering at 1, so `both` + `week=1` returns
regular week 1 merged with postseason week 1 (`game_team_stats` 2024: regular=137,
postseason=50, both=187, and `both` == `regular | postseason` id-for-id). The filename
`{name}_{season}_wk{week}.json` cannot hold them apart. Six endpoints would have been
overwritten with conflated content. None of them feed `build`/`enrich`, so they are
deferred at zero cost; closing them needs a `_post_wk` filename axis.
**Superseded the same day by `260828-l60`, which added that axis and pulled them.**

## Verification

`verify_seasontype.py` (in this directory) gates on the only thing that discriminates:
regular-season row count **unchanged** per endpoint per season, postseason rows **present**.
A total row count catches neither failure.

It flagged three endpoints short on regular rows. Re-asking the API `regular` on the spot
returned the same lower number, and `both`'s regular subset matched it id-for-id — upstream
reprocessing since the last scrape, not loss caused by `both`. `drives` 2024 gained a
regular row, which a `both` bug cannot do.

Feature gate: 381 of 13,014 pre-existing games moved, all attributable to upstream churn in
re-scraped files. `running_games_played` — the one field that can only change if a game
entered a prior-game window — moved **nowhere**, so no bowl contaminated any regular game.

`upcoming.py` was checked and is unaffected: it already passed `season_type=_BOTH`
explicitly rather than relying on the default.

## Two things to carry forward

1. **`running_stats` has a dormant lookahead vector.** It sorts by `startDate` and falls
   back to `f"{season}-w{week:02d}"`; postseason weeks restart at 1, so a bowl with no date
   would sort to the front of the season. Today 0 postseason games lack a date
   (`check_postseason_sort_leak.py` re-checks it). One missing field away from live.
2. **The backtests have not been re-read.** Bowls entering the sample shifts every saved
   system's hit rate, p-value and holdout split, and the bowl subsample is small enough to
   invite over-reading. Do that under `econometrics`, not ad hoc.

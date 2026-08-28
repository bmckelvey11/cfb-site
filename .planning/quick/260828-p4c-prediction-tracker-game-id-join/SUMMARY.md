---
task: Combine prediction-tracker CSVs and join to CFBD game_ids
status: complete
created: 2026-08-28
completed: 2026-08-28
---

# Summary

`scripts/build_prediction_tracker.py` unions the 25 Prediction Tracker season CSVs
(`C:/Users/mckel/dev/cfb/prediction-tracker/ncaa{2001..2025}.csv`) into
`data/raw/prediction_tracker_lines.csv` — 17,755 rows × 178 columns — and attaches a CFBD
`game_id` to 17,754 of them (100.0%).

## Result

- **game_id attached: 17,754 / 17,755.** The one holdout is genuinely unresolvable and is
  left unmatched rather than guessed: 2017 UCF–Memphis, which PT files at week 3 with a
  0–0 (unplayed) score, while CFBD has two UCF–Memphis meetings that season — the
  hurricane-rescheduled week 5 game and the week 14 AAC championship — both typed
  `regular`. Nothing in the row distinguishes them.
- **Score agreement 17,731 / 17,754 (99.87%).** This, not the match count, is the evidence
  the join is right: PT `hscore`/`vscore` reproduce CFBD's home/away points on every row
  after orientation alignment.
- 409 rows are `orientation_flipped` (neutral-site and bowl home/road designations
  disagree between the two sources); 815 rows are CFBD `postseason`.
- 0 unresolved team names, 0 rows with no CFBD game found.

## What the work turned on

**The CFBD source had to change.** `data/raw/games_{season}.json` holds `seasonType=regular`
rows *only* (2025 is the lone rescraped exception), so joining against it silently lost
every bowl and conference championship — ~35 rows a season, which is exactly the 5–8%
"unmatched" the first pass reported. `data/processed/games.csv` is 2013+ and inherits the
same gap. The script reads `stg.game` from `data/cfb.duckdb` (the GraphQL-fed table)
instead, which carries postseason back to 2001. **Anything else joining on `data/raw/games_*.json`
is missing postseason too.**

**Week can't be in the join key.** CFBD numbers postseason weeks from 1; PT keeps counting
(19, 20). A `(season, week, home, away)` key drops essentially every bowl.

**Rematches split on final score, not week.** A pair like 2011 LSU/Alabama appears twice
(regular season + BCS title). Score is the only field that separates them reliably, so
`pick_game` prefers the candidate whose points agree, falls back to week, and returns
`ambiguous` rather than guessing.

**Team names resolve per season against that season's CFBD team set**, so era drift needs
no dated rules — `Central Florida`→`UCF`, `Connecticut`→`UConn`, `Louisiana-Lafayette`→
`Louisiana`, `Troy St.`→`Troy` each pick the spelling that existed that year. 141 distinct
PT names, explicit alias dict, no fuzzy matching.

## Known data quality (not join bugs)

23 matched rows carry `match_status=matched_score_mismatch` — the team pair is unique in
that season so the game_id is certain, but PT's own score is wrong or absent:

- 11 rows PT never filled in (blank or `0-0`), mostly hurricane-postponed 2016–2017 games.
- 9 rows are PT typos (Bowling Green 70 vs 69, Duke 29 vs 28, Rice 21 vs 14, …).
- 1 row (2006 New Mexico–Wyoming) has PT column misalignment: `hscore` holds `-18.95`.
- 2001 Oklahoma–North Carolina is the reverse — CFBD carries `10-0` for a game that
  finished 41–27.

9 `game_id`s map to 2 PT rows each. All legitimate: 4 are postponed games PT listed twice
(original 0–0 date + rescheduled result), 5 are near-duplicate PT rows differing only in a
line value.

## Files

- `scripts/build_prediction_tracker.py` — the builder (re-runnable, no network)
- `tests/test_prediction_tracker.py` — 6 tests over `pick_game` / `candidates` /
  `read_season_csv`, including the LSU/Alabama rematch and the ambiguous UCF/Memphis case
- `data/raw/prediction_tracker_lines.csv` — output, 8.1 MB, gitignored (regenerable)

Output columns: `game_id`, `cfbd_home_team`, `cfbd_away_team`, `cfbd_week`,
`cfbd_season_type`, `orientation_flipped`, `match_status`, `season`, then the union of every
season's original columns (`home`, `road`, `week`, `hscore`, `vscore`, and ~160 `line*`
model columns). Model column names are unioned case-folded but never fuzzy-merged —
`linemore` and `linemoore` stay separate because they may be different modelers.

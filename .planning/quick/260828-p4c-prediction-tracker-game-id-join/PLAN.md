---
task: Combine prediction-tracker CSVs and join to CFBD game_ids
status: in-progress
created: 2026-08-28
---

# Quick: prediction-tracker -> CFBD game_id join

## Goal

Union the 25 season CSVs at `C:/Users/mckel/dev/cfb/prediction-tracker/ncaa{2001..2025}.csv`
(~17.7k rows, per-year schema drift, 141 distinct team names) into one wide table and
attach a CFBD `game_id` to every row.

## Approach

1. **Union** — case-fold headers before union (2001 is `HOME`/`LINESAG`, later years
   `Home`/`linesag`). Add `season` from the filename. Drop ruler rows (home name is all
   digits, e.g. `1234567890123456` in ncaa2013). Do NOT fuzzy-merge model column names
   (`linemore` != `linemoore`).
2. **CFBD side** — `data/raw/games_{2001..2025}.json`. `data/processed/games.csv` is 2013+
   only so it cannot cover the first 12 seasons.
3. **Team names** — explicit alias dict, no fuzzy matching. 141 names is small enough to
   reach 100%. Include truncated spellings (`Louisiana-Lafaye`, `Texas-San Antoni`).
   Resolve per season and assert the resolved name is in *that* season's CFBD team set,
   to catch era drift (`Central Florida` -> `UCF`, `Connecticut` -> `UConn`).
4. **Join key** — `(season, home, away)`. **Not** week: CFBD files bowls/CFP as
   `seasonType=postseason` with its own week numbering while PT keeps counting regular
   weeks, so a week-bearing key would drop nearly every bowl. Week is a tiebreaker only,
   for in-season rematches.
5. **Orientation fallback** — on a miss, retry the reversed pair (neutral-site/bowl
   home-road designations disagree) and tag `orientation_flipped`.
6. **Unmatched rows are kept** with null `game_id` and a `match_status` reason
   (`no_team_match` / `no_game_match` / `ambiguous`).

## Done when

- Combined CSV written with `game_id` + `match_status` columns.
- **Score agreement is the acceptance criterion**, not match count: on matched rows
  PT `hscore`/`vscore` must equal CFBD home/away points. Any mismatch is a real bug
  (bad alias, wrong orientation, wrong rematch) and gets investigated, not tolerated.
- Per-season match rate reported; an outlier season means a name-map bug.

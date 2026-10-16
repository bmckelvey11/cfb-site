# Why 22 teams have no 2026 pace rating

**Question.** Through week 7 of 2026, `scripts/pace_stats.py` gives no `tempo_s` to 22 of
138 FBS teams, including Ohio State, Oregon and Penn State. Why, and can it be fixed?

**Answer.** Two causes. For 17 teams, CFBD's game clock is stuck in enough of their games
that the clock gate drops them, which leaves them under the 30-pair minimum. Those games
cluster at a few home stadiums, mostly in the Big Ten. The other 5 teams have usable clocks
but have played too few close games to collect 30 neutral snaps. Wallclock passes the gate
in every game the game clock fails, runs about 1 s behind the game clock, and would restore
pace for the 17. The other 5 need shrinkage toward a prior or a lower minimum.

This updates [pace-stats-2026-09-24.md](pace-stats-2026-09-24.md) in two places. In 2026
the failures follow the home site rather than the TV outlet. The wallclock calibration that
doc left open is a flat shift of about 1 s so far.

Script: [`scripts/pace_clock_gaps.sql`](../scripts/pace_clock_gaps.sql)
(`duckdb -readonly data/cfb.duckdb < scripts/pace_clock_gaps.sql`). The neutral-snap
counts apply `pace_stats.neutral_mask` to its last query's rows.

## Data

`stg.plays`, `stg.games`, `stg.media` and `core.fact_game_clock_quality` from the
2026-10-15 warehouse refresh. FBS-vs-FBS regular season, 2026 weeks 1–7 (333 games with a
quality row), plus 2024–2025 for comparison.

## How a team gets a pace number

A snap pair is a non-first-down rush and the next snap in the same drive. A game is dropped
if 10% or more of its pair deltas are zero or negative (`clock_ok`). A team needs 30 pairs
in neutral situations (Q1–Q3, score within 14, not the final 2:00 of Q2) to be rated.
A typical team gets about 11 neutral pairs per usable game, so it needs about 3 good games.

## Findings

**Coverage is not getting worse.** The game clock is usable in 79% of games in 2024, 85% in
2025 and 86% in 2026 (287 of 333). Week to week in 2026 it moves between 78% and 94% with no
trend.

**The bad clock is stuck, not missing.** No play in a failing game has a null clock. Each
play repeats its drive's start time. In Ohio State against Ball State, week 1 (game
401858432), Ball State's opening drive reads 14:14 on all four plays and Ohio State's next
drive reads 12:05 on every snap, while wallclock advances 35–40 s per play. Of the 46
failing games, 30 are mostly stuck (median 82% of deltas stale) and 16 are borderline at
10–26%.

**Failures follow the home stadium.**

| Home team | 2026 home games | Clock failed |
| --- | --- | --- |
| Ohio State | 4 | 4 |
| Penn State | 4 | 4 |
| Michigan State | 4 | 4 |
| Old Dominion | 2 | 2 |
| South Florida | 2 | 2 |
| James Madison | 2 | 2 |

By home conference, Big Ten games are usable 76% of the time (14 failures), against 98% for
the ACC and 95% for the Big 12. By TV outlet the lowest rates are BTN 68%, ESPNU 78% and
CBSSN 79%, with ESPN2, SEC Network and ACC Network at 100%. Before 2024 the outlet explained
the failures (only ABC/ESPN games were reliably clean). In 2026 the home pattern is the
stronger one. That points to the stadium's stats feed, which is an inference from the counts
and is not confirmed.

**Which teams, and why.**

| Cause | Teams | Usable games | Neutral pairs |
| --- | --- | --- | --- |
| Clock stuck in too many games | Ohio State, Penn State, Michigan State, Buffalo, FIU, James Madison | 2 each | 20–29 |
| | Massachusetts, Georgia Tech, Florida Atlantic, Colorado State, Boston College, UConn, Old Dominion, Oregon, Middle Tennessee | 3 each | 20–29 |
| | Akron, Utah State | 4 each | 20–29 |
| Too few close-game snaps | Southern Miss, Northern Illinois, UTEP, Ball State, Charlotte | mostly clean | 19–29 |

The five blowout-heavy teams had 55–67% of their pairs in games decided by more than 14,
against 24% league-wide. That leaves them 5–6 neutral pairs per game against a league
median of 10.8.

**Wallclock fills the clock gap.** Wallclock passes the same 10% test in all 46 failing
games, so every 2026 FBS game has one usable clock. In the 285 games where both pass (6,285
neutral pairs), the median pair is 36 s on the game clock and 37 s on wallclock. Team tempos
on the two clocks correlate 0.93 across 116 teams, and the median team difference is
+1.0 s. Using wallclock in the failed games brings 17 of the 22 teams to 30+ neutral pairs.
The five blowout-heavy teams stay at 19–29 either way.

## What this does not support

- It does not show why the home feeds fail. The stadium pattern is a count, not a confirmed
  cause.
- The wallclock pair counts are approximate. In failed games the "final 2:00 of Q2" filter
  still reads the frozen game clock.
- The 1 s offset is measured on 2026 weeks 1–7 only. It is not shown to hold by team, by
  stadium or late in the season.
- Nothing here is scored against totals or spreads.

## Next

A wallclock fallback in `pace_stats.PAIRS_SQL`, shifted by the season's median offset, would
rate the 17 clock-gap teams. The 5 blowout-heavy teams need shrinkage toward last season's
tempo, as `prior_v1` does for the possession ratings. Until then, the rankings page leaves
pace out.

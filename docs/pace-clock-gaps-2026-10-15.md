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

## Fix

`scripts/pace_stats.py` now keeps games that pass either clock. Game-clock games use the
game-clock delta. Wallclock-only games use the wallclock delta minus the season's median
(wallclock - game clock) gap, measured on pairs from games where both pass. Each pair
carries `clock_source`. Seasons before 2025 gain almost nothing, because wallclock is stale
in the same games as the game clock there. The five blowout-heavy teams still need
shrinkage toward last season's tempo, as `prior_v1` does for the possession ratings.

## Breaking ties

`tempo_s` is a median of whole-second deltas, so 120 of 133 rated 2026 teams share a value
with another team (29 distinct values). `scripts/pace_tiebreak.py` compares tie-free
alternatives on 2014–2026 team-seasons (`python -m scripts.pace_tiebreak <out_dir>`).

| Stat | Split-half r | Full-season r | YoY r | Distinct 2026 | Teams tied 2026 |
| --- | --- | --- | --- | --- | --- |
| median (`tempo_s`) | 0.776 | 0.874 | 0.666 | 29 | 120 |
| interpolated median | 0.781 | 0.877 | 0.668 | 99 | 61 |
| mean of deltas ≤ 90 s | 0.803 | 0.891 | 0.689 | 127 | 12 |
| IQM | 0.788 | 0.881 | 0.677 | 129 | 8 |
| Hodges-Lehmann | 0.807 | 0.893 | 0.688 | 29 | 126 |
| mean of game medians | 0.764 | 0.866 | 0.664 | 118 | 27 |

The trimmed mean is slightly more reliable, but it reads wallclock-heavy teams fast (about
0.6 s on average, 2–2.7 s for Ohio State, Penn State and Michigan State), because the
wallclock shift is calibrated on the median and the two clocks' tails differ. Re-shifting by
the mean gap (`--mean-calibrated`) does not remove it. The interpolated median shows no such
bias, so the rank uses it, with the trimmed mean breaking its remaining ties: 133 distinct
ranks. The reliability gain over `tempo_s` is small; this fixes ties, not noise.

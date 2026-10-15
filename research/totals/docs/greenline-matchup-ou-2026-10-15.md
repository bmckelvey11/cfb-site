# Greenline unders by offense/defense matchup and by over/under record: both null

2026-10-15

## Question

These are two follow-ups to [pff under screen](greenline-pff-under-screen-2026-10-15.md),
asked the same day and run on the same graded unders.

1. Do combinations of good or bad offenses and defenses, judged by PFF grades, separate
   winning Greenline unders from losing ones?
2. Does a team's over/under record so far this season matter? The idea was that the market
   has already moved totals for teams that keep going over, and PFF's projection might lag
   that move.

## Answer

**Neither filters the unders.** The nine matchup cells do not differ by more than chance
(permutation p 0.12), and the eras disagree about which cells win. Over/under history has no
slope on the unders (p 0.98 and 0.71).

Market-wide there is a small effect, but it runs the other way from the idea above: games
between teams that have been going over land slightly *under* the close. That is the market
overshooting, not PFF lagging, and at about 0.4 points per SD it is too small to beat −110.

## Method

Script: [`greenline_matchup_ou.py`](../scripts/greenline_matchup_ou.py). The sample is the
409 graded Greenline unders from `under_filters.greenline_unders()` across 2020, 2022-23 and
2026 weeks 2-7. The outcome is cover margin, the capture line minus the actual total, so a
positive margin favours the under.

- **Matchup grid.** Offense quality is the snap-weighted PFF `grades_offense`. Defense
  quality is the snap-weighted `grades_defense`. Both use the screen's no-lookahead window:
  last regular season plus this season strictly before the game's week. A team counts as
  "good" at or above its era's median. Each game falls in one of nine cells, by how many of
  its two offenses are good (0-2) and how many of its two defenses are good (0-2). The test
  is a one-way F on era-demeaned margins with a within-era permutation p-value (5,000
  draws). The cluster-robust Wald test was tried first and dropped. With 2026's 16 slate
  dates and eight restrictions it read F 15.8 on data whose permutation p is 0.16.
- **Over/under record.** Each team's games this season before the game week, using the
  median REST-backed close (`_source <> 'gql'`), with at least two prior games required.
  - `ou_resid`: mean of (actual − close).
  - `ou_over`: share of those games that went over, pushes dropped.

  The game's value is the mean of the two teams. Each feature gets a slope with era fixed
  effects and date-clustered SEs, and Holm is applied across the two. Each is also run on
  every FBS regular-season game's close residual, weeks 3-14, 2015-2026, as a market-wide
  control.
- **Trials.** 1 grid + 2 O/U = 3, which brings the running total for this question to 23
  (the screen's 20 included).

## Numbers

**Matchup grid, all eras** (403 unders with both teams' grades; omnibus permutation p 0.118):

| good offenses | good defenses | n | record | win% | mean margin |
| ---: | ---: | ---: | --- | ---: | ---: |
| 0 | 0 | 48 | 28-20 | 58.3 | +3.9 |
| 0 | 1 | 42 | 21-21 | 50.0 | −3.0 |
| 0 | 2 | 15 | 11-4 | 73.3 | +10.6 |
| 1 | 0 | 44 | 24-20 | 54.5 | +1.9 |
| 1 | 1 | 93 | 40-53 | 43.0 | −1.8 |
| 1 | 2 | 55 | 30-25 | 54.5 | +1.0 |
| 2 | 0 | 15 | 8-7 | 53.3 | −1.9 |
| 2 | 1 | 53 | 31-22 | 58.5 | +1.4 |
| 2 | 2 | 38 | 19-19 | 50.0 | +0.1 |

By era the omnibus test gives 2026 p 0.159 and 2020 + 2022-23 p 0.385. The cells do not
replicate:

| cell | 2026 | 2020 + 2022-23 |
| --- | --- | --- |
| two good offenses, two good defenses | 35% (7-13) | 67% (12-6) |
| two good offenses, two bad defenses | 83% (5-1) | 33% (3-6) |

The intuitive "two bad offenses, two good defenses" cell goes 11-4 in total, 7-2 and 4-2 by
era. Fifteen games cannot carry a filter. Each extra good offense moves the margin −0.8 pts
(p 0.43), and each extra good defense moves it −0.1 (p 0.90).

**Over/under record to date:**

| feature | unders slope (pts/SD) | p | Holm | 2020 + 2022-23 | 2026 | market-wide control |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| `ou_resid` | +0.03 ± 0.86 (n=329) | 0.976 | 1.00 | +1.81 ± 0.89 | −1.26 ± 1.20 | +0.41 ± 0.21 (n=7,722, p 0.052) |
| `ou_over` | −0.24 ± 0.64 (n=328) | 0.710 | 1.00 | +0.64 ± 1.15 | −0.87 ± 0.67 | +0.43 ± 0.19 (n=7,720, p 0.020) |

The two eras point in opposite directions on both features. Under win% by `ou_over` third
is 48.7 / 56.7 / 49.5, with no ordering.

## What this does not support

- **Not any matchup cell as a filter.** The best cells are 15 games each, and they flip
  between eras. The "mixed" 1-1 cell losing 40-53 has no story behind it, and its
  replication across eras (38.5%, 48.8%) is the kind of match nine cells produce by
  chance.
- **Not "PFF lags market adjustments."** If PFF's under flags were stale on over-heavy
  teams, those unders would lose more. They do not (slope ~0).
- **Not a market-wide over/under fade as a bet.** The control's positive sign means a
  game whose teams have been going over tends to land about 0.4 points under the close per
  SD of the feature. At most that is 1.6 pp of win probability against the 2.4 pp −110
  needs. It is one of two control tests, not adjusted for the rest of the search, and its
  p 0.020 is not a finding until a pre-registered test on new seasons repeats it.

## Every FBS game, not just Greenline's

Asked the same day: run both questions on every FBS regular-season game, weeks 2-14 of
2015-2026, with a REST-backed close (`greenline_matchup_ou.py --market`). That is 9,117 games
with a decided over/under. Of those, 5,999 have both teams' grade profiles and 7,671 have both
teams' O/U histories. The outcome is the under against the median close. "Good" means at or
above that season's median across the sample. 2015-20 and 2021-26 are reported separately as
a replication check. The 2015-20 rows are thinner because REST closes cover fewer games then.

**Matchup grid** (omnibus permutation p 0.068, 1,000 draws; 2015-20 p 0.374, 2021-26 p 0.080):

| good offenses | good defenses | n | under record | under % | 2015-20 | 2021-26 |
| ---: | ---: | ---: | --- | ---: | ---: | ---: |
| 0 | 0 | 594 | 296-298 | 49.8 | 50.5 | 49.5 |
| 0 | 1 | 742 | 359-383 | 48.4 | 47.0 | 49.4 |
| 0 | 2 | 229 | 116-113 | 50.7 | 52.8 | 48.8 |
| 1 | 0 | 668 | 347-321 | 51.9 | 52.0 | 51.9 |
| 1 | 1 | 1,463 | 723-740 | 49.4 | 51.7 | 48.0 |
| 1 | 2 | 718 | 360-358 | 50.1 | 55.1 | 47.2 |
| **2** | **0** | **248** | **141-107** | **56.9** | **57.0 (65-49)** | **56.7 (76-58)** |
| 2 | 1 | 730 | 380-350 | 52.1 | 54.1 | 50.7 |
| 2 | 2 | 607 | 314-293 | 51.7 | 51.8 | 51.7 |

One cell stands out, and it is the opposite of a Greenline-style under. When **both offenses
are good and both defenses are bad**, the under wins 56.9%, and it does so at the same rate in
both halves. The market's total in those games runs about 1.8 points too high. This is the
best of nine cells chosen after looking, so the pooled number is optimistic. The cleaner read
uses the halves: the cell was also best in 2015-20, and on 2021-26 it went 76-58. That is
p ≈ 0.07 one-sided against 50%, and p ≈ 0.18 against the 52.38% break-even at −110. It is a
lead with a mechanism a bettor could name ("the market over-adds for shootouts"). It is not
yet a system, and it is not in PFF's under flags: those 15 Greenline games went 8-7.

**Over/under record to date:**

| feature | all (pts/SD) | 2015-20 | 2021-26 | under % by fifth, low → high (all) |
| --- | ---: | ---: | ---: | --- |
| `ou_resid` | +0.40 ± 0.21 (p 0.054) | +0.79 ± 0.36 | +0.26 ± 0.25 | 49.6 / 48.0 / 48.7 / 53.3 / 52.6 |
| `ou_over` | +0.43 ± 0.19 (p 0.022) | +0.67 ± 0.36 | +0.34 ± 0.22 | 48.4 / 48.8 / 50.6 / 51.3 / 53.2 |

The direction holds in both halves: teams that have been going over drift back under. The
effect shrinks in the later half, though. The top fifth of `ou_over` hits 53.2% overall and
52.2% in 2021-26, which is below the 52.38% needed at −110. It is real enough to use as a
model feature and too small to bet alone.

Trials for this question: 23 on the unders, plus 3 here = 26.

## Reproduce

```
python research/totals/scripts/grade_greenline.py --week 2 --week 3 --week 4 --week 5 --week 6 --week 7
python research/totals/scripts/greenline_matchup_ou.py
python research/totals/scripts/greenline_matchup_ou.py --market
```

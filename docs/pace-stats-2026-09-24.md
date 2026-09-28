# Pace stats from play-by-play clock deltas

**Question.** Can play-by-play give team pace stats that measure something plays per game
and possessions per game do not? Those two are already held: raw plays per game is priced
by the market ([stat-angles-retest.md](stat-angles-retest.md)), and possessions feed the
ridge pace rating $P$ ([weekly-ratings-2026-09-23.md](weekly-ratings-2026-09-23.md)).
The comparisons below use raw possessions per game, the unshrunk input to $P$, not $P$
itself.

**Answer.** One stat is new and solid. Neutral tempo (`tempo_s`, seconds per snap) has a
full-season reliability of 0.90 and a year-over-year r of 0.64. Its within-season
correlation with plays per game is −0.58, so it shares about a third of its variance with
volume. It is not a relabel. The other three stats fail for three different reasons:

- `hurry_rate` duplicates `tempo_s` (r −0.92).
- `trail_delta_s` is noise.
- `tempo_faced_s` is mostly schedule, not defense: r 0.71 with the offenses' own tempo.

Nothing here is scored against totals.

Script: [`scripts/pace_stats.py`](../scripts/pace_stats.py) (`python -m scripts.pace_stats`).
The clock-coverage and wallclock tables come from
[`scripts/pace_clock_coverage.sql`](../scripts/pace_clock_coverage.sql).
Test: `tests/test_pace_stats.py`.

## Data and a trap found on the way

- **Source.** `stg.plays` joined to `stg.games`, FBS-vs-FBS regular season, 2012–2026
  (2026 through week 2).
- **FCS in the play feed.** The FBS filter is required. The count of distinct offenses in
  `stg.plays` jumps from 227 (2021) to 297 (2022) because FCS coverage arrives.
- **The game clock is stale in whole games.** A game is stale when most of its
  consecutive snaps repeat the same clock. The per-game split is bimodal, not uniform
  noise, so stale games can be dropped whole.

| Seasons | FBS games with a clean clock | Stale games |
| --- | --- | --- |
| 2012–2014 | 54–61% | 38–45% |
| 2015–2023 | 31–45% | 55–68% |
| 2024 | 79% | 17% |
| 2025 | 85% | 10% |

**What a stale game looks like.** Every play carries its drive's start clock. Florida
against Towson (2019, game 401110809) shows 15:00 on all 12 snaps of the opening drive,
and only the touchdown gets a real time (9:28). Drive start and end times are kept, so
drive elapsed time is still usable: in 2015–2023, drives of 3+ plays show 0 s elapsed in
3.0% of stale games against 0.6% of clean ones, with medians of 119 s and 124 s.

**The cause is the broadcast, not the stadium.** Clean-clock rate by TV outlet,
2015–2023 FBS games with one TV listing:

| Outlet | Games | Clean 2015–23 | Clean 2023 | Clean 2024 | Clean 2025 |
| --- | --- | --- | --- | --- | --- |
| ABC | 373 | 96% | 91% | 98% | 94% |
| ESPN | 651 | 92% | 74% | 86% | 93% |
| CBS | 168 | 69% | 26% | 81% | 86% |
| FOX | 288 | 59% | 23% | 85% | 87% |
| ESPN2 | 505 | 57% | 23% | 69% | 86% |
| ESPNU | 445 | 29% | 17% | 67% | 73% |
| FS1 | 390 | 24% | 21% | 87% | 84% |
| BTN | 300 | 22% | 29% | 90% | 89% |
| CBSSN | 539 | 10% | 15% | 73% | 72% |

In the same stadium, ABC/ESPN games have a clean clock 93% of the time against 37% on
every other outlet. That comes from 79 home teams with 3+ games of each (1,001 against
2,573 games), and all 79 show the gap. In 2024 every outlet jumps to about 70–90%, so the
upstream play-by-play feed changed that season for all games at once. By conference, the
same split shows up as SEC 58% down to Conference USA 6% in 2015–2023, which follows the
TV contracts.

CFBD takes its play-by-play from an upstream provider. The most likely reading is that
the provider recorded a per-play clock only for its top-tier broadcasts until 2024.
Nothing here confirms that; it is an inference from the outlet split.

**The gate is a core table.** `core.fact_game_clock_quality` has one row per game in
`stg.plays` and is built by `build_core` on every refresh. It carries the stale shares
and two flags:

- `clock_ok` is true when under 10% of the game's post-rush clock deltas are zero or
  negative.
- `wallclock_ok` applies the same test to wallclock.

The table counts regulation only, because college overtime has no game clock. That is
why these shares run about a point above a count that includes OT snaps. `pace_stats.py`
keeps `clock_ok` games: 4,808 games and 186,964 snap pairs.

**Wallclock** (2018+) goes stale in the same games through 2024, so it adds no coverage
there and is not used. It changes from 2025:

| Season | Clean game clock | Clean wallclock | Clean on either |
| --- | --- | --- | --- |
| 2025 | 85% | 75% | 91% |
| 2026 (week 2) | 85% | 99% | 100% |

In games where both clocks pass, wallclock tempo tracks clock tempo in every season
from 2018 to 2025 (team-season r 0.80–0.91), and its median runs 1.5–6.5 s higher. In 2025
the figures are r 0.91 and 38.0 s against 36.0 s. That makes wallclock the v2 path to a
live 2026 rating, after a per-season calibration between the two clocks. That path is
not built here.

Any clock-based idea hits the same wall, including tempo elasticity in
[cross-domain-derived-metrics.md](cross-domain-derived-metrics.md) §4. In 2015–2023 it
sees a third to a half of games, and which games survive depends on the feed, not at
random.

## Method

- **Pair.** A snap pair is a rush followed by the next snap in the same drive, period and
  offense. The rush is not a first down and not a touchdown. The next play is a scrimmage
  play. Neither play is a timeout or a penalty.
- **Why rushes only.** They keep the clock running between the two snaps in every season.
  Excluding first downs makes the 2023 clock rule change irrelevant.
- **Delta.** The delta is play duration plus huddle-to-snap time. Play duration varies
  little between teams, so the differences are tempo.
- **Neutral state (provisional).** Q1–Q3, score within 14, and not the final 2:00 of Q2.
  **Trailing** means down 9 or more, outside the final 2:00 of either half.

| Stat | Definition |
| --- | --- |
| `tempo_s` | Median neutral seconds per snap, offense (lower = faster) |
| `hurry_rate` | Share of neutral snaps inside that season's fastest league quartile |
| `trail_delta_s` | Median trailing seconds minus `tempo_s` (negative = speeds up when behind) |
| `tempo_faced_s` | Median neutral seconds of opponents' snaps against this defense |

**Sample floors.** A team-season needs 30 neutral pairs for `tempo_s` and `hurry_rate`.
It needs 15 trailing pairs for `trail_delta_s`, and 30 faced pairs for `tempo_faced_s`.

**Reliability measures.**

- **Split-half.** Games alternate into two halves by week order; the result is the r
  between the halves.
- **Full-season.** The split-half r stepped up with Spearman-Brown.
- **Year-over-year.** The same team's stat in season $s$ against season $s+1$.
- **Volume correlations.** Z-scored within season, so the league-wide drift does not
  inflate them.

## Numbers

**The league slowed down.** Median neutral tempo was 30–31 s per snap in 2012–2019. It
rose to 32 s in 2020–21, 33 s in 2022, 35 s in 2023, and 36 s in 2024–26. Cross-season use
needs within-season z-scores.

| Stat | Split-half r | Full-season r | Year-over-year r | Team-seasons |
| --- | --- | --- | --- | --- |
| `tempo_s` | 0.821 | 0.901 | 0.644 | 1,260 |
| `hurry_rate` | 0.734 | 0.847 | 0.550 | 1,260 |
| `trail_delta_s` | −0.013 | −0.026 | 0.079 | 1,016 |
| `tempo_faced_s` | 0.385 | 0.556 | 0.515 | 1,301 |

Within-season correlations (z-scored):

| | `tempo_s` | `hurry_rate` | `tempo_faced_s` | plays/game | possessions/game |
| --- | --- | --- | --- | --- | --- |
| `tempo_s` | 1 | −0.919 | 0.137 | −0.582 | −0.511 |
| `tempo_faced_s` | 0.137 | −0.146 | 1 | −0.198 | −0.206 |

**Tempo and offensive EPA: near zero.** Against opponent-adjusted offensive EPA per play
(`stg.adjusted_team_season.epa_total`), `tempo_s` has r −0.05 in 2025 (95% CI −0.22 to
0.12, 135 teams) and −0.04 over 2024–2025 on within-season z (268 team-seasons, mostly the
same teams twice). That rules out a strong linear link, not a modest one, and says nothing
about subsets or nonlinear shapes. Earlier seasons are left out because their clean-clock
games lean toward ABC/ESPN broadcasts. Chart:
[`scripts/pace_epa_chart.py`](../scripts/pace_epa_chart.py).

**2025 extremes** (135 teams rated):

- **Fastest:** South Florida 23.0 s, East Carolina 25.0, Tennessee 26.0, West Virginia
  26.0, Florida Atlantic 26.5.
- **Slowest:** Vanderbilt 43.0 s; then Central Michigan, Northwestern and UL Monroe at
  41.0; then Illinois, Iowa, Minnesota, Nevada and Washington State at 40.0.

**Coverage.** Clock staleness decides how many teams get a rating:

| Season | Teams rated (of about 130) |
| --- | --- |
| 2021 | 89 |
| 2022 | 89 |
| 2023 | 63 |
| 2024 | 133 |
| 2025 | 135 |
| 2026 (week 2) | 8 |

## What this does not support

- **Not that tempo predicts totals or beats the market.** Nothing was scored. Raw pace is
  already priced ([stat-angles-retest.md](stat-angles-retest.md)). Whether `tempo_s` adds
  anything beyond plays per game and $P$ is a separate test, bound by
  [model-evaluation-standard.md](model-evaluation-standard.md).
- **Not that defenses force a pace.** `tempo_faced_s` correlates 0.71 (within-season z,
  1,296 team-seasons) with the pair-weighted own tempo of the offenses it faced. Its
  full-season reliability is 0.56, so schedule accounts for nearly all of the reliable
  part. It is also about as stable year over year (0.52) as within a season, which fits
  repeating conference schedules. Any defensive pace-forcing effect would have to be
  measured as a residual against opponents' own tempo. That was not done here.
- **Not that teams show no score-state tempo response.** The per-team samples are 15+
  trailing pairs, and good teams rarely trail. At that size, `trail_delta_s` measures
  nothing. A pooled or shrunk estimate might.
- **Not unbiased coverage in 2015–2023.** Which games have a clean clock depends on the
  feed. A team's rated games may lean toward some venues.
- **Not a live 2026 rating yet.** 8 teams clear the 30-pair floor through week 2. As-of
  use needs shrinkage toward the prior season, and wallclock would add games (see
  above). `pace_team_game.csv` carries team-game rows for that.

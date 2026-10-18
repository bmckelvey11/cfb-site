# ridge_v1 home edge, declared before build — design

**Status:** declared 2026-10-17, before any variant is built or scored.
**Why:** the market-implied score baseline found `ridge_v1` over-forecasts home teams by about
0.5 points and under-forecasts away teams by about 1.2, so its home edge is too large by
roughly 1.7 points of margin on 2023–25
([`../market-implied-score-baseline-2026-10-17.md`](../market-implied-score-baseline-2026-10-17.md)).
**Suspected cause (untested):** `fit_ppp` in `scripts/weekly_ratings.py` penalizes every
team's offense and defense toward 0 but leaves the home term $h$ unpenalized. When the
better team is more often at home, the shrunk team ratings leave part of the strength gap
unexplained, and the free $h$ absorbs it. The same mechanism inflated a true 3.0 home edge
to 3.37 in a random-effects model ([arXiv 1806.08059](https://arxiv.org/pdf/1806.08059)).
The fit set is already FBS-vs-FBS only, so FCS home games are not the cause.
**Leaves alone:** every frozen Glicko file and holdout, P1's sealed confirmation, the sealed
2026 `prior_v3` confirmation, and `ridge_v1`'s λ picks (40 possessions, 8 games). Nothing
here reads a game after 2026-10-16.

## Variants

All three use `ridge_v1`'s λ and differ only in where $h$ comes from. A fixed $h$ is moved
to the left-hand side of the fit, so the team ratings are fitted given it.

| Name | Home edge $h$ (points per possession) |
| --- | --- |
| `free` | Fitted each week from the season's games so far, unpenalized. This is `ridge_v1` unchanged |
| `carry` | Fixed at the end-of-regular-season `free` fit of the previous season, every week. 2020 is never carried (empty stadiums): 2021 carries 2019 |
| `fixed` | Fixed at 2.4 points of margin, converted each week as $h = 2.4 / (2\bar N)$ |

$$
\begin{gathered}
h = \frac{H}{2\bar N} \\[1em]
\begin{array}{rl}
\text{where}\quad H: & \text{home edge in points of margin, 2.4} \\
\bar N: & \text{mean regulation possessions per team per game in the week's fit set} \\
h: & \text{home edge in points per possession, added to the home rate and subtracted from the away rate}
\end{array}
\end{gathered}
$$

The home rate gains $h$ and the away rate loses $h$, each over about $\bar N$ possessions, so
the margin moves by $2h\bar N = H$. With $\bar N = 12$, $H = 2.4$ gives $h = 0.1$. The 2.4 is
the 2023 FBS estimate of Benz, Bliss and Lopez ([arXiv 2401.16392](https://arxiv.org/pdf/2401.16392)),
taken as declared, not tuned.

## Games and forecasts

- **Scored games:** completed FBS-vs-FBS games, regular season and postseason, with final
  scores (`scripts.market_implied_scores.scored_games`). Week 1 has no same-season evidence
  and is skipped, as in every `ridge_v1` record.
- **Forecast:** each side's regulation points from `scripts/weekly_forecast.py::_parts`, plus
  half the fit's overtime constant, from the fit frozen at the week's first kickoff. The same
  forecast the baseline record scored.
- **Fit set:** the season's non-gated regular-season games that kicked off before that cutoff.

## Windows and the pick

- **Pick:** 2014–2019. Each variant's forecast SD (one number for both sides) is fitted on
  this window by mean CRPS on the baseline's 0.5-point grid (8–16). The pick is the variant with
  the lowest mean per-game CRPS (mean of the two sides) at its own SD.
- **Check:** 2021–2025, SDs held fixed. 2020 is not scored.
- **Adopt rule:** the pick replaces `free` as the weekly ratings' home edge only if it is not
  `free` and its paired CRPS difference against `free` on 2021–2025 has a 95% interval wholly
  below 0. Otherwise `ridge_v1` stands.
- **Paired intervals:** season-week block bootstrap, 2,000 draws, seed 20261017, as in the
  baseline.

## Reported

- Per variant and window: per-side MAE, RMSE, CRPS, bias and calibration slope, home and away
  separately and pooled; margin bias (actual minus forecast home margin) and margin MAE;
  total MAE.
- Paired CRPS and MAE differences, `carry` and `fixed` minus `free`, both windows.
- On 2021–2025 games that also have a Bovada open: per-side MAE and margin bias of every
  variant beside `implied`, and paired MAE differences against `implied`.
- Diagnostic: `free`'s fitted $h$ in points of margin ($2h\bar N$) by season and week, and its
  margin bias by week bucket (2–4, 5–8, 9+, postseason).

**Trial count:** 3 variants, each with one SD fitted on a 17-point grid. `ridge_v1` itself has
been scored against these seasons before (Release B and the baseline), so 2021–2025 is a
repeat look and the check is descriptive, not a confirmation.

## What it will not support

- A home edge in totals: $h$ cancels in the total, so any total change comes only through
  the refitted offense and defense ratings.
- A claim about Glicko's home edge, which bundle P3-C tests on its own sealed holdout.
- A claim that 2.4 is the true home edge: `fixed` tests one declared value, not a grid.

Script: `scripts/ridge_home_edge_eval.py`. Output: `processed/ratings/ridge_home_edge.json`.

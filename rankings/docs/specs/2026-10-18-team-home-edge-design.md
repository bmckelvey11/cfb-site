# Per-team home edge, declared before build — design

**Status:** declared 2026-10-18, before any code is written or any data is read.
**Why:** Blake asked why the models use one home edge for every team. The 2026-10-16 review
ranked team-specific home field as "skip": raw per-team estimates are mostly noise, and in the
NFL past team home edge predicts essentially nothing
([`../glicko-adjustments-review-2026-10-16.md`](../glicko-adjustments-review-2026-10-16.md)).
That claim was never tested on our data. This test does that, with each team's estimate pulled
toward the league value, as Massey does.
**Base model:** `ridge_h24`, the weekly forecast's ridge with the league home edge held at 2.4
points ([`../ridge-home-edge-2026-10-17.md`](../ridge-home-edge-2026-10-17.md)).
**Leaves alone:** every frozen Glicko file and holdout, P1's sealed confirmation, the sealed
2026 `prior_v3` confirmation, `ridge_v1`, and `ridge_h24`'s fit. Nothing here reads a game
after 2026-10-17.

## The question, in two parts

1. **Does a team-specific home edge exist in our data?** Answered by a reliability check that
   needs no model choice.
2. **If it does, does adding a shrunk per-team term improve `ridge_h24`'s forecasts?**

## Part 1: reliability check

For every completed FBS-vs-FBS game, regular season and postseason, 2013–2025 without 2020,
take `ridge_h24`'s walk-forward forecast (week 1 skipped, as in every ridge record) and its
margin residual $e = \text{actual margin} - \text{forecast margin}$, home minus away. For team
$i$ in season $s$, its raw home edge is:

$$
\begin{gathered}
d_{is} = \frac{1}{2}\left(\bar e^{\,\text{home}}_{is} - \bar e^{\,\text{away}}_{is}\right) \\[1em]
\begin{array}{rl}
\text{where}\quad \bar e^{\,\text{home}}_{is}: & \text{mean margin residual in team } i\text{'s true home games in season } s \text{, points, home minus away} \\
\bar e^{\,\text{away}}_{is}: & \text{mean residual in its road games, with the sign flipped to team } i\text{'s side, points} \\
d_{is}: & \text{how much better team } i \text{ does at home than on the road beyond the league edge, points}
\end{array}
\end{gathered}
$$

Neutral-site games count as neither. Halving turns the home-minus-road gap into an edge on
one side of the league value, matching how the league edge is defined. Using home minus road,
not home alone, cancels the part of a residual that only means the team was under- or
over-rated all season. A team that beat its forecasts by 3 at home and missed by 1 on the road
gets $d = 2$.

**Reported:** the correlation across teams between $d_i$ averaged over odd seasons and over
even seasons, with a team-level bootstrap interval (2,000 draws, seed 20261018), for teams with
at least 3 home and 3 road games in both halves; and the method-of-moments estimate of the
between-team SD of the true edge, $\hat\tau$, below. A correlation whose interval includes 0,
or $\hat\tau^2 \le 0$, means per-team home edge is not detectable in our data, and Part 2 is
still run and reported but cannot be adopted.

## Part 2: the shrunk per-team model

**Candidate `team_eb`.** At each season $s$, team $i$'s edge comes from its raw $d$ over up to
the 4 previous seasons (2013 onward, 2020 skipped), shrunk toward 0 by empirical Bayes:

$$
\begin{gathered}
\delta_{is} = \frac{\hat\tau^2}{\hat\tau^2 + \mathrm{se}_{is}^2}\, \bar d_{is}, \qquad
\mathrm{se}_{is}^2 = \frac{\hat\sigma^2}{4}\left(\frac{1}{n^{h}_{is}} + \frac{1}{n^{a}_{is}}\right) \\[1em]
\begin{array}{rl}
\text{where}\quad \bar d_{is}: & \text{team } i\text{'s raw home edge pooled over its home and road games in the lookback, points} \\
n^{h}_{is},\ n^{a}_{is}: & \text{true home and road games in the lookback} \\
\hat\sigma: & \text{SD of one game's margin residual, from the lookback seasons, points} \\
\hat\tau^2: & \text{between-team variance of the true edge, method of moments on the lookback: } \mathrm{var}(\bar d) - \mathrm{mean}(\mathrm{se}^2)\text{, floored at 0, points}^2 \\
\delta_{is}: & \text{team } i\text{'s home edge on top of the league 2.4 in season } s \text{, points}
\end{array}
\end{gathered}
$$

The weight $\hat\tau^2 / (\hat\tau^2 + \mathrm{se}^2)$ runs from 0 to 1. With no between-team
signal ($\hat\tau^2 = 0$) every team gets $\delta = 0$ and `team_eb` is `ridge_h24`. A team with
few games gets a large $\mathrm{se}^2$ and is pulled almost all the way to 0. For example, with
$\hat\sigma = 14$, 24 home and 24 road games give $\mathrm{se} \approx 2.0$. If $\hat\tau = 1$, the
weight is 0.2, so a raw +5 becomes +1.

**Applying it.** The ridge fit is unchanged. At forecast time, a true home game adds
$\delta_{\text{home team}}/2$ to the home score and subtracts it from the away score, so the
margin moves by $\delta$ and the total is unchanged. Neutral sites and teams with no lookback
get 0. Everything is walk-forward: season $s$ uses only seasons before it.

**Nothing is tuned.** $\hat\tau$ and $\hat\sigma$ are estimated, not picked, and the 4-season
lookback and the shrinkage form are fixed here.

## Windows and the adopt rule

- **First look:** 2014–2019, each model's forecast SD fitted here on the baseline's 0.5-point
  grid (8–16), as in the home-edge record.
- **Check:** 2021–2025, SDs held fixed.
- **Adopt rule:** `team_eb` replaces `ridge_h24` in the weekly forecast only if (a) Part 1's
  split-half correlation interval is wholly above 0, and (b) its paired per-game CRPS difference
  against `ridge_h24` on 2021–2025 has a 95% interval wholly below 0. Otherwise `ridge_h24`
  stands and the review's "skip" is confirmed on our data.
- **Paired intervals:** season-week block bootstrap, 2,000 draws, seed 20261018.

## Reported

- Part 1: split-half correlation with interval, $\hat\tau$ by season, the number of teams
  qualifying, and the 10 largest and 10 smallest shrunk $\delta$ entering 2025.
- Part 2, per window: per-side MAE and CRPS, margin bias and MAE, paired CRPS and MAE against
  `ridge_h24`, and on 2021–25 lined games, per-side MAE against the Bovada open.

**Trial count:** 1 candidate, no tuned parameters, one SD per model on a 17-point grid.
2021–25 has been scored for this ridge family before, so the check is a repeat look.

## What it will not support

- A per-venue or per-stadium effect: the edge belongs to the team, and a team that moves
  stadiums keeps its history.
- Glicko's home edge, which bundle P3-C tests on its own holdout.
- A betting edge: the ridge trails the open by about 0.6 points per side.
- A null result is not proof that team edges are zero; it means they are too small to measure
  and use with 12 seasons of data.

Script (to build): `scripts/team_home_edge_eval.py`. Output:
`processed/ratings/team_home_edge.json`.

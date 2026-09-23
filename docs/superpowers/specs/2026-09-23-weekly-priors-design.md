# Previous-season priors for the weekly ratings — design

**Status:** approved design, 2026-09-23.
**Builds on:** Release B, [`docs/weekly-ratings-2026-09-23.md`](../../weekly-ratings-2026-09-23.md),
`scripts/weekly_ratings.py`, `scripts/weekly_ratings_eval.py`.
**Spec it implements:** [`research/totals/docs/totals-modeling-guide.md`](../../../research/totals/docs/totals-modeling-guide.md)
§7.4–7.5 and §13 step 4, restricted to inputs CFBD has.
**Review:** no Codex review. Its Windows sandbox fails at startup (error 206); see
`docs/superpowers/plans/2026-09-22-weekly-ratings-review-log.md`.

## Goal

Start each team's weekly ratings from a prior built on last season instead of from league
average, so early-season forecasts stop collapsing to the mean. Score the prior-centered
ratings (`prior_v1`) against Release B's `ridge_v1` on the same games, with week 1 now
forecast.

## Scope

In: carryover of last season's final ratings, an offensive returning-production
interaction, prior-centered ridge, week-1 forecasts, re-tuned λ.

Out: talent change (talent starts 2015 and the files hold final-roster values), the pace
switch on play-caller or head-coach change and its $\kappa$ term, per-team λ from prior
variance, a second lag, garbage-time filtering, bet grading of any kind.

## Priors

**Final ratings.** For each season $s-1$ in 2013–2024: Release B ridge at its tuned λ
(40 possessions, 8 games), fit on the whole regular season (FBS vs FBS, drive gate on).
This gives $O_{i,-1}$, $D_{i,-1}$, $P_{i,-1}$ and the final league levels $\mu$, $\nu$, $h$,
$c$.

$$
\begin{gathered}
O_{i,0}=\left(b+c\,\text{RP}_i\right)O_{i,-1},\qquad D_{i,0}=b_D\,D_{i,-1},\qquad P_{i,0}=a\,P_{i,-1} \\[1em]
\begin{array}{rl}
\text{where}\quad O_{i,0},\ D_{i,0},\ P_{i,0}: & \text{team } i\text{'s priors for season } s \text{ (points per possession; possessions per team per game)} \\
O_{i,-1},\ D_{i,-1},\ P_{i,-1}: & \text{team } i\text{'s final ridge ratings for season } s-1 \\
\text{RP}_i: & \text{offensive returning production, CFBD } \texttt{percentPPA}\text{, 0 to 1} \\
b,\ c: & \text{offense carryover with nothing returning, and extra carryover per unit of RP} \\
b_D,\ a: & \text{defense and pace carryover shares}
\end{array}
\end{gathered}
$$

Each prior is last season's rating scaled down toward average. A carryover share below 1
is regression to the mean applied before the season: part of last season's rating was
noise. $c>0$ means an offense that returns more of its production keeps more of its
rating. With $b=0.4$, $c=0.3$, an offense at $+0.80$ returning 70% of its production
starts at $(0.4+0.21)\times0.80=+0.49$ (illustrative). CFBD has no defensive returning
production, so defense and pace use a single share each.

- **Fit:** OLS with no intercept (ratings are centered), target = season $s$'s final
  rating, on the transitions 2014→2015 through 2018→2019. Team-clustered standard errors.
- **Centering:** each season's O, D and P priors are shifted to sum to 0, so the penalty
  never competes with $\mu$ or $\nu$ (guide §7.5, identification).
- **Missing inputs:** a team new to FBS has no prior rating, so its prior is 0; a team with
  no RP row gets the season's mean RP. Both are flagged per team (`prior_source`) and
  counted.
- **2021** uses the 2020 COVID season's final ratings as they are, reported per season.
- **As of:** season $s-1$ ended before season $s$ began. RP is `pregame_direct`
  (`docs/pregame-feature-eligibility-2026-09-16.md`), but the files were pulled in 2026;
  late-transfer revision is a named caveat.

## Weekly fit

`prior_v1` is Release B's ridge with each rating written as prior plus deviation,
$O_i=O_{i,0}+\delta_i$ (same for $D$, $P$): the prior-implied part is subtracted from the
target and $\delta$ is penalized toward 0. $\mu$, $h$, $\nu$ stay unpenalized. With no
games every rating equals its prior; as possessions accumulate the data moves it. In code,
`fit_ridge(games, lam_ppp, lam_pace, prior=None)`; `prior=None` is exactly `ridge_v1`.

- **Week 1:** ratings = priors; $\mu$, $\nu$, $h$, $c$ = last season's final values. The
  2023 clock rule will show as week-1 pace bias that season; reported, not corrected.
- **Week 2+:** as Release B, cutoff at the week's first kickoff.
- **λ re-tuned with priors**, on 2015–2019 including week 1, same component loss as B:
  $\lambda_{\text{PPP}}\in\{10,20,40,80,160,320,640\}$ possessions,
  $\lambda_{\text{pace}}\in\{1,2,4,8,16,32,64\}$ games; independent grids, 14 trials; a pick
  on a grid edge is flagged.
- **Snapshots:** method `prior_v1`, extra columns `O0`, `D0`, `P0`, `rp`, `prior_source`.

## Evaluation

Scored 2021–2025, λ and coefficients frozen. Forecasts on the same games: Bovada open,
train mean, `raw_v1`, `ridge_v1`, `prior_v1`.

| Population | Rule | Forecasts |
| --- | --- | --- |
| Week 1 | week-1 games with an open | `prior_v1`, mean, open |
| Early 2+ | week ≥ 2, a team with < 3 prior games, open present | all five |
| Primary | both teams ≥ 3 prior games, open present | all five |

**Declared verdicts** (`classify_verdict`, week-cluster bootstrap, 10,000 draws):

1. `prior_v1` − `ridge_v1` on **early 2+**.
2. `prior_v1` − `ridge_v1` on **primary**.

**Go** if (1) improves and (2) is not worse, both unchanged under all four stress variants
(λ ×0.5, ×2; prior coefficients ×0.5, ×1.5). Anything else is reported as it lands.

**Week 1 is reported, not gated.** Each season's week 1 is one cluster, so pooled week 1
has 5 clusters, too few for a bootstrap interval. It gets per-season differences
(`prior_v1` − mean, `prior_v1` − open) and a sign count.

Also reported: `prior_v1` − open per population, encompassing slope, bias per season, the
coefficients with SEs.

**Regression check:** the run recomputes `ridge_v1` and `raw_v1`; their pooled verdict
differences must equal Release B's recorded values to 4 decimals, or the run stops.

**Trial count:** 14 λ grid points, 4 prior coefficients, 1 method added, 4 stress variants,
on top of Release B's.

## Files

- `scripts/weekly_ratings.py`: `fit_ridge(..., prior=None)` only.
- `scripts/weekly_priors.py`: `final_ratings`, `load_rp`, `fit_carryover`,
  `build_priors`, `week1_ratings`.
- `scripts/weekly_ratings_eval.py`: prior tuning, `prior_v1` forecasts including week 1,
  new populations and verdicts, a `priors` block in the same manifest.

## Tests

`tests/test_weekly_priors.py`, in-memory:

1. Huge λ → ratings equal the centered priors; tiny λ on noiseless data → same recovery as
   `ridge_v1`.
2. `fit_carryover` recovers known $b$, $c$, $b_D$, $a$.
3. `build_priors`: centered sums 0; new-to-FBS 0; missing RP imputed; flags.
4. Leakage: changing a season-$s$ result leaves season $s$'s priors unchanged; the week-1
   snapshot holds no season-$s$ game.
5. Week-1 levels equal last season's final $\mu$, $\nu$, $h$, $c$.

## Docs

Dated finding doc in root `docs/` with a README row; guide §7 status, §13 step 4, §2 table.

## What this design does not claim

- No betting value; the open has no clock and no price.
- Talent, coaching and roster turnover beyond offensive RP are not modeled; a team that
  rebuilt its defense through the portal keeps last season's defense, scaled.
- Week 1 has no interval; its sign count is descriptive.

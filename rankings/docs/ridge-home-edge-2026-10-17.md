# ridge_v1's home edge is too big early in the season; holding it fixed fixes the bias

**Question.** `ridge_v1` over-forecasts home teams by about 1.7 points of margin
([baseline record](market-implied-score-baseline-2026-10-17.md)). Does holding its home edge
fixed, instead of refitting it each week, remove that bias and improve its score forecasts?

**Answer.** Yes. Both fixed versions remove most of the bias and beat `ridge_v1` on CRPS in
both windows. The declared pick, `fixed` (2.4 points), clears the adopt rule:
**−0.035 CRPS [−0.060, −0.010] on 2021–25**. `carry` (last season's fitted value) is
statistically tied with it and better calibrated on margin. Neither closes much of the gap to
the market: every variant still trails the Bovada open by about 0.6 points of MAE per side.

Spec, declared and committed before scoring:
[`specs/2026-10-17-ridge-home-edge-design.md`](specs/2026-10-17-ridge-home-edge-design.md).
Script: `python -m scripts.ridge_home_edge_eval` (writes `processed/ratings/ridge_home_edge.json`),
run 2026-10-17 at commit cf7441b.

## Method

Three versions of the weekly possession ridge, all with `ridge_v1`'s λ (40, 8), differing only
in the home term $h$ (points per possession):

- `free`: fitted each week, unpenalized. This is `ridge_v1` unchanged.
- `carry`: fixed at the previous season's end-of-regular-season `free` fit (2021 carries 2019).
- `fixed`: fixed at 2.4 points of margin, $h = 2.4 / (2\bar N)$.

Scored on completed FBS-vs-FBS games, regular season and postseason, week 1 skipped, as final
points per side (regulation forecast plus half the overtime constant). Each variant's forecast
SD was fitted on 2014–2019 (all came out at 12.5), and the pick was the lowest 2014–2019 CRPS.
2021–2025 is the check, with SDs held fixed. Paired intervals use a season-week block
bootstrap (2,000 draws, seed 20261017). Games: 4,355 (2014–19) and 3,702 (2021–25).

## Results

**Pick window, 2014–2019.** Mean per-game CRPS: `free` 7.1169, `carry` 7.0829, `fixed` 7.0811.
The pick is `fixed`, ahead of `carry` by 0.002, which is far inside the noise.

| 2021–2025 | CRPS vs `free` | MAE vs `free` | Margin bias | Margin MAE |
| --- | --- | --- | --- | --- |
| `free` | — | — | −2.07 | 13.66 |
| `carry` | −0.038 [−0.060, −0.018] | −0.041 [−0.076, −0.007] | +0.22 | 13.43 |
| `fixed` | −0.035 [−0.060, −0.010] | −0.031 [−0.074, +0.011] | +1.01 | 13.44 |

Margin bias is actual minus forecast home margin, so `free`'s −2.07 means it gives home teams
about 2 points too much. Every season from 2021 to 2025 favours both fixed variants on CRPS
(`fixed` by only −0.002 in 2024). In 2014–2019 the paired CRPS differences are −0.034
[−0.064, −0.005] for `carry` and −0.036 [−0.068, −0.004] for `fixed`.

**Where `free`'s bias sits.** Its margin bias by week (2021–25): weeks 2–4 −3.16, weeks 5–8
−3.09, week 9 on −1.16, postseason +0.06. 2014–19 shows the same shape (−3.42, −1.94, −0.93,
+1.23). The bias is largest when the fit has the fewest games and shrinks as the season fills
in. That fits the suspected cause: the team ratings are shrunk toward average while $h$ is not,
so early on $h$ absorbs part of the strength gap between better home teams and their visitors.
The fitted $h$ itself shows it directly. In 2014–2022 (2020 not scored), `free`'s home edge in points
of margin ($2h\bar N$) was **9.2–13.2 at week 2** (36–52 games in the fit), 4.8–9.0 at week 4,
and settled at **2.5–3.5 by the end of the regular season**. Every season decays the same way. The
end-of-season fits are 0.10–0.17 points per possession for 2013–2024.

**Totals are unchanged.** Total MAE is identical across variants (13.825 in 2014–19, 13.074 in
2021–25): the home term shifts one side up and the other down by the same amount.

**Against the market (2021–25, 3,685 games with a Bovada open).** Per-side MAE minus
`implied`: `free` +0.652 [0.498, 0.826], `carry` +0.612 [0.462, 0.787], `fixed` +0.622
[0.465, 0.805]. The open's margin bias is −0.09.

## Decision

Per the spec's adopt rule, `fixed` replaces the free home edge as the weekly ratings' home
term. It is the declared pick and its 2021–2025 interval is wholly below 0. This record does
not re-pick: `carry` scores the same within noise and is closer to unbiased on margin (+0.22
against +1.01), but switching to it after seeing 2021–25 would be choosing on the check
window.

## What it does not support

- **A betting edge.** Every variant trails the open by about 0.6 points of MAE per side.
- **That 2.4 is the true home edge.** `fixed` still leaves home teams about 1 point better
  than forecast, so this ridge's effective home edge is higher than 2.4. Only one value was
  tested, by design.
- **Anything about Glicko's home edge**, which bundle P3-C tests on its own sealed holdout.
- **A confirmed result.** `ridge_v1` had been scored on 2021–25 before, so the check is a
  repeat look, not a confirmation. Trial count: 3 variants, each with one SD on a 17-point grid.

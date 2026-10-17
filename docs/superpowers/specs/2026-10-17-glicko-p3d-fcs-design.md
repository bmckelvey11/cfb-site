# Glicko P3-D: shrink FBS-vs-FCS forecasts, declared before build — design

**Status:** declared 2026-10-17, before bundle D is built, tuned or scored. No Glicko work has
read a 2026 game kicking off after 2026-10-16, or any 2027 game.
**Why:** the diagnostics run recorded in
[`2026-10-16-glicko-p3-bundles-design.md`](2026-10-16-glicko-p3-bundles-design.md) found P1's
FBS-vs-FCS forecasts too extreme. Regressing the forecast miss on the forecast margin gives a
slope of −0.149 [−0.204, −0.096] over 1,252 games, 2014–2025, against −0.025 [−0.050, 0.000]
for FBS-vs-FBS. The bigger the predicted FBS win, the more it overshoots.
**Leaves alone:** `glicko_ratings.py`, `FROZEN_P1`, P1's sealed confirmation, and bundles A–C
(frozen 2026-10-17 in `scripts/glicko_p3_frozen.json`).

## Is it the FCS seed?

No. The FCS seed m₀ (−27.279) only sets the starting rating of an FCS team the first time the
pool sees it. After that the pool rates FCS teams from about 600 FCS-vs-FCS games a season. A
wrong seed would show as a constant miss, shared by every FBS-vs-FCS game. The same diagnostics
show the mean FBS-vs-FCS miss by season changing sign and mostly within noise: over 2014–2025
(2020 skipped) it ranges from −2.3 to +3.5 points, and only 2021 and 2025 clear zero, in
opposite directions. The finding is a slope, not an offset, so a different seed would not
remove it. Bundle D tests the slope directly.

## Bundle D

For a game between an FBS and an FCS team, P1's expected margin is replaced by a shrunk one:

$$
\begin{gathered}
\hat m_x = (1 - \lambda)\,\hat m, \qquad \hat m = r_h - r_a + H\,\mathbb{1}[\text{not neutral}] \\[1em]
\begin{array}{rl}
\text{where}\quad \hat m: & \text{P1's expected home margin, points} \\
\hat m_x: & \text{the cross-subdivision forecast used by bundle D, points} \\
\lambda: & \text{shrink fraction, unitless; } \lambda = 0 \text{ is P1} \\
r_h, r_a: & \text{home and away ratings, points vs an average FBS team} \\
H: & \text{home edge, points (P1: 2)}
\end{array}
\end{gathered}
$$

With λ = 0.15, a game P1 would forecast as a 30-point FBS win is forecast as 25.5. The shrunk
mean is used for the forecast and for the update. The innovation is margin − $\hat m_x$; the
Kalman gains and variances are P1's unchanged. FBS-vs-FBS and FCS-vs-FCS games are unchanged.
The forecast SD is P1's, $\sqrt{u_h^2 + u_a^2 + \sigma_{pred}^2}$.

- **Grid (2014–2019 only):** λ ∈ {0, 0.05, 0.10, 0.15, 0.20, 0.25}, tuned jointly with σ_pred on
  11.0–16.0 in steps of 0.5. Everything else is P1's.
- **Selection:** lowest mean CRPS on FBS-vs-FCS regular-season games, 2014–2019 (2013 burn-in).
- **Built as** a new class in `scripts/glicko_p3.py`. λ = 0 reproduces P1 exactly.
- **Its own frozen file** `scripts/glicko_p3d_frozen.json` and its own
  `scripts/glicko_p3d_eval.py` with `--freeze` and `--look interim|final`. The freeze reads no
  game after 2025.
- **Descriptive 2021–2025 report** (decides nothing): D minus P1 (σ_pred 13.5) paired CRPS and
  MAE on FBS-vs-FCS and on FBS-vs-FBS games, plus the FBS-vs-FCS residual slope (diagnostic D1)
  under P1 and under D.

## Holdout and looks

- **Holdout:** completed games kicking off after 2026-10-17T12:00Z, before that day's first
  kickoff, through the end of the 2027 postseason. Scored on FBS-vs-FCS games and on
  FBS-vs-FBS games.
- **Interim look** after the 2026 postseason, not before 2027-01-20: recorded, labelled interim,
  nothing adopted.
- **Final look** after the 2027 postseason, not before 2028-01-20, read once.
- **Comparison:** D minus P1 with σ_pred 13.5, paired CRPS and MAE, season-week block bootstrap,
  10,000 draws, seed 20261017.
- **Adopt D** if its FBS-vs-FCS paired CRPS interval is below 0 **and** the lower bound of its
  FBS-vs-FBS paired CRPS interval is ≤ 0.

About 120 FBS-vs-FCS games are played a season, and few after mid-October, so the interim look
will be noisy and the final verdict rests mostly on 2027.

## Trial accounting

6 λ values × 11 σ_pred values = 66 fits, added to the family's count (21,625 before this spec).

## What this does not support

- No betting claim.
- It does not test an FCS-wide offset tracked as its own state, which would shift every FCS team
  rather than shrink large gaps.

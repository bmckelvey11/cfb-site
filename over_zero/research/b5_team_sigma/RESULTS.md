# B5.1: Team-σ walk-forward comparison — Results

## Command

```
python research/b5_team_sigma/team_sigma.py
```

## Output (verbatim)

```
K=30: mean OOS logloss improvement (pooled - team) = -1.38 x1e-4  season-block bootstrap 95% [-2.76,-0.11] x1e-4  (10,255 games)
K=15: mean OOS logloss improvement (pooled - team) = -2.02 x1e-4  season-block bootstrap 95% [-3.75,-0.34] x1e-4  (10,255 games)
K=60: mean OOS logloss improvement (pooled - team) = -0.87 x1e-4  season-block bootstrap 95% [-1.99,+0.04] x1e-4  (10,255 games)

VERDICT (K=30): TEAM-SIGMA HURTS OOS
```

## Checklist

1. **CI excludes 0 at K=30?** Yes — 95% CI is [-2.76, -0.11] x1e-4, entirely below 0. This means the improvement (pooled minus team) is significantly *negative*: team-σ is significantly *worse* than pooled-σ out of sample, not better.
2. **Same sign across K=15/60?** Yes for the point estimates — all three K values (15, 30, 60) give a negative mean improvement (-2.02, -1.38, -0.87 x1e-4), i.e. team-σ underperforms pooled-σ at every shrinkage level tested. Note the K=60 CI is [-1.99, +0.04] x1e-4, which straddles zero — so at the weakest shrinkage (largest K, most pooling toward the pooled estimate) the direction is consistent but not statistically significant.
3. **Verdict:** TEAM-SIGMA HURTS OOS (K=30, primary).

**Scope of this result:** this comparison is not a from-scratch team-sigma probit — both arms use the SAME probit, fit and calibrated on pooled-sigma bias (`probit = probit_win_v2(...)` fit once on `bias_tr`, computed from the pooled `s1, s2` sigmas, then reused by `season_logloss` for both the pooled arm and the team arm); the team arm substitutes team-sigma bias through that pooled-calibrated link function. A calibration mismatch from the shifted regressor distribution can alone produce a log-loss gap independent of whether team-level sigma heterogeneity carries real predictive information. Team variances are also shrunk toward the pooled Tobit sigma (fit on ALL games, including censored ones) while the team-level variance itself is estimated only on UNCENSORED games — a one-sided bias making team sigma look smaller/more different from its own shrinkage target than a symmetric comparison would show. The correct verdict given what was actually tested is: **team-σ substituted into a pooled-σ-calibrated probit hurts OOS log-loss** — not an unqualified "team-sigma is worse than pooled-sigma." A fair test would refit the probit on team-sigma bias within the team arm; that has not been done here. This single-probit structure is a design property of the plan's original B5.1 task spec (`docs/superpowers/plans/2026-07-30-research-track-b.md`, Task B5.1 driver pseudocode), not an implementation defect — flagging it here so the result isn't over-read.

Because the result is not an improvement, the prespecified follow-up note (rerun the BET simulation) is not added — the brief gates that note on an improved result, which this is not.

## Caveat

Team σ estimated on uncensored games only (mild truncation); shrinkage constant K is games-count prior weight, K=30 ≈ 2.5 seasons.

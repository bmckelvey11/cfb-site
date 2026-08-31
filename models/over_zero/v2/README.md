# v2 — tightening two caveats

v1 (frozen in `../v1/`) reproduced Arscott (2022). v2 stress-tests its two
methodological caveats. **Both turn out to be harmless on this data** — v1's
results stand — but v2 proves it rather than asserting it.

```bash
python v2/run_v2.py                       # pooled 2013–2025
python v2/run_v2.py --season 2024 2025     # subset
```

Files: `models_v2.py` (analytic-SE Tobit, statsmodels probit, correlation +
bivariate MC), `run_v2.py` (driver).

---

## Caveat A — analytic standard errors vs BFGS inverse-Hessian

v1 took SEs from the BFGS optimizer's inverse-Hessian approximation. v2 derives
the **analytic score** of the Tobit log-likelihood and forms the covariance from
the **outer product of gradients (OPG / BHHH)** — an analytic information-matrix
estimator. The probit moves to statsmodels (analytic observed-information SEs).

Analytic Tobit score, params `[α, β, log σ]`, `μ = α + βx`:

| | uncensored (y>0), z=(y−μ)/σ | censored (y=0), a=μ/σ, λ=φ(a)/Φ(−a) |
|--|--|--|
| ∂ℓ/∂μ | z/σ | −λ/σ |
| ∂ℓ/∂log σ | z²−1 | a·λ |

(`∂ℓ/∂α = ∂ℓ/∂μ`, `∂ℓ/∂β = ∂ℓ/∂μ·x`.) The optimizer used this exact gradient
and converged to the same σ as v1 (11.03 / 11.77), validating the derivation.

**Result (pooled 2013–2025):**

| Param | OPG (analytic) SE | BFGS SE (v1) |
|-------|-------------------|--------------|
| Tobit dog α | 0.391 | 0.364 |
| Tobit dog β | 0.0173 | 0.0167 |
| Tobit fav α | 0.537 | 0.525 |
| Tobit fav β | 0.0154 | 0.0152 |

SEs agree to within ~7%; OPG is marginally larger (more conservative), as
expected. Probit slope **+0.176, analytic SE 0.028, p = 5.9e−10**. **Verdict:
v1's "fine for inference here" was correct** — no qualitative conclusion changes.

---

## Caveat B — dropping independence cov(δ₁, δ₂) = 0

v1 assumed favorite and underdog score errors are uncorrelated. v2 estimates the
correlation and propagates it through a censored **bivariate-normal** score model
(Monte-Carlo, common random numbers, zero-meaned draws).

**Estimated correlation: ρ = +0.067** (Pearson, on 11,976 both-uncensored games).
Small and positive.

### B1 — `biasTotals` is invariant to ρ (proved)

The expected censoring bias is a **marginal** expectation, `E[max(0,x)] − μ`,
which by linearity of expectation is independent of the joint correlation. MC
confirms (mean over 2,000 games):

| Quantity | Value |
|----------|-------|
| analytic `biasTotals` (ρ-free formula) | 0.2028 |
| MC E[trueTotals]−totalsEst, ρ = 0 | 0.1909 |
| MC E[trueTotals]−totalsEst, ρ = +0.07 | 0.1911 |

ρ = 0 and ρ = 0.067 give the **same** expected bias (0.1909 vs 0.1911; the gap
to the analytic 0.2028 is MC sampling noise). So the trading signal itself is
untouched by the independence assumption.

### B2 — win probability barely moves

ρ only reshapes the *variance* of the totals error, so it can shift P(over | bias).
Theoretical P(over) under independent vs correlated, binned by bias, vs the
empirical realized over-rate:

| bias bin | N | empirical | probit | theory ρ=0 | theory ρ=0.067 |
|----------|---|-----------|--------|------------|----------------|
| (−1.0, 0.25] | 1518 | 0.470 | 0.477 | 0.502 | 0.502 |
| (0.25, 0.50] | 271 | 0.535 | 0.496 | 0.504 | 0.504 |
| (0.50, 1.00] | 133 | 0.526 | 0.518 | 0.509 | 0.508 |
| (1.00, 1.75] | 47 | 0.511 | 0.559 | 0.523 | 0.520 |

ρ = 0 and ρ = 0.067 columns are identical to ≤0.003. **Verdict: at the observed
correlation the independence assumption is harmless.** Why v1 was safe even in
principle: its probit is fit on *realized* over/under outcomes, which already
embed the true correlation — independence only ever entered the *theoretical*
derivation, not the empirical edge.

### Bonus finding

Pure-censoring **theory** predicts a flatter bias→P(over) slope (0.502 → 0.523
across bins) than the **empirical** probit (0.477 → 0.559). Censoring explains
the *direction* of the edge, but the realized edge is somewhat *larger* than
censoring alone accounts for — hinting at additional bias correlated with
high-censoring (low-total, lopsided) games. Worth a v3.

---

## Net

Both caveats checked, both immaterial on 2013–2025 CFBD data. v1's strategy
(bet over when expected censoring bias > 1.0) is unchanged: 680 bets, 56.62%,
probit slope significant at p ≈ 1e−9 with analytic SEs. The independence
assumption is safe because ρ ≈ 0.07 and because the edge is estimated
empirically, not from the theoretical joint distribution.

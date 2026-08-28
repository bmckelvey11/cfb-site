# Saturation Bias model — the ceiling-side analog (NEGATIVE RESULT)

The question: does Arscott's censoring theory extend to the **under**? His edge
comes from the **floor** (points can't go below 0 → totals biased up → over).
This model builds the structural **mirror**: a soft scoring **ceiling** from
finite drives/clock (points saturate at some C → totals biased down → under),
motivated by the v3 exploration where totals lines > 66 went under ~54%.

```bash
python saturation_bias/run_saturation.py
```

`saturation.py` (ceiling-bias math, C selection, OOS under strategy),
`run_saturation.py` (driver). Shared core imported from `../v2`.

## The model

Each team's points are right-saturated: `observed = min(C, latent)`,
`latent ~ N(teamEst, σ²)`. The expected bias mirrors the floor case:

```
saturationBiasTeam = E[min(C,X)] − μ = −[σ·φ(d/σ) − d·Φ(−d/σ)],   d = C − μ
saturationBiasTotals = −(satBias_fav + satBias_dog)   ≥ 0  (downward-bias magnitude)
```

It only bites when expected points μ are within ~1–2σ of the ceiling C — i.e.
high-scoring teams / high totals lines.

**Why this is weaker than the paper, by construction:** the floor at 0 is
*observed* — real games pile up at 0 points, so a left-censored Tobit identifies
it. There is **no pile-up at any scoring ceiling** (no team maxes out), so C is
not identified by the score distribution. C must be chosen by predictive fit.

## Result: no under edge exists

### 1. Ceiling C is not identified — OOS log-loss is flat

| C (per team) | OOS log-loss |
|--------------|--------------|
| 38 | 0.69305 |
| 46 | 0.69296 |
| **50** | **0.69295** |
| 58 | 0.69298 |
| 66 | 0.69306 |

The "best" C=50 beats the worst by 0.00015 — noise. No ceiling is meaningfully
identified. (log-loss ≈ ln 2 = 0.693 everywhere = near-coin-flip.)

### 2. The probit slope points the WRONG way

`P(under) = Φ(const + slope·saturationBias)` → **slope = −0.031 (p=0.006)**.
Negative: more saturation bias → *less* likely to go under. In-sample quartiles:

| saturation-bias quartile | under-win% |
|--------------------------|-----------|
| lowest | 51.39% |
| 2nd | 51.64% |
| 3rd | 50.84% |
| highest | **49.89%** |

The highest-saturation (highest-scoring) games go under *less*, not more — the
opposite of the hypothesis.

### 3. No out-of-sample under strategy

Betting the under where predicted P(under) > 52.38%: across 5 folds, only **6
bets** ever cleared the hurdle (33% win). The model essentially never finds a
profitable under — because the relationship is weak and the wrong sign.

## Verdict

**The censoring theory does NOT extend to the under.** The asymmetry is real both
ways:

- *Mathematically*: left-censoring at a known floor is one-directional; it can
  only bias totals up.
- *Empirically*: the ceiling mirror has no predictive power, C is unidentified,
  and the fitted relationship runs the wrong way.

The v3 hint (totals > 66 → 54% under) does **not** survive proper modeling — it
was a small-N, non-monotone in-sample artifact. The over edge from floor
censoring is genuine and robust (v1–v3); a symmetric under edge from ceiling
saturation is not there. If an under edge exists, it needs a mechanism *outside*
the two betting lines (pace, weather, specific offenses) — a different study with
different data, not an extension of this theory.

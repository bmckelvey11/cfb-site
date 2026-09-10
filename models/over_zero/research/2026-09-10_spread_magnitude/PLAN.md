# Analysis plan — edge by spread and total level

Pre-committed before fitting. Written after [`RESULTS.md`](RESULTS.md) (the >50
record) raised the question, and before any 2D estimate exists. Graded against by
[`RESULTS-2D.md`](RESULTS-2D.md).

## 1. Estimand

**Primary.** The market's total mispricing surface: `E[total_err | spread, total]`
where `total_err = actual_total − posted_total`, over FBS games priced by the
consensus line, seasons 2016–2025. This is the quantity a bet on the over
collects; zero means the market is right.

**Secondary (mechanism).** The same expectation split into legs —
`fav_err = fav_pts − fav_implied` and `dog_err = dog_pts − dog_implied`, using
`implied_team_points`, the model's own split of the spread/total pair. Descriptive
only; the surface is the decision input.

**Decision estimand.** Whether a rule of the form "bet the over when bias > 1.75
**and** (spread, total) is in region R" beats the unrestricted rule
out-of-sample. R is a candidate, not an estimand — see §5, §7.

## 2. Model specification

One pre-registered form, fit on **all 10,255 graded games**, not on the 234 bets:

```
total_err ~ spread + total + spread:total
```

plus a natural-cubic-spline variant in `spread` (df=4) as the one pre-declared
alternative, because the mechanism under test (favorite censored from above at
extreme mismatches) is explicitly nonlinear and a linear term cannot express it.
Two specs, both declared here. No further form search; no bin hunting.

Controls deliberately excluded: `bias` (a deterministic function of spread and
total — including it is the same regressor twice), season fixed effects (the
dependence is handled in the SE, §3; the estimand is pooled across seasons).

**Why all games and not the bets.** Inside the bet set, `bias = f(spread, total)`
and the 1.75 gate is a level curve of it, so spread and total are collinear **by
construction**: the observed crosstab is near-diagonal — 27 bets at spread ≤ 35 all
sit at total ≤ 50, all 13 bets at total > 63 sit at spread > 50, and the
off-diagonal cells are empty. Two separate effects are **not identified on the bet
sample**. The gate does not restrict the full sample, which has support across the
whole rectangle, so the surface is estimable there.

**The claim this buys, and the one it does not.** The surface says where the
*market* misprices totals. It does not say what *the model's record* is in a
region, because outside the gate the model does not bet. Surface → where a gate
should run; record → descriptive, never the decision.

## 3. Dependence structure

Games are not iid. Named dependence: **season** — total-setting conventions and
scoring environment shift year to year, and the sample is back-loaded (2022+ is
68% of games). Cluster at the season level.

10 clusters is **few**, so cluster-robust SEs are anti-conservative and the
**wild cluster bootstrap** (Rademacher, 9,999 reps) is the reported inference, not
an optional extra. Asymptotic clustered SEs reported alongside for contrast only.

Within-season team repetition is a second dependence channel, unhandled and
stated: a team appears ~12 times a season. Season clusters absorb it only for
same-season pairs. Treated as ignorable for the *pooled mean surface*; it would
not be ignorable for a team-level claim, and no team-level claim is made.

## 4. Primary metric + benchmark

Primary: mean `total_err` with a wild-bootstrap 95% CI, by region.

Benchmark: **the market**, i.e. `total_err = 0`. Not the base rate. The
decision-relevant threshold is not zero but the vig: at −110 an over needs
+0 points of edge to break even *in expectation on the number*, but the
operational rule prices at −120 or better, so the surface must clear the spread of
the price, reported explicitly rather than implied.

Secondary, descriptive: hit rate and ROI by region on the 234 bets.

## 5. Multiplicity budget

- **Two specs** (linear, spline). Declared here, both reported. No selection of
  the better one for the headline.
- **Zero bin searches.** Regions reported are fixed in advance at the spread
  bands already used in `RESULTS.md` (30–40, 40–50, >50) and total terciles of the
  full sample. They are for reading the fitted surface, not for finding a cell.
- **Any candidate rule R is confirmed out-of-sample (§7), not corrected.**
  Held-out confirmation is preferred to BH/Holm here because a single rule is
  being decided, not a family of features ranked.
- The >50 finding that motivated this is itself post-hoc. It is carried as a
  hypothesis to be confirmed, and is not re-tested on the same 234 bets.
  Re-cutting at 45 shows sensitivity, **not** confirmation.

## 6. Pre-run power / MDE

`sd(total_err) = 16.3` points. MDE at α=0.05, power=0.80 is `2.8 × SE`:

| sample | N | SE | MDE (points of total error) |
|---|---:|---:|---:|
| all graded games | 10,255 | 0.16 | **0.45** |
| spread 30–40, all games | 569 | 0.68 | 1.91 |
| spread 40–45, all games | 126 | 1.45 | 4.06 |
| spread 45–50, all games | 78 | 1.85 | 5.17 |
| **spread >50, all games** | **41** | **2.54** | **7.13** |
| the 234 bets | 234 | 1.07 | 2.98 |
| >50 bets | 38 | 2.64 | 7.40 |

Hit-rate MDE against break-even 52.38%: **9.1pp** at n=234, **22.7pp** at n=38.

**Stated before fitting: the >50 cell is power-dead and cannot be widened.** 41
games is the entire ten-season population at that spread, not a subsample. Its MDE
(7.1 points) exceeds the anomaly that prompted the question (~5 points). Per the
skill's interpretation rule, a null there is **not** evidence of absence, and a
"significant" result there would more likely be noise than signal. The surface fit
is the only route to a usable statement about that region, and it works by
borrowing strength from the smooth — which is an assumption, not a measurement.

The full-sample surface is well powered (MDE 0.45 points). The recommendation must
rest on it, or on nothing.

## 7. Stop rule / evaluation window

Fixed now: seasons **2016–2025**, every graded game, one look. No re-cut after
seeing results, no extension to a new season mid-analysis.

Any candidate rule R is graded by **walk-forward**: for season *t*, R's parameters
are fit on seasons < *t* only, then season *t* is graded; results pooled over *t*.
This is the same protocol that produced the 234 bets. A rule whose walk-forward
version does not beat the unrestricted rule **is not adopted**, regardless of how
its in-sample region looks. In-sample region selection is exactly what inflates
the 1.75 threshold's own estimate, which `MODEL_GUIDE.md` §3 already concedes.

## 8. Identification status

**Predictive / conditional association.** No causal design, none claimed. The
mechanism language ("the favorite is censored from above") is a *hypothesis
consistent with* the leg decomposition, not an identified effect. Spread magnitude
is confounded with mismatch class (FBS-vs-FCS), roster depth, and benching
convention; it is used as a pre-game **proxy**, and the write-up must say so.

The one thing that would upgrade this: a design separating spread magnitude from
FBS-vs-FCS status — graded on all games, where both vary. Out of scope here,
flagged as the follow-up.

---
Written 2026-09-10, before fitting. Data: `docs/backtest_bets.csv`
(`monitor/roi_report.py`), 10,255 graded games, 234 at `passes_filter == 1`.

# Massey rankings against the opener, and every Massey system against the market — 2026-09-30

**EXPLORATORY.** This follows up [`fair-oster-massey-replication-2026-09-30.md`](fair-oster-massey-replication-2026-09-30.md),
which found that the paper's nine systems add nothing to the closing line. Two questions:

1. Do rankings carry information that the **opening** line lacks, and do they predict where the
   line moves by close?
2. Does **any** of the ~170 other Massey systems add information that the market lacks?

**Answer.**
1. **Against the close: no system adds anything out of sample.** That holds for all 172 systems,
   including the composite. 14 pass Benjamini–Hochberg in-sample, but none of those that can be
   checked out of sample beats the close, except one single season that is chance.
2. **Against Bovada's opener: some in-sample information, no proven gain.**
   - Predictive systems carry in-sample information (Dokter Entropy, Kelly Ford, FPI,
     TeamRankings: Holm p < .05).
   - Out of sample, none improves on the opener with an interval that excludes zero.
   - The ranking model predicts none of Bovada's open-to-close move (R² −0.006).
3. **DraftKings' opener moves toward the rankings, but mostly because it converges to the other
   books.**
   - Out of sample, the ranking gap anticipates 15% of DK's move (R² 0.153 [0.10, 0.19], 2024–25).
   - About 60% of that coefficient disappears once DK's gap to Bovada's opener is controlled for.
     What remains is small and was found post hoc.
   - What this supports is a line-shopping observation (DK's early number is soft relative to
     other books), not a ranking signal.
4. **No opener result is bettable as shown.** The openers have no timestamps before 2026. In
   2026, 48% of CFBD's DraftKings opens were look-ahead lines posted before the previous weekend.
   Every opener number here is an upper bound. No ATS or ROI at the opener is computed: a price
   that cannot be placed at decision time is a hard gate under
   [`model-evaluation-standard.md`](model-evaluation-standard.md).

Reproduce: `python scripts/massey_market_tests.py`, which writes
`$CFB_DATA_ROOT/processed/massey_market_tests.json`. The pre-specification is in the script
docstring.

---

## Data and method

- **Sample.** The replication's sample: FBS vs FBS, regular season, week ≥ 6. The latest Massey
  edition before the game's Eastern date. The same orientation flip, rank gaps
  $Q = 100\,(R_{away} - R_{home})/N$, and weeks clustered by edition.
- **Lines.** Per book from `core.fact_game_line`.
  - Opens exist only for 2021–2025, for three books: Bovada (2021–25, primary), DraftKings
    (2023–25) and ESPN Bet (2024–25).
  - Closes use the per-game median across books (the "close" family), or the same book's close
    (the movement tests).
- **Timing of the open.** For 2026, Action Network ticks give the time each DraftKings line first
  appeared. Matching CFBD's DK open to those ticks puts 48.2% of 309 matched games' opens before
  the previous Sunday: posted Wednesday–Friday, before the previous weekend's games. The rest
  were posted that Sunday, with a median hour of noon.
  - Bovada and ESPN Bet have no ticks.
  - Massey editions are dated Sunday or Monday. So even a Sunday opener is at best simultaneous
    with the rankings.
- **Pre-specified tests** (script docstring, committed with the results):
  - **A (timing):** open-to-close move on last week's result surprise.
  - **O1:** encompassing against the opener.
  - **O2:** walk-forward movement.
  - **O3:** movement with a surprise control.
  - **S1 / S2:** scans against the close and against Bovada's opener.
  - **Post-hoc, added after run 2 was read:** O4, the DraftKings controls.
- **Trials.** Three runs. Run 1 was aborted before any output was seen. Run 2 fit 337
  regressions. Run 3 added O4's 5 regressions: 342 in total.

The movement metric is the one `research/spread` uses:

$$
\begin{gathered}
R^2_{move} = 1 - \frac{\sum_g \left(M_g - \gamma\, \text{gap}_g\right)^2}{\sum_g M_g^2} \\[1em]
\begin{array}{rl}
\text{where}\quad g: & \text{one game in a test season} \\
M_g = LV^{close}_g - LV^{open}_g: & \text{the book's open-to-close move, points, in the expected-margin scale} \\
\text{gap}_g = \hat{Y}^{rank}_g - LV^{open}_g: & \text{ranking model's margin minus the opener; } \hat{Y}^{rank} \text{ fit on 2013 to } s-1 \\
\gamma: & \text{share of the gap the line closes, fit on opener seasons before } s
\end{array}
\end{gathered}
$$

A line that never moves scores 0. A score of 0.15 means the ranking gap, scaled by $\gamma$,
accounts for 15% of the squared movement. A negative score means the prediction does worse
than assuming no move. Example: $\gamma = 0.34$ and a 3-point gap predict the line moves 1 point
toward the rankings.

## A — which openers are stale

| Book | Seasons | n | Move on last-week surprise | t (clustered) | R² of move |
| --- | --- | --- | --- | --- | --- |
| Bovada | 2021–25 | 2,425 | 0.011 | 5.3 | .012 |
| DraftKings | 2023–25 | 1,465 | 0.031 | 5.7 | .045 |
| ESPN Bet | 2024–25 | 1,014 | 0.012 | 2.3 | .010 |
| DK 2026, look-ahead opens | wk 2–5 | 71 | 0.112 | 8.0 | .476 |
| DK 2026, Sunday opens | wk 2–5 | 113 | 0.028 | 3.4 | .093 |

- DraftKings' 2023–25 opens load on last week's surprise about as much as its 2026 Sunday opens
  do, not as much as its look-ahead opens. That is suggestive only: the 2026 calibration comes
  from weeks 2–5, where lines react more to results.
- Bovada's open reacts the least. It behaves like the latest-posted, sharpest of the three.

## O1–O3 — rankings against each book's opener

| Book | O1 F(core = 0 given open), clustered p | Same given that book's close | O2 walk-forward R² of move [95% CI] | direction right | O3 in-sample γ (t; MDE) |
| --- | --- | --- | --- | --- | --- |
| Bovada | .086 (SAG .127, t 2.4) | .56 | −0.006 [−0.035, 0.010], 2022–25, n 1,959 | 51.1% | 0.104 (1.8; 0.165) |
| DraftKings | < .001 (SAG .273, t 5.1) | .22 | **0.153 [0.101, 0.192]**, 2024–25, n 988 | 59.4% | 0.340 (8.4; 0.114) |
| ESPN Bet | .24 | .29 | −0.002, 2025 only, n 511 | 54.7% | 0.176 (2.9; 0.168) |

- The core is SAG, BIL, COL, MAS, DUN and REC, as in the replication.
- Adding last week's surprise (O3) leaves each book's γ within 0.02.
- **Bovada.** A γ above about 0.17 can be ruled out (the MDE), and DK's 0.34 is well above that.
  Rankings anticipate little or none of Bovada's move.
- **Comparison with Prediction Tracker.** DraftKings' 0.153 is the same order of magnitude as
  the Prediction Tracker panel's movement result in
  [`line-movement-results.md`](../research/spread/docs/line-movement-results.md). The book,
  seasons, anchor and sample size all differ, so the two numbers are not directly comparable.

### O4 (post-hoc) — what DraftKings' gap stands in for

The O4 table uses DraftKings, 2023–25, n = 1,464: the games that also have a Bovada open.

| Model for DK's move | gap coef (t) | Control coefs (t) | R² of move |
| --- | --- | --- | --- |
| gap alone | 0.340 (8.4) | — | .196 |
| + Bovada open − DK open | **0.141 (2.3)** | book gap 0.686 (3.6) | .528 |
| + change in composite gap since last edition | 0.329 (8.3) | 0.049 (5.4) | .209 |
| + home | 0.339 (8.4) | −0.10 (−1.3) | .197 |
| all three | 0.135 (2.3) | book gap 0.684 (3.6); news 0.022 (2.0); home −0.21 (−3.2) | .535 |

- **Converging to the other books explains most of it.** DraftKings closes about 69% of its gap
  to Bovada's opener, and that takes more than half the ranking coefficient with it.
- **The rest is weak.** News since the last edition and home field each explain little. The
  ranking gap left over, 0.14 with t 2.3, is one post-hoc regression among 342. It is not a
  finding.

## S1 / S2 — every eligible Massey system, one at a time

- **Eligibility.** A system is eligible if it has a median of at least 100 teams ranked per
  edition over 2013–25. That removes the top-25 polls and leaves 213 systems. CMP (the composite)
  and REC are added.
- **Sample size.** A system enters a family with at least 500 games (S1) or 300 (S2).
- **The test.** Each system gets $Y = \lambda\, LV + \alpha H + \beta_k Q_k$, with BH at q = .10
  on clustered p.
- **The survivor check.** Walk forward by season: fit on earlier seasons, then compare
  out-of-sample MSE with the raw line. The interval comes from resampling whole weekly editions.

| Family | Systems | BH rejects | Holm p < .05 | Survivors whose out-of-sample ΔMSE CI lies below 0 |
| --- | --- | --- | --- | --- |
| S1: given the median close, 2013–25 | 172 | 14 | 2 (PiRate, CPA) | 1 of 12 checkable: Real Time RPI, 2015 only, 448 games |
| S2: given Bovada's open, 2021–25 | 123 | 11 | 4 (Dokter Entropy, Kelly Ford, FPI, TeamRankings Pred) | 0 of 9 checkable |

**S1 reading.**
- The in-sample coefficients are small and positive (0.05–0.14 per percentile point), and every
  system is a proxy for the same strength gap. Read them as one small common tilt, not 14
  findings.
- The composite does not carry it: CMP 0.021, t 1.5.
- Out of sample, the long-coverage survivors do slightly worse than the close:
  - PiRate: ΔMSE +0.98 [−0.24, +2.16] over 2015–25.
  - Dokter Entropy: +0.80 [−0.44, +2.03].
- Real Time RPI's one significant season is 1 check in 12, on 448 games: chance.
- **Paper's nine:** none passes BH; the best is AND at q = .115.

**S2 reading.**
- Against Bovada's opener, the systems that pass are rating-based predictive systems.

  | System | coef | t | out-of-sample ΔMSE, 2023–25 [95% CI] |
  | --- | --- | --- | --- |
  | Dokter Entropy | .115 | 5.2 | −0.61 [−2.65, +1.41] |
  | Kelly Ford | .107 | 4.6 | −0.52 [−2.39, +1.17] |
  | FPI | .099 | 3.9 | −0.28 [−2.31, +1.45] |
  | TeamRankings Pred | .092 | 3.7 | −0.24 [−1.89, +1.34] |
  | Sagarin (SAG) | .090 | 3.1 | +0.16 [−1.67, +2.01] |

- The out-of-sample direction is right for four of the five, and the coefficient is positive in
  every season for DOK and KFD.
- The intervals are about ±2 points² on about 1,500 games. So a gain smaller than about
  2.8 points², roughly 1% of the opener's MSE, cannot be detected.
- S&P+ is significantly worse out of sample: +1.66 [+0.20, +3.16].
- The honest summary is **not established out of sample**, rather than "no information". The
  survivor check also refits the anchor's slope, which adds variance against a very small
  increment.

**Standalone, no market.** On the common 2,425-game opener sample, each system's rank-only fit
has this RMSE above Bovada's opener:

| System | RMSE above opener |
| --- | --- |
| Dokter Entropy | 0.284 |
| Kelly Ford | 0.286 |
| Sagarin | 0.327 |
| FPI | 0.338 |
| TeamRankings | 0.343 |

For a spread with no market, DOK and KFD are as good as Sagarin or marginally better. These
are rank-based inputs; each system's own ratings would likely do better than its rank.

## What this does not support

- **No bet at any opener.** There are no decision-time timestamps before 2026, and roughly half
  of DraftKings' 2026 opens predate the previous weekend's games. No ATS or ROI is claimed.
- **Not a ranking edge at DraftKings.** DK's open-to-close movement is mostly DK converging to
  other books. The only route from here to a bet is a timestamped forward log, which is outside
  this record: record DK's Sunday open and the other books' opens at capture time, and grade on
  CLV to DK's close. That is book-divergence work, which belongs with
  `research/spread/docs/prereg-line-shopping.md`.
- **Not "these systems have no information".** Most scan results are out-of-sample nulls from
  three test seasons, with a detection floor near 1% of MSE.
- **Not a ranking of the systems' real forecasts.** Every input is a Massey rank converted to a
  percentile gap, not a system's rating or point prediction.
- **Post-hoc numbers are not results.** O4 and any single system's coefficient chosen from the
  scan are exploratory, on 342 regressions.

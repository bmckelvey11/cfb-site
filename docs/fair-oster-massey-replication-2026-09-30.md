# Fair & Oster (2005) replicated on the Massey composite — 2026-09-30

**Question.** Fair and Oster ("College Football Rankings and Market Efficiency", Cowles
Foundation DP 1381, 2002 rev. 2005) found three things for 1998–2001:

1. Several BCS computer rankings carry independent information about game margins, some of it
   with a negative weight.
2. A weighted combination beats every single system.
3. Once the closing Las Vegas spread is added, none of the rankings add anything.

Do the same three results hold when the rankings come from our Massey composite archive?
We ask this for the paper's window and for 2013–2025, where we have closing lines.

**Answer.**
- **Result 1 replicates in both eras.** Sagarin dominates. Massey adds nothing once the others
  are in. One system carries a significant negative weight: Anderson (the paper's SEA) in
  1998–2001, and Colley (COL) in 2013–25.
- **Result 3 replicates.** F(others = 0 | close) = 0.97, p = .42, against the paper's 0.96.
  The close's coefficient is 0.95–1.01, not different from 1.
- **Result 2 does not survive out of sample.** Walk-forward by season, the combination ties
  Sagarin alone: RMSE difference +0.003, 95% CI [−0.055, +0.061] over 2016–25. It trails the
  close by 0.70 points, 95% CI [0.57, 0.84].

Reproduce: `python scripts/fair_oster_massey.py`, which writes
`$CFB_DATA_ROOT/processed/fair_oster_massey.json`.

---

## Method

The model is the paper's Fair–Shiller regression, with no constant:

$$
\begin{gathered}
Y_g = \alpha H_g + \sum_{k} \beta_k Q_{gk} + \lambda\, LV_g + \varepsilon_g \\[1em]
\begin{array}{rl}
\text{where}\quad g: & \text{one FBS-vs-FBS regular-season game, week} \ge 6 \\
Y_g: & \text{margin in points, team } i \text{ minus team } j \\
H_g: & +1 \text{ if } i \text{ is home, } -1 \text{ if } j \text{ is home, } 0 \text{ at a neutral site} \\
Q_{gk}: & 100\,(R_{jk} - R_{ik})/N \text{: system } k\text{'s rank gap as a percent of the } N \text{ ranked teams} \\
Q_{g,REC}: & 100 \times (\text{win\% of } i - \text{win\% of } j) \text{ to date} \\
LV_g: & \text{market's expected margin for } i = -\text{median closing spread across books} \\
\alpha: & \text{home-field advantage in points} \\
\beta_k,\ \lambda: & \text{weights; } \lambda \text{ enters only in Table 5}
\end{array}
\end{gathered}
$$

The equation weights each system's rank gap to predict the margin. A positive $\beta_k$ means a
better rank for $i$ predicts a bigger margin for $i$. A negative $\beta_k$ means that, holding the
other systems fixed, that system's opinion should be leaned against.

There is no constant because the choice of which team is $i$ is arbitrary. Each game starts
oriented home $= i$ and is then flipped by game-id parity. Flipping a row multiplies every
variable in it by $-1$, so the coefficients and standard errors are unchanged. Only R² and the
Table 1 correlations depend on the orientation.

Worked example: with the 2013–25 regression 9 weights, a team 20 percentile points better on
Sagarin ($Q = 20$) is predicted to win by $0.408 \times 20 \approx 8.2$ points at a neutral
site, before the COL and REC terms.

**Choices.** Two of these were set after a dry run whose results had been seen: the
core-coverage cutoff and the regression-9 rule. Both are marked below, with their effect.

- **Rankings.** `stg.massey_ranks`. For each game we use the latest edition dated strictly before
  its US/Eastern kickoff date.
  - No-lookahead check: the edition's W–L equals the team's record through the edition date in
    100% of games, and includes a later game in 0%.
- **Systems.** The paper's nine: MAT, SAG, BIL, AND (= Seattle Times/Anderson & Hester), COL, MAS,
  RTH, WOL, DUN. REC (win percentage) is built from the edition's W–L.
  - A system joins the Table 2 "core" if it ranks at least 90% of the era's games.
  - The rest enter Tables 3–4 on complete-case subsamples, as in the paper.
  - **Set after a dry run.** The first run used a 97% cutoff. That left COL (95.6%) and DUN
    (93.5%) out of the modern core. The cutoff was lowered to 90% to match the paper's
    full-coverage set, which includes both.
  - At 97% (modern core SAG, BIL, MAS, REC), the verdict does not change. Walk-forward
    combo − single is −0.004 [−0.049, +0.044]. Table 5 gives F = 1.85, p = .14.
- **Closing line.** The per-game median of `core.fact_game_line.spread_close` across providers.
  Coverage is 98.4% of the 2013–25 Table 2 sample. No lines exist here before 2013.
- **Regression 9.** Keep the systems whose edition-clustered |t| ≥ 1.96 in regression 8. This
  rule is **selection on the test set**. The walk-forward uses the full core instead.
  - **Set after a dry run.** The dry run used OLS |t| ≥ 2 instead.
- **t-statistics.** Every coefficient reports two: OLS (the paper's) and clustered by edition,
  because games in one week share a ranking snapshot.
  - The two agree closely on the main effects.
  - They do not agree on which systems survive in the small paper-era subsamples. In Table 3,
    BIL has OLS t 2.04 but clustered t 1.77. In Table 4, SAG has OLS t 2.46 but clustered t
    1.92.
  - With the OLS rule, BIL stays in Table 3 row 2, and SAG stays in Table 4 row 2 in place of
    COL. Tables 2 and 5, and the walk-forward, are identical under either rule.
- **Walk-forward.** For each season $s$, fit on all seasons before $s$ and score $s$.
  - The "best single" system is chosen by training-window SSR.
  - RMSE differences get a 95% interval from a bootstrap that resamples whole weekly editions
    (2,000 reps).
- **Trial count.** The final run fits 33 regressions across both eras, all listed in the JSON
  `trials`. Two earlier dry runs repeated the same specifications under the variants above
  (97% cutoff; OLS-t rule). That makes **3 full passes, about 95 regressions**.

## Data

| Era | Seasons | Games with an edition | Table 2 core | Table 2 n |
| --- | --- | --- | --- | --- |
| paper | 1998–2001 | 1,741 | MAT SAG BIL MAS DUN REC | 1,735 |
| modern | 2013–2025 | 6,220 | SAG BIL COL MAS DUN REC | 5,544 |

The paper had 1,588 games in weeks 6–15. Ours are CFBD weeks ≥ 6, which gives about 150 more.
The week numbering likely differs; this was not chased.

Massey's Colley series starts 2000-10-09. So in the paper window COL appears only in the
593-game Table 4 subsample, not in Table 2 as in the paper. MAT ends in 2007, so it is absent
from the modern era.

## Results

### Table 2 — each system alone, then combined

The table shows coefficients with (OLS t; clustered t). SE is the regression's standard error
in points.

| Era | Regression | H | Systems | SE | R² | % right |
| --- | --- | --- | --- | --- | --- | --- |
| paper | best single: DUN | 4.82 | DUN .381 (31.8; 32.5) | 16.66 | .400 | .730 |
| paper | reg 8, all six | 4.50 | MAT −.111 (−1.9); SAG .244 (4.2); BIL .087 (2.3); MAS −.016 (−0.3); DUN .183 (4.8); REC .012 (0.5) | 16.48 | .415 | .743 |
| paper | reg 9 | 4.57 | SAG .157 (4.6; 5.7); BIL .074 (2.0; 1.9); DUN .168 (4.6; 3.9) | 16.49 | .413 | .739 |
| modern | best single: SAG | 2.49 | SAG .416 (55.7; 53.8) | 16.37 | .372 | .717 |
| modern | reg 8, all six | 2.54 | SAG .399 (13.2); BIL .006 (0.3); COL −.091 (−3.6); MAS −.031 (−0.8); DUN .033 (1.3); REC .116 (5.3) | 16.33 | .376 | .721 |
| modern | reg 9 | 2.52 | SAG .408 (28.7; 27.4); COL −.095 (−4.3; −4.2); REC .121 (5.6; 5.3) | 16.33 | .376 | .722 |

Against the paper (its reg 9: SAG .217, BIL .075, COL −.171, DUN .119, REC .132; H 4.30):

- **Replicates.**
  - MAT and MAS carry no independent information in either era.
  - SAG is the anchor system.
  - A negative-weight system exists. In the modern era it is COL, the same system and sign
    as the paper's (−.095 vs −.171).
- **Differs.**
  - In 1998–2001, REC is not significant without AND. In Table 3, once AND enters, REC turns
    significant (.113, clustered t 3.0) and AND takes a negative weight (−.207, t −3.6). That
    is the pattern of the paper's Table 3: SEA −.182, REC .179.
  - In the modern era, DUN and BIL add nothing beyond SAG.
- **Home field.** 4.4–5.0 points in 1998–2001, matching the paper's 4.1–4.8. Only 2.4–3.0
  points in 2013–25.

### Tables 3–4 — partial-coverage systems

- **Paper era.**
  - Table 3 (n = 1,434, adds AND): AND −.207 (t −3.6).
  - Table 4 (n = 593, all ten): nothing but DUN is stable. COL's sign flips between regressions
    8 and 9 (−.232, then +.035). At n = 593 with ten collinear regressors, this table cannot
    rank systems, as the paper also found.
- **Modern era.**
  - Table 3 (n = 3,129): AND is not significant (−.096, t −1.3).
  - Table 4 (n = 2,769): AND −.194 (t −4.1), RTH +.093 (t 1.95).
  - Neither holds across both subsamples. The paper saw the same instability between its
    Tables 3 and 4.

### Stability (Chow test, first vs second half of the seasons)

- Modern: F = 0.30 on (4, 5536) df, p = .88. Stable.
- Paper era: F = 2.95 on (4, 1727) df, p = .019. **Not stable.**
- The paper reported F = 2.25 on (6, 1570) df and did not reject, citing a 5% critical value of
  3.67. The 5% critical value of F(6, 1570) is 2.10, so its own statistic has p = .036. The
  paper-era combination was unstable in both datasets.

### Table 5 — adding the closing line (2013–2025 only)

| Regression | LV | Others | SE | R² | % right |
| --- | --- | --- | --- | --- | --- |
| LV + H | 1.014 (61.2) | H −0.21 (−1.0) | 15.79 | .419 | .728 |
| reg 9 + LV | 0.952 (20.1) | H −.05, SAG .026 (1.1), COL −.022 (−1.0), REC .028 (1.3) | 15.79 | .420 | .728 |

- F test that everything except LV is zero: 0.97 on (4, 5452) df, p = .42 (clustered p = .47).
- t for LV = 1 is −1.01.
- Adding LV to each single-system regression gives LV between 0.97 and 1.01, and no system's
  clustered |t| above 1.1.
- Home field also drops to zero once the close is in: the market prices it fully.

### Walk-forward (the test the paper did not run)

| Era | Test seasons | n | RMSE best single | RMSE combo | RMSE close | combo − single, 95% CI | combo − close, 95% CI |
| --- | --- | --- | --- | --- | --- | --- | --- |
| paper | 1999–2001 | 1,320 | 17.33 | 17.23 | — | −0.10 [−0.29, +0.08] | — |
| modern | 2016–2025 | 4,135 | 16.37 | 16.38 | 15.68 | +0.00 [−0.06, +0.06] | +0.70 [+0.57, +0.84] |

- The training window picked SAG as the best single system every modern season.
- Out-of-sample encompassing test, Y on LV and the out-of-sample combination (clustered):
  LV 1.047 (t 22.3), combination −0.059 (t −1.2).

### Table A — combined ranking, last pre-bowl edition of 2025

Weights are modern reg 9 (SAG, COL, REC). The top five are Indiana, Ohio State, Oregon,
Texas Tech, and Notre Dame. Because COL's weight is negative, teams COL rates low move up
(Penn State: 6–6, COL 55th, 15th here). The full top 25 is in the JSON. For 2001 the same
procedure puts Miami, Florida, and Nebraska on top, which matches the paper's Table A order
of Miami, Nebraska, and Florida closely.

## What this does not support

- **No betting edge.** Nothing here is a bet. The only market result is that ranks add nothing
  to the close. There is no ROI, no CLV, and no execution test. It confirms, from an
  independent source (published ranks, not point predictions), the Prediction Tracker finding in
  [`panel-vs-line-2026-09-17.md`](../research/spread/docs/panel-vs-line-2026-09-17.md) that no
  panel line beats the close.
- **No open-line test.** The test uses the closing line, the strongest version of the market.
  It says nothing about whether ranks lead the **opener**. That is the line-movement question in
  `research/spread/`, which uses different data.
- **No "optimal weights."** The in-sample weights are selected on the test set and do not beat
  SAG out of sample. They should not be used as a rating.
- **No negative-weight rule.** The negative-weight system is real in-sample in both eras, but
  which system carries it (AND vs COL) changes with the sample. Not a rule to trade on.
- **No 1998–2001 market test.** There are no lines for that window here.

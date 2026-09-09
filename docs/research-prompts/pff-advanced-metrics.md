# Advanced Football Analytics Research: PFF and the Public Metric Stack

Paste the block below into Perplexity (Research / Deep Research mode).

---

## Shared research instructions

Research mode: exhaustive deep research with inline citations.

You are advising a solo developer building FBS college football pregame betting models
(spreads, totals, line-movement/CLV targets) in Python and DuckDB, with CFBD data from
2012-2025, ActionNetwork line history, and a licensed PFF API feed (team and player
grades, facet leaderboards, signature stats, participation).

- No word limit. Prefer depth, evidence quality, methodological detail, and implementation value.
- Cite every empirical and numeric claim immediately beside the claim.
- Prefer papers, official documentation, verified datasets, and reproducible backtests.
- Label undocumented industry, blog, podcast, and forum claims `[anecdotal]`.
- Label uncertain, extrapolated, weakly supported, or conflicting claims `[uncertain]`.
- Separate direct FBS/college evidence from NFL evidence and from mechanism-only reasoning.
  PFF's own published validation is overwhelmingly NFL; say so explicitly whenever you
  transfer an NFL result to college.
- Distinguish what PFF *documents publicly*, what PFF *markets*, and what independent
  researchers have *verified*. Never present PFF marketing copy as validated evidence.
- Never fabricate papers, data coverage, results, ROI, CLV, win rates, or effect sizes.
- For negative literature searches, write:
  `No published independent validation found in searched sources.` Never claim universal absence.
- For every backtest cited, report seasons, sample size, odds source, line timing, vig
  treatment, validation method, wager count, and uncertainty when available.
- Distinguish descriptive accuracy, year-over-year stability, out-of-sample predictive
  power, probability calibration, CLV, and realized profit. A metric can be excellent at
  one and worthless at the next.
- Enforce strict as-of availability: state, per metric, when in the week it is published,
  whether it is ever revised after publication, and whether any input uses post-game
  information (charting done after the fact still counts as charted-after-kickoff).
- State research cutoff date, databases searched, representative queries, and access limitations.

## Research assignment

Produce a working reference on advanced football analytics, centered on PFF but covering
the metrics PFF is normally combined with or compared against. For each metric family
answer the same five questions: what it measures, how it is actually computed, where it
falls short, how it is misused, and what better metric can be built on top of it.

### 1. Metric inventory - explain each

For each of the following, give the definition, the exact computation or charting process
where documented, the unit and scale, the level of aggregation (player / unit / team /
play), the earliest season available, and the publication latency:

**PFF-specific**
- PFF player grades (-2 to +2 per play, normalized 0-100) - grading rubric, grader
  workflow, second-review/quality-control process, position-specific criteria.
- PFF team grades and unit grades (offense, pass block, run block, coverage, pass rush, run defense).
- Wins Above Average / WAR (PFF's version) and any PFF Elo-style team rating.
- Signature stats: pressure rate, pressures allowed, hurries/hits/sacks split, time to
  throw, average depth of target, yards per route run (YPRR), catchable/contested target
  rates, tackles-avoided/yards-after-contact, missed-tackle rate, coverage snaps per
  target/reception, passer rating allowed, kick/punt grades.
- Alignment and participation data: snap counts, alignment splits (slot/wide/inline),
  personnel groupings, box counts, blitz/simulated-pressure charting, coverage-scheme labels
  (Cover 0-6, man/zone rate).
- PFF's college-specific coverage: which FBS games are fully graded, whether Group of Five
  and FCS opponents receive the same grading depth, and how the grade scale is normalized
  across a talent range far wider than the NFL's.

**The rest of the public stack (for contrast and for combination)**
- EPA per play and its variants (success rate, EPA allowed, early-down EPA, dropback EPA),
  and the expected-points model choices that make EPA values non-comparable across sources.
- WPA, and why it is nearly useless for prediction.
- SP+, FEI, FPI, Sagarin, Massey, Elo - what each conditions on, opponent-adjustment
  method, and preseason-prior weight.
- Havoc rate, line yards, stuff rate, second-level/open-field yards, adjusted sack rate.
- CPOE, expected yards after catch, air yards / aDOT, ESPN-style receiver scores.
- Completion-probability and expected-rushing-yards models built from tracking data, and
  the fact that college has no public tracking data comparable to NFL Next Gen Stats.
- Pace, seconds-per-play, plays-per-game, and neutral-situation adjustments.
- Recruiting/talent composites (247, Blue-Chip Ratio) and roster-continuity/portal metrics.

### 2. Where they fall short

For each metric family above, state the concrete failure modes, with evidence:

- **Subjectivity and inter-rater reliability.** What is publicly known about PFF grader
  agreement, grader training, and the audit process? Has any independent party measured
  reliability? What happens on plays where assignment is unknowable from broadcast angles
  (coverage responsibility, blocking assignment, blown-coverage attribution, defensive-line
  stunts)?
- **Broadcast-angle limitations in college** - off-screen players, missing All-22, tight
  camera on non-marquee games, and whether grading depth varies by game importance.
- **Scheme confounding.** Grades are per-play credit assignments inside a scheme; a metric
  that cannot separate scheme from player conflates them. Quantify where this bites hardest
  (offensive line, coverage, quarterback under pressure).
- **Small-sample instability.** Which metrics stabilize in how many snaps/plays/games?
  Give published or computable stabilization points (split-half reliability, KR-21, or
  year-over-year r) for grades, YPRR, pressure rate, missed-tackle rate, EPA/play.
- **Opponent adjustment.** Are PFF grades opponent-adjusted at all? What breaks when they
  are not, in a sport where schedule strength varies more than in any other league?
- **Roster turnover and portal churn** - the college-specific reason last season's team
  grade is a weak prior for this season.
- **Survivorship, garbage time, and score-state contamination** in both grades and EPA.
- **Metric-market overlap.** The market already prices most of this. Which metrics are
  plausibly already fully reflected in the opening line, and what evidence exists either way?
- **Circularity risk.** Where does a vendor metric use the betting market or a market-derived
  rating as an input, making it useless as an independent signal?

### 3. Pitfalls when using them in a model

Be specific and practical:

- **Lookahead and as-of discipline.** Weekly grade snapshots that are season-to-date and get
  revised; team-report endpoints that silently include the game you are trying to predict;
  season-final leaderboards used as if they were week-N knowledge. Describe how to build a
  genuinely point-in-time PFF panel and what to do if only end-of-season snapshots exist.
- **Aggregation traps.** Snap-weighted vs simple-average grades; grades of departed players
  still in a team aggregate; injured/benched starters; unit grades dominated by one player.
- **Normalization traps.** Grades normalized within season and within level - cross-season
  and cross-division comparisons are not on a common scale unless proven otherwise.
- **Collinearity** among grades, EPA, and SP+ - near-duplicate signal inflating apparent
  feature importance and destabilizing coefficients.
- **Multiple comparisons and garden-of-forking-paths** when screening dozens of facet
  metrics against a thin target.
- **Target choice.** Predicting margin vs predicting the closing line vs predicting line
  movement/CLV are different problems with different achievable R-squared; a metric useful
  for one may be worthless for another.
- **Vendor drift** - retroactive re-grades, methodology changes between seasons, schema and
  column changes in the API, and how to detect them automatically.
- **License and redistribution constraints** on PFF data in a derived model.

### 4. Where they can be improved

Concrete, testable improvements, ranked by expected value per unit of work:

- Opponent-adjusting PFF grades (ridge / mixed-effects opponent adjustment on per-play or
  per-game grade, with shrinkage), and how to validate that the adjustment adds
  out-of-sample value.
- Empirical-Bayes shrinkage of small-sample player and unit grades toward
  position/recruiting-rank priors.
- Explicit roster-continuity weighting: rebuild the team prior from returning players'
  individual grades and snaps rather than from last year's team grade.
- Separating scheme from personnel with fixed effects for coordinator/scheme and random
  effects for player.
- Recalibrating grades to an outcome scale (points, EPA, or line movement) instead of using
  the 0-100 scale directly as a feature.
- Uncertainty propagation: attaching a variance to every aggregated grade and letting the
  model use it (heteroskedastic weighting, or a Bayesian hierarchical spec).
- Combining PFF's charted inputs with play-by-play EPA to build metrics neither source can
  produce alone.
- Cross-source reconciliation: where PFF and CFBD disagree on snaps, participation, or
  outcome attribution, and which to trust.

### 5. Derived metrics that can be built on top

For each proposal give the formula/spec, the required inputs (naming the specific PFF facet
or endpoint family and the CFBD table), the expected failure mode, and one falsifiable test:

- Opponent-adjusted, snap-weighted returning-production grade (team preseason prior).
- Trench-mismatch index: pass-block grade vs opposing pass-rush grade at the unit level,
  and the analogous run-block / run-defense pairing - tested against rushing efficiency and
  against the total.
- Pressure-rate differential and expected sack rate (pressure rate x conversion prior),
  separating the stable component (pressure) from the noisy one (sacks).
- QB-under-pressure stability index: split QB grade clean-pocket vs pressured, weighted by
  the opponent's projected pressure rate.
- Coverage-mismatch score: WR YPRR and aDOT vs opposing CB coverage snaps-per-reception and
  passer-rating-allowed, alignment-matched (slot vs wide).
- Explosive-play propensity and variance forecast (not just the mean) - a distributional
  feature for totals and for alternate lines.
- Pace x efficiency interaction as an explicit plays-per-game forecast feeding a totals model.
- Special-teams and kicking grade converted to expected points per game.
- Injury/availability-adjusted unit grade using snap-share reallocation to the backup's own grade.
- A "market-residual grade": regress the closing line on market-visible ratings, then test
  whether PFF-derived features explain the residual - the only version of this work that can
  plausibly beat the number.
- Grade-based volatility/uncertainty feature to drive abstention rather than side selection.

### 6. Deliverables

1. A metric-by-metric table: definition, source, level, first season, latency, revision
   behavior, documented validation, independent validation, and a 1-5 usefulness score for
   (a) margin prediction, (b) closing-line prediction, (c) CLV.
2. A ranked list of failure modes with the specific diagnostic that detects each in a panel dataset.
3. A point-in-time PFF panel construction spec, including the leakage checks that must pass.
4. Ten derived-metric specs from section 5, each with inputs, formula, and a falsification test.
5. A prioritized experiment plan: what to test first, the chronological validation protocol,
   the pre-registered success threshold, and the kill criteria.
6. An explicit "what the market already knows" section separating features likely priced in
   from features with a plausible edge, with the evidence for each classification.

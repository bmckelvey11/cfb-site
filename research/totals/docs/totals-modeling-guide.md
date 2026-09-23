# FBS pregame totals: a modeling guide

**Status: living guide, Strand 2 reading material.** Every modeling claim here is a
hypothesis to test, not a finding. The guide adds no new numbers. Where it cites a number,
the number comes from a dated record in this repo (linked) or from an outside source
(labeled). If this guide and a dated record disagree, the record wins and this guide is
stale.

**What it combines.** Four source documents, merged and checked against what the repo has
since established:

| Source | Where it lives now | What this guide keeps |
| --- | --- | --- |
| FBS pregame totals research report (2026-09-08 cutoff) | [fbs-totals-system-research-report.md](fbs-totals-system-research-report.md) | Feature evidence levels, market literature, target table, leakage table, data sources |
| Frontier-model survey (2026-09-08 cutoff) | [fbs-totals-frontier-models.md](fbs-totals-frontier-models.md) | Model-family priorities, falsification tests, frontier leakage risks |
| Starter framework for a totals model | New in this guide (was untracked) | Target design, scoring decomposition, distribution-first output, build order |
| Conversation notes on regression, priors, and the market-residual workflow | New in this guide (was untracked) | Totals-specific shrinkage table, turnover decomposition, first feature set |

The two tracked reports stay as the full reference material, with their citation lists.
§7 writes opponent adjustment and previous-season priors in their totals form: points per
possession, pace, and one fit that does both. The general methods, their evidence, and the
head-to-head comparison stay in
[opponent-adjustment-priors-model-comparison.md](opponent-adjustment-priors-model-comparison.md),
which §7 links to instead of repeating.

Scoring is governed by [`docs/model-evaluation-standard.md`](../../../docs/model-evaluation-standard.md).
When this guide's evaluation advice and that standard differ, the standard wins.

---

## 1. Bottom line

1. **Model the gap to the market, not the total.** The target is the final total minus an
   auditable decision-time line. Low RMSE on raw points says nothing about edge: the book's
   total is already a strong forecast.
2. **The repo's clean totals attempts so far are nulls.** The walk-forward harness hits
   49.69% against the opener once leaked features are removed, and that is no better than
   shuffled predictions. The seasonal-under effect, kicker quality, and Greenline CLV
   against a gated Pinnacle close are all nulls too. See §2.
3. **The one market-relative signal on record predicts *movement*, not outcomes.** PFF's
   dropback-weighted passing grade moves the total by +0.26 points per SD between open and
   close. That argues for keeping $r^{\text{move}}$ (§3) as a first-class target.
4. **Line data sets the calendar, not model choice.** CFBD totals start in 2013. They carry
   an opener and a current number but no timestamp and no totals price, and there is no
   real sportsbook in them before 2018. Any ROI or CLV claim is bounded by which seasons
   can price a bet (§5).
5. **Output a distribution, then price it.** An over/under decision needs
   $P(\text{over})$, $P(\text{under})$, and $P(\text{push})$ at the offered number and
   price. §8 gives the conversion, which none of the four sources wrote down.

---

## 2. Where the repo already stands

Each row is a claim the source documents make or depend on, what this repo has measured,
and the record that measured it.

| Question | Sources said | Repo status | Record |
| --- | --- | --- | --- |
| How far back do CFBD lines go? | "2012–2025" | **2013.** 2012 returns games with empty `lines` | [cfbd-lines-coverage-2026-09-17.md](../../../docs/cfbd-lines-coverage-2026-09-17.md), [data-line-floor.md](../../../docs/data-line-floor.md) |
| Which books are in CFBD lines? | Unknown, audit first | 2013–17: aggregators and model lines only (`consensus`, `teamrankings`, `numberfire`). Real books from 2018. `consensus` dies after 2022 | [cfbd-lines-coverage-2026-09-17.md](../../../docs/cfbd-lines-coverage-2026-09-17.md) |
| Do CFBD lines carry open/close and a timestamp? | Unknown, audit first | `GameLine` has `overUnder` and `overUnderOpen`. It has **no capture timestamp and no over/under price** (moneylines only) | `cfbd-python/cfbd/models/game_line.py`; [clv-analysis.md](../../../docs/clv-analysis.md) treats `overUnder` as the close |
| Grade against one book or many? | Unstated | The system builder grades against the median across books, snapped to the half point | [median-line-2026-09-17.md](../../../docs/median-line-2026-09-17.md) |
| Timestamped multi-book odds | The Odds API, mid-2020 on | Wired in, alongside the Action Network history scrape and oddspapi's Pinnacle feed | [odds-sources-an-vs-apis-2026-09-11.md](../../../docs/odds-sources-an-vs-apis-2026-09-11.md), [oddsapi-ingest.md](../../../docs/oddsapi-ingest.md) |
| Does a feature-based totals model beat the opener? | Untested | **No.** 49.69% (95% CI 47.66–51.71, n=2,383, 2022–25) after removing leaked this-game features | [totals-model.md](../../../docs/totals-model.md) |
| Seasonal under effect | Not raised | **Null.** Late-season unders 50.80% vs early 51.00%, p=0.83 | [seasonal-totals-backtest.md](../../../docs/seasonal-totals-backtest.md) |
| Kicker quality/volatility past the close | Special teams "shrink heavily" | **Bound, not a zero.** CI upper bound buys a 51.5% over vs 52.38% break-even; underpowered | [kicker-quality-volatility-totals-2026-09-18.md](kicker-quality-volatility-totals-2026-09-18.md) |
| Can a team stat predict line movement? | Market-as-sensor listed as frontier | **Yes, one.** PFF passing grade, +0.26 pts/SD, Holm p 0.003, n=956 | [pff-line-movement-2026-09-22.md](pff-line-movement-2026-09-22.md) |
| Vendor picks vs a real close | Not raised | Greenline CLV **+0.06 ± 0.48** against gated Pinnacle; the personal 2023–25 bets show +0.29 against CFBD's close. The benchmarks differ, and the personal bets are mostly Greenline flags | [greenline-clv-market-close-2026-09-22.md](greenline-clv-market-close-2026-09-22.md), [clv-analysis.md](../../../docs/clv-analysis.md) |
| Arscott's zero-censoring bias | "Untested; replicate first" | The repo runs a strategy on the same mechanism: the floor-bias over-zero model prices the zero floor on team scores | [`models/over_zero/docs/MODEL_GUIDE.md`](../../../models/over_zero/docs/MODEL_GUIDE.md) |
| Key numbers in the total | "Respect key numbers" | Measured: one-point bins with neighbour lift, 2014–25 FBS | [total-points-distribution-2026-09-17.md](../../../docs/total-points-distribution-2026-09-17.md) |
| Wind | Anecdotal 13–15 mph thresholds | Pre-registered plan for crosswind vs along-field wind | [wind-orientation-totals.md](../../../docs/wind-orientation-totals.md) |
| Which stats are usable pre-game? | "Strictly trailing" | 565 of 1,043 PFF/CFBD columns usable; the dividing line is table grain | [pregame-feature-eligibility-2026-09-16.md](../../../docs/pregame-feature-eligibility-2026-09-16.md) |
| Opponent-adjusted efficiency | "Build it" | Built: crossed-random-effects PPA ratings, v1.0; five better EPA constructions specified. Weekly as-of ridge points-per-possession and pace ratings (§7.1–7.3, no priors) built; they beat raw ratings and a train mean on 2021–25 totals and trail the Bovada open by 0.33 MAE. Previous-season priors built; no-go on robustness | [ppa-opponent-adjusted-ratings-2026-09-16.md](../../../docs/ppa-opponent-adjusted-ratings-2026-09-16.md), [epa-metric-constructions-2026-09-18.md](../../../docs/epa-metric-constructions-2026-09-18.md), [weekly-ratings-2026-09-23.md](../../../docs/weekly-ratings-2026-09-23.md), [weekly-priors-2026-09-23.md](../../../docs/weekly-priors-2026-09-23.md) |

---

## 3. What to predict

The sources agree on one design choice: predict the part of the outcome the decision-time
market does not explain. Keep three targets, because each is a different edge.

$$
\begin{gathered}
r^{\text{final}}_g = T^{\text{final}}_g - L^{\text{dec}}_g
\qquad
r^{\text{move}}_g = L^{\text{close}}_g - L^{\text{dec}}_g
\qquad
T^{\text{final}}_g = S^{\text{home}}_g + S^{\text{away}}_g \\[1em]
\begin{array}{rl}
\text{where}\quad g: & \text{one game} \\
T^{\text{final}}_g: & \text{combined final points, overtime included (points)} \\
L^{\text{dec}}_g: & \text{the posted total at the fixed decision time (points)} \\
L^{\text{close}}_g: & \text{the posted total at kickoff, from a fixed benchmark source (points)} \\
S^{\text{home}}_g, S^{\text{away}}_g: & \text{each team's final score (points, } \ge 0\text{)} \\
r^{\text{final}}_g: & \text{outcome residual; positive means the game went over the decision line} \\
r^{\text{move}}_g: & \text{market move after the decision; positive means the total rose}
\end{array}
\end{gathered}
$$

$r^{\text{final}}$ is the betting question: was the number wrong? $r^{\text{move}}$ is the
CLV question: will the market agree with you later? A feature can predict one and not the
other. The PFF passing-grade result is an $r^{\text{move}}$ result, and it says nothing yet
about $r^{\text{final}}$. The team-score split exists because team totals and the zero
floor live there, which is where Arscott's bias and the over-zero model sit.

**Worked example.** A decision line of 54.5, a close of 56.0, and a 49–10 final give
$r^{\text{move}}=+1.5$ and $r^{\text{final}}=59-54.5=+4.5$. An over bet at 54.5 gained
1.5 points of CLV and won.

The research report's target table
([§3 there](fbs-totals-system-research-report.md#3-applicable-modeling-approaches-and-prediction-targets))
also lists the closing total as a separate target. It is diagnostic only, and it must never
be an input to a decision-time model.

---

## 4. The market is the baseline

**Outside literature**, with each source's scope kept. Details and references are in the
research report, §2.

- **Arscott (2023, *J. Sports Economics*)**: team-total lines are biased by censoring at
  zero. A naive strategy wins above 55% over about two decades and beats typical
  transaction costs. This is the only profitable-after-vig evidence found, and it is for
  **team totals**, not the game total.
- **Paul & Weinbach (2005)**: CFB totals show bettor preference for overs, so the over is
  overpriced. Abstract-level access only.
- **NFL, transfer hypotheses only.** Shank (2018) finds extreme-total and over-momentum
  inefficiency. A 1996–2019 NFL preseason study finds efficiency (50.8% unders). The NFL
  evidence conflicts, so no bias should be assumed to transfer.
- **Wind thresholds** (57% unders at 13+ mph, and similar): industry blogs with no stated
  line timing, vig, or holdout. `[anecdotal]`

**This repo's record** is in §2. Every clean test of the game total against a market close
so far is a null or a bound. The prior for any new feature is therefore "the market
already has it."

The frontier survey's six evidence levels are worth keeping as vocabulary: mechanism, then
raw-score forecasting, totals probability, incremental beyond the market, CLV, and
profitable after vig. Almost every feature and model family in the sources stops at level
1 or 2.

---

## 5. Line data sets the calendar

This section replaces the sources' "audit the lines first" with what the audit has found.

**What CFBD's lines can and cannot support**

- **Seasons.** 2013 on. The sources' training windows that start in 2012 are not feasible.
- **Provider.** 2013–17 is aggregators and model lines, not books. A backtest in that era
  measures accuracy against a consensus-style number, not against a price anyone could bet.
- **Timing.** `overUnderOpen` and `overUnder` (read as the close). No capture timestamp, so
  "decision time" can only mean *open* or *close*, and the open's own timing is unknown.
- **Price.** No over/under juice. ROI has to assume a price such as −110.

**What that means under the evaluation standard.** Its hard gates mark a result invalid if
"prices cannot be reconstructed at decision time." Applied to totals:

| Era | Decision time available | Price at decision | Use for |
| --- | --- | --- | --- |
| 2013–2017 | Open or close, untimed; aggregator/model lines | None | Forecast skill and calibration against the line only. No ROI, no CLV claims |
| 2018–2020 (to mid-2020) | Open or close, untimed; real books | None | Forecast skill; CLV open→close as a within-book measure; ROI only at an assumed price, labeled as such |
| Mid-2020 on | Timestamped multi-book snapshots (the-odds-api), plus AN history and Pinnacle | Yes | The only era where ROI and CLV at a real decision time pass the gate |

The sources proposed two calendars that conflict: one trains on 2012–2016 and tests from
2017, the other trains on 2012–18, tunes on 2019–21, and holds out 2022–25. Neither
survives the table above. §10 gives the reconciled version.

---

## 6. The scoring process

A total is possessions times points per possession. Modeling the two separately makes
misses diagnosable: an error is either a pace miss or an efficiency miss.

$$
\begin{gathered}
\mathbb{E}[T_g] \approx N_g\,\big(\text{PPP}^{\text{home}}_g + \text{PPP}^{\text{away}}_g\big) \\[1em]
\begin{array}{rl}
\text{where}\quad T_g: & \text{combined final points in game } g \\
N_g: & \text{expected possessions per team (the two sides differ by at most about one)} \\
\text{PPP}^{\text{home}}_g: & \text{expected points per possession for the home offense against this defense} \\
\text{PPP}^{\text{away}}_g: & \text{same for the away offense}
\end{array}
\end{gathered}
$$

The formula multiplies a shared possession count by the sum of the two offenses'
per-possession scoring. With 12 possessions each, a home offense at 2.4 PPP, and an away
offense at 2.0, the expectation is $12(4.4)=52.8$ points. One fewer possession per side
takes 4.4 points off, which is why pace errors move a total as much as efficiency errors.

Two caveats. First, possessions and efficiency are not independent: quick scores and
turnovers add possessions. Second, overtime adds a right tail this product does not
produce. Both argue for simulation (§9) once the linear version is understood.

**Pace**

- Use neutral-state pace (seconds per play in competitive, non-hurry situations), opponent
  adjusted and computed only through the prior completed game. Raw plays per game mixes
  both teams, game script, turnovers, and overtime.
- Useful pace features: plays per non-garbage drive, pass rate over expectation
  (incompletions stop the clock), no-huddle rate, and fourth-down aggressiveness.
- **2023 clock rule.** The clock now runs after first downs outside the final two minutes
  of each half, which is confirmed by NCAA and Football Foundation rule pages. The widely
  quoted size of the effect, about 7.8% fewer plays and 1.4% shorter games, comes from an
  r/CFB tally after Week 0. `[anecdotal]` Treat 2023 as a regime break and carry an era
  flag. Measuring the size is an open item (§14).

**Efficiency**

- Use opponent-adjusted EPA/PPA and success rate, split pass/rush and early/passing downs
  where the sample supports it. The repo's adjusted ratings are
  [ppa-opponent-adjusted-ratings-2026-09-16.md](../../../docs/ppa-opponent-adjusted-ratings-2026-09-16.md).
- Garbage time distorts both pace and efficiency. Filter it with a frozen definition, and
  test filtered against unfiltered rather than assuming the filter helps. The research
  report ranks this ablation second.
- Red-zone finishing, explosive rate, turnovers, and special teams are the least stable
  inputs. See §7.

**Environment**

- Weather enters as an interaction with passing and kicking tendency, not as an additive
  term. Wind matters more to a pass-heavy offense.
- Only an **archived forecast** is a legitimate pregame weather feature. Observed weather
  is a postgame fact, useful for sizing the mechanism and nothing else. Archived forecasts
  cost money retrospectively (Visual Crossing's historical-forecast tier) or have to be
  collected prospectively.
- Dome and roof status, altitude, travel, rest, and neutral site are mechanism-plausible,
  with no FBS totals evidence found.

---

## 7. Opponent adjustment, previous-season priors, and shrinkage

A team's raw scoring and pace depend on who it played. Opponent adjustment turns them into
ratings that do not. Before any games are played there is nothing to adjust, so the
ratings start from a prior built on last season. This section writes both for totals:
efficiency and pace in the units §6 multiplies, priors that carry across seasons, and
one fit that does adjustment and prior decay together.

The general methods are in
[opponent-adjustment-priors-model-comparison.md](opponent-adjustment-priors-model-comparison.md):
iterative, ridge, crossed random effects, Bayesian and Elo adjustment (§1 and §9 there),
SP+ and FPI prior components (§5), effective-sample decay (§6), empirical-Bayes reliability
(§7), and transfer-era roster features (§8). This section uses that doc's **additive sign
convention**: an offense effect $O$ is positive for a good offense, and a defense effect
$D$ is **negative** for a good defense, because it lowers what opponents score.

**Status.** §7.1–7.3 are built without priors: weekly as-of ridge ratings shrunk toward
league average, points from line scores, in `scripts/weekly_ratings.py`, scored in
[weekly-ratings-2026-09-23.md](../../../docs/weekly-ratings-2026-09-23.md). Tuned on
2014–2019, $\lambda_{\text{PPP}}=40$ possessions and $\lambda_{\text{pace}}=8$ games. §7.4–7.5
are built in reduced form — carryover plus offensive returning production, no talent or
play-caller terms — in `scripts/weekly_priors.py`, and failed their declared go rule
([weekly-priors-2026-09-23.md](../../../docs/weekly-priors-2026-09-23.md)): an early-week gain
that does not survive inflating the carryover by half. Fitted carryover: offense 0.47 (+0.13 × RP, not
distinguishable from 0), defense 0.60, pace 0.46. **Every coefficient and league average in
the worked examples below is illustrative, not estimated.**

### 7.1 Opponent-adjusted efficiency

Rate each team's points per possession, the $\text{PPP}$ in §6, against the defenses it
faced.

$$
\begin{gathered}
y_{ig}=\mu_s+O_i+D_{j(g)}+hH_{ig}+\epsilon_{ig} \\[1em]
\begin{array}{rl}
\text{where}\quad y_{ig}: & \text{team } i\text{'s offensive points per possession in game } g \text{ (regulation, competitive possessions)} \\
\mu_s: & \text{league-average points per possession in season } s \\
O_i: & \text{team } i\text{'s offense effect (points per possession; } +\text{ = better offense)} \\
j(g): & \text{team } i\text{'s opponent in game } g \\
D_{j(g)}: & \text{that opponent's defense effect (points per possession allowed; } -\text{ = better defense)} \\
h: & \text{home-field effect (points per possession)} \\
H_{ig}: & +1 \text{ if } i \text{ is home, } -1 \text{ away, } 0 \text{ neutral} \\
\epsilon_{ig}: & \text{game noise; its variance falls as the game's possession count rises}
\end{array}
\end{gathered}
$$

An average offense facing defense $j$ at that venue is expected to score
$\mu_s+D_j+hH$ per possession. Whatever team $i$ did above that is credited to its
offense. Each game is weighted by its possession count, so a 14-possession game counts more
than a 9-possession one. The defensive side of every game supplies the mirror observation:
opponent $i$'s scoring is data on $D_j$.

**Worked example (illustrative: $\mu_s=2.10$, $h=0.05$).** Team A scores 3.0 per
possession at home against a defense rated $D=-0.40$. The game credits A's offense with
$3.0-2.10-(-0.40)-0.05=+1.25$. Raw, 3.0 looks like $+0.90$ above average. Against a strong
defense it is worth $+1.25$.

Points per possession is used rather than EPA/play because §6 multiplies in those units.
EPA/play and success rate remain useful inputs to the priors in §7.4, and as features.
Drop FBS–FCS games or rate FCS teams separately (priors doc §2).

### 7.2 Opponent-adjusted pace

Efficiency is offense against defense. Pace is not: both teams feed one shared possession
count, so their effects add.

$$
\begin{gathered}
N_g=\nu_s+P_{\text{h}(g)}+P_{\text{a}(g)}+\epsilon_g \\[1em]
\begin{array}{rl}
\text{where}\quad N_g: & \text{possessions per team in game } g \text{ (regulation offensive possessions of both teams} \div 2\text{)} \\
\nu_s: & \text{league-average possessions per team per game in season } s \\
\text{h}(g),\ \text{a}(g): & \text{the home and away team in game } g \\
P_i: & \text{team } i\text{'s pace effect (possessions per team per game; } +\text{ = more possessions in its games)} \\
\epsilon_g: & \text{game noise, including game script}
\end{array}
\end{gathered}
$$

A fast team adds possessions to every game it plays, and a slow opponent takes them away
from the same game. That is why a pace rating has to be opponent-adjusted too: a team that
played three slow opponents has a raw possession count below its real tendency.

**Worked example (illustrative: $\nu_s=12.0$).** A $+0.8$ team meets a $-0.5$ team. The
expected count is $12.0+0.8-0.5=12.3$ possessions each.

Three cautions.

- **Possessions are partly an efficiency outcome.** Long drives, turnovers, and quick
  scores change the count, so $P_i$ absorbs some efficiency. A cleaner split rates neutral
  seconds per play for the offense only and derives possessions from it. Test both.
- **Overtime is excluded** from $N_g$. It is a separate tail, handled by the distribution
  (§8), not by pace.
- **Model the game's count, not two team counts.** Possessions alternate, so the two teams'
  counts are nearly equal. Priors doc §3 makes the same point.

### 7.3 From ratings to a total

$$
\begin{gathered}
\widehat{T}_g=\widehat{N}_g\left(\widehat{\text{PPP}}^{\text{home}}_g+\widehat{\text{PPP}}^{\text{away}}_g\right) \\[0.5em]
\widehat{N}_g=\nu_s+P_{\text{h}}+P_{\text{a}},
\qquad
\widehat{\text{PPP}}^{\text{home}}_g=\mu_s+O_{\text{h}}+D_{\text{a}}+h,
\qquad
\widehat{\text{PPP}}^{\text{away}}_g=\mu_s+O_{\text{a}}+D_{\text{h}}-h \\[1em]
\begin{array}{rl}
\text{where}\quad \widehat{T}_g: & \text{predicted regulation total (points)} \\
\text{h},\ \text{a}: & \text{the home and away team; } O,\ D,\ P \text{ are their current ratings} \\
\widehat{N}_g: & \text{predicted possessions per team (§7.2)} \\
\widehat{\text{PPP}}^{\text{home}}_g,\ \widehat{\text{PPP}}^{\text{away}}_g: & \text{each offense's predicted points per possession against this defense (§7.1)}
\end{array}
\end{gathered}
$$

This is §6's decomposition with the ratings filled in. Each offense's rate uses the
**other** team's defense, and home field moves the two rates in opposite directions.
Defensive and special-teams scores can be added as a small separate term, as in priors
doc §3.

**Worked example (illustrative: $\mu_s=2.10$, $h=0.05$, $\nu_s=12.0$).**

| | $O$ | $D$ | $P$ |
| --- | ---: | ---: | ---: |
| Home | +0.40 | −0.30 | +0.8 |
| Away | −0.10 | +0.20 | −0.3 |

- Home offense: $2.10+0.40+0.20+0.05=2.75$. The away defense is poor ($D=+0.20$).
- Away offense: $2.10-0.10-0.30-0.05=1.65$.
- Possessions: $12.0+0.8-0.3=12.5$.
- Total: $12.5\times(2.75+1.65)=55.0$.

If the market is 58.5, the decomposition says what would have to be true for the market to
be right: about 0.8 more possessions per team ($58.5/4.40=13.3$), or 0.28 more points per
possession between the two offenses ($58.5/12.5=4.68$). That turns an edge into a claim
about pace or about efficiency, which can each be checked.

### 7.4 Previous-season priors

A prior sets each rating before the season's first game. It starts from last season's
final opponent-adjusted rating, regresses it toward average, and adjusts for who left and
who arrived.

**Efficiency prior**

$$
\begin{gathered}
O_{i,0}=\left(b+c\,\text{RP}^{\text{off}}_i\right)O_{i,-1}+q\,Z^{\text{off}}_i \\[1em]
\begin{array}{rl}
\text{where}\quad O_{i,0}: & \text{prior for team } i\text{'s offense effect this season (points per possession vs this season's average)} \\
O_{i,-1}: & \text{team } i\text{'s final opponent-adjusted offense effect last season (vs last season's average)} \\
\text{RP}^{\text{off}}_i: & \text{offensive returning production, 0 to 1, as available before the season} \\
b: & \text{share of last season's effect a team keeps with nothing returning} \\
c: & \text{extra share kept per unit of returning production; } b+c<1 \\
Z^{\text{off}}_i: & \text{talent change on offense (recruiting plus transfers in, minus departures), standardized} \\
q: & \text{points per possession per standard deviation of talent change}
\end{array}
\end{gathered}
$$

The bracket is how much of last season carries over. It stays below 1 even when every
starter returns, because part of last season's rating was noise and luck. That shortfall
is the regression to the mean, applied before the season instead of discovered during it.
A team that lost most of its production regresses most of the way to average, and talent
change then moves it. Defense uses the same form with $D$, $\text{RP}^{\text{def}}$,
$Z^{\text{def}}$, and its own coefficients.

**Worked example (illustrative: $b=0.30$, $c=0.40$, $q=0.10$).** An offense finished last
season at $+0.80$.

- With 75% returning production the multiplier is $0.30+0.40(0.75)=0.60$, giving $+0.48$.
  A talent change of $+0.5$ SD adds $0.05$, for a prior of $+0.53$.
- With 30% returning, the multiplier is $0.42$, giving $+0.34$. With the same talent change
  the prior is $+0.39$.

The product $c\,\text{RP}\times O_{i,-1}$ is the interaction the priors doc (§5) calls the
simplest way to make a strong team with little returning regress harder. A second lag,
$e\,O_{i,-2}$, stays only if it earns its place in walk-forward testing. This replaces the
fixed 70/20/10 season weights (§7.9).

**Pace prior**

Pace belongs to the play-caller more than to the roster, so the prior switches on whether
the play-caller changed.

$$
\begin{gathered}
P_{i,0}=S_i\,a_{\text{same}}\,P_{i,-1}+\left(1-S_i\right)\left(a_{\text{new}}\,P_{i,-1}+\kappa\,P^{\text{call}}_{i,-1}\right) \\[1em]
\begin{array}{rl}
\text{where}\quad P_{i,0}: & \text{prior for team } i\text{'s pace effect this season (possessions per team per game vs this season's average)} \\
P_{i,-1}: & \text{team } i\text{'s final opponent-adjusted pace effect last season} \\
S_i: & 1 \text{ if the offensive play-caller is unchanged, } 0 \text{ if new} \\
P^{\text{call}}_{i,-1}: & \text{the new play-caller's team pace effect last season at a previous FBS job; } 0 \text{ if none} \\
a_{\text{same}},\ a_{\text{new}}: & \text{share of the team's own pace kept with the same or a new play-caller} \\
\kappa: & \text{share of the new play-caller's old pace carried over}
\end{array}
\end{gathered}
$$

With the same play-caller, the team keeps most of its own pace. With a new one, it keeps
less of its own and takes on part of the newcomer's.

**Worked example (illustrative: $a_{\text{same}}=0.7$, $a_{\text{new}}=0.3$,
$\kappa=0.5$).** A team was $+1.0$ possession last season.

- Same play-caller: $0.7(1.0)=+0.70$.
- New play-caller from a team at $-0.6$: $0.3(1.0)+0.5(-0.6)=0.00$. The team is projected
  at league pace.

**Data gap.** The warehouse has head coaches only.
[coach-playstyle-analysis.md](../../../docs/coach-playstyle-analysis.md) records that
"attribution is team-level", and a coordinator change under a stable head coach is
invisible. Until a play-caller table exists, $S_i$ can only mean "same head coach", which
misses coordinator-only changes. See open item 8 (§14).

**Why the priors are effects, not levels.** Every prior above is a deviation from its own
season's average. The season averages $\mu_s$ and $\nu_s$ are set separately. That is how
league-wide shifts stay out of team priors: the 2023 clock rule, and the scoring decline
since 2016 in
[total-points-distribution-2026-09-17.md](../../../docs/total-points-distribution-2026-09-17.md).
A team that was $+1.0$ possession in 2022 enters 2023 as a $+1.0$ team in a
lower-possession league. It does not keep 2022's absolute snap count.

This moves the era problem into the season average. It does not solve it. Before Week 1,
$\mu_s$ and $\nu_s$ are themselves forecasts: last season's value plus any known rule
effect. In 2023 the size of that rule effect is anecdotal (open item 3). The league
averages do firm up quickly once games are played, because every game informs them.

**Inputs and their timing.**
[pregame-feature-eligibility-2026-09-16.md](../../../docs/pregame-feature-eligibility-2026-09-16.md)
classes CFBD's `returning_production`, `recruiting_teams`, and `talent` as
`pregame_direct`: fixed before the season starts. The research report still flags revision
risk for any value that can change after publication, such as a figure that takes in
offseason transfers. Record the date each value was pulled, and use the value as of the
prior's snapshot date.

**Prior uncertainty.** Each prior has a variance. It is wider when returning production is
low, the play-caller is new, or the talent change is large. That variance sets how hard
the fit in §7.5 holds the rating to its prior. It also belongs in the predictive
distribution's $\sigma(x)$ (§8).

### 7.5 One fit: shrink toward the prior

Opponent adjustment and prior decay can be one ridge fit. The only change from the priors
doc's ridge (§1 there) is the shrinkage target: each rating is pulled toward **its own
prior**, not toward zero.

$$
\begin{gathered}
\min_{\mu_s,\,h,\,O,\,D}\;\sum_{g<t}w_g\left(y_{ig}-\mu_s-O_i-D_{j(g)}-hH_{ig}\right)^2
+\sum_i\lambda_i^{O}\left(O_i-O_{i,0}\right)^2
+\sum_j\lambda_j^{D}\left(D_j-D_{j,0}\right)^2 \\[1em]
\begin{array}{rl}
\text{where}\quad g<t: & \text{games completed before the cutoff } t \\
w_g: & \text{the game's possession count (weight on its points-per-possession observation)} \\
O_{i,0},\ D_{j,0}: & \text{the previous-season priors from §7.4} \\
\lambda_i^{O},\ \lambda_j^{D}: & \text{each team's penalty, in possessions: how much evidence its prior is worth; } \ge 0
\end{array}
\end{gathered}
$$

The first sum rewards ratings that reproduce what happened against the schedule played.
The penalty sums charge for moving away from the prior. In Week 0 there are no games, so
every rating equals its prior. As possessions accumulate, the data term grows and the
ratings move toward what the team has shown against its opponents. No separate fade
schedule is needed; the decay falls out of the fit.

$\lambda$ plays the role of the priors doc's $n_0$. In the normal case,
$\lambda_i=\sigma^2/\tau_i^2$: per-possession noise variance over prior variance, in
possessions. A confident prior has a small $\tau_i$, a large $\lambda_i$, and moves slowly.
A team with a new play-caller or little returning production gets a smaller $\lambda_i$
and follows its games sooner. Pace uses the same fit with $N_g$, $P_i$, $P_{i,0}$, and
$\lambda_i^{P}$. Tune the overall scale of each $\lambda$ on earlier seasons by
one-step-ahead loss.

**Worked example (illustrative: $\lambda=30$ possessions).** An offense has a prior of
$+0.50$. After three games and 36 possessions, its opponent-adjusted average is $+1.10$.
Treating this one team in isolation,
$\widehat{O}\approx(30\times0.50+36\times1.10)/(30+36)=+0.83$. After eight games and 96
possessions at the same average, $(15+105.6)/126=+0.96$. The formula is an approximation:
the real fit couples every team through its opponents, so a rating also moves when an
opponent's does.

**Identification.** Center each season's priors so the offense priors sum to zero, and so
do the defense priors. Leave $\mu_s$ and $h$ out of the penalty. Otherwise the penalty
pulls the average rating toward the average prior and fights the intercept. That is the
same add-$c$-to-every-$O$, subtract-$c$-from-every-$D$ ambiguity the priors doc §1 warns
about.

**Implementation.** Write $O_i=O_{i,0}+\delta_i$ and fit an ordinary ridge on $\delta$,
with the prior-implied prediction subtracted from $y$. A per-team $\lambda_i$ is a
per-column rescaling. Refit at every cutoff and append the ratings to a snapshot table
keyed by `as_of`, as priors doc §4 describes.

### 7.6 Leakage rules for priors and adjustment

- **Last season's final ratings are legal inputs.** That season ended before this one
  began. This season's final ratings joined back onto its own early games are not legal.
- **Fit every coefficient on earlier seasons only**: $b$, $c$, $q$, $a$, $\kappa$, and the
  scale of $\lambda$. Never tune them on the season being scored.
- **Refit at each cutoff.** A rating used for a Week 5 game comes from games completed
  before that game's decision time, not from a mid-season or full-season fit.
- **Play-caller changes count from their announcement date**, not from the season start.

### 7.7 How hard other inputs regress

Ordinal guidance for the inputs used as features or as prior ingredients, taken from the
conversation notes. The strengths are hypotheses: fit the actual $\lambda$, $n_0$, or reliability $B$
per metric in walk-forward folds.

| Metric family | Regress toward | Strength | Why |
| --- | --- | --- | --- |
| Neutral pace | Team preseason pace, then an era-specific conference mean | Moderate | Coaching persistence, but game state and opponent drive it too |
| Offensive EPA/play | Team preseason offense | Moderate | Real signal, distorted early by schedule |
| Defensive EPA/play | Team preseason defense | Moderate–high | Noisier and more opponent-dependent than offense |
| Explosive-play rate | Team prior and conference mean | High | Rare events dominate short samples |
| Turnover margin | Expected turnover margin (§7.8) | Very high | Realization is largely luck |
| Fumble recovery rate | 50% | Very high | Driven by the bounce |
| Sack rate | Pressure rate times a conversion prior | Moderate | Pressure repeats, conversion is noisy |
| Special teams | Specialist prior plus tier mean | High early | Low attempt volume; the kicker record found PAAR persists at r 0.16 |

### 7.8 Turnovers: separate opportunity from realization

Turnovers matter to totals through possessions and short fields. Model the expected count,
not the realized one: expected fumbles lost is half of total fumbles, and expected
interceptions come from pass volume, pressure, and the quarterback's prior rate. ESPN's
turnover-luck framing does the same split. The mechanism evidence is NFL. `[transfer]`

### 7.9 Conflicts between the sources, resolved

- **Fixed 70/20/10 season weights.** The conversation notes proposed
  $P = 0.70A_{t-1}+0.20A_{t-2}+0.10A_{t-3}$ as a default. The priors doc learns $f$ over
  one to four prior seasons with a regression toward the league mean, plus a
  prior-rating × returning-production interaction. **Use the priors doc.** Fixed weights
  cannot regress, and they ignore roster continuity.
- **Returning-production weights.** The conversation notes quote Connelly's offense weights
  as 39.6/35.0/22.3/3.1 (OL snaps / WR-TE yards / QB yards / RB yards) and defense as
  65.9/19.2/14.9, labeled 2026. The priors doc quotes 40/35/22/3 and 66/19/15 as the 2025
  formula. The two agree to rounding. Neither is a totals weight; fit target-specific
  weights for offense, defense, pace, and volatility.
- **The four-game shrinkage threshold** is a starting point from the research report, not
  a rule. The effective-sample blend replaces it.

### 7.10 PFF player-level priors

If PFF data is point-in-time valid, rebuild each unit from shrunk player grades weighted by
projected snaps, rather than carrying last season's team grade. That avoids counting
departed players and trusting thin-sample transfers. PFF documents its −2 to +2 play grade
and 0–100 scale but not its aggregation, so recalibrate the grades as vendor features.
Check coverage first: [pregame-feature-eligibility-2026-09-16.md](../../../docs/pregame-feature-eligibility-2026-09-16.md)
lists which PFF columns are usable pre-game.

---

## 8. From a distribution to a bet

A point forecast cannot be bet. The decision needs the probability of each outcome at the
offered line and the price actually on offer.

$$
\begin{gathered}
p_{\text{o}} = \Pr(T > L),\qquad
p_{\text{u}} = \Pr(T < L),\qquad
p_{\text{p}} = \Pr(T = L) \\[0.5em]
\text{EV}_{\text{over}} = p_{\text{o}}\,(d_{\text{o}}-1) - p_{\text{u}}
\qquad
\text{EV}_{\text{under}} = p_{\text{u}}\,(d_{\text{u}}-1) - p_{\text{o}} \\[1em]
\begin{array}{rl}
\text{where}\quad T: & \text{the game's combined final points (an integer)} \\
L: & \text{the offered total (points); a half-point line makes } p_{\text{p}}=0 \\
p_{\text{o}}, p_{\text{u}}, p_{\text{p}}: & \text{model probabilities of over, under, push; they sum to 1} \\
d_{\text{o}}, d_{\text{u}}: & \text{decimal odds on offer for each side (}-110 \to 1.9091\text{)} \\
\text{EV}: & \text{expected profit per unit staked; a push returns the stake, so it adds 0}
\end{array}
\end{gathered}
$$

A winning over pays $d_{\text{o}}-1$ per unit, a losing one costs the unit, and a push
costs nothing. Setting EV to zero gives the break-even condition
$p_{\text{o}}/(p_{\text{o}}+p_{\text{u}}) > 1/d_{\text{o}}$. At −110 that is 52.38% of the
non-push outcomes.

**Worked examples, both at −110.**

- Half-point line, 52.5, model gives $p_{\text{o}}=0.55$: EV $=0.55(0.9091)-0.45=+0.050$,
  so +5.0% per unit.
- Integer line, 52, model gives $p_{\text{o}}=0.53$, $p_{\text{p}}=0.03$,
  $p_{\text{u}}=0.44$: EV $=0.53(0.9091)-0.44=+0.042$. The push mass is not lost, but it
  does not win either, so it shrinks the edge. The break-even check is
  $0.53/0.97=0.546>0.524$.

**Consequences for the model**

- **A Normal around the mean understates pushes at key numbers.** Final totals are
  integers with spikes. A continuous model needs a continuity correction:
  $\Pr(T>52.5)=\Pr(T\ge53)$, and $\Pr(T=52)\approx F(52.5)-F(51.5)$. On top of that, the
  empirical spike at each key number from
  [total-points-distribution-2026-09-17.md](../../../docs/total-points-distribution-2026-09-17.md)
  should correct the push mass. That also prices half-point buys.
- **Predict the variance, not just the mean.** Two games with the same edge in points have
  different $p_{\text{o}}$ when one is a high-tempo, explosive matchup and the other a
  grind. The sources' distributional candidates (GAMLSS/NGBoost, §9) exist for this.
- **Use the price on offer, never a best-of-books price picked afterward.** The research
  report's leakage table lists retrospective best-price selection as inflating ROI.
- **Calibration does not create edge.** Isotonic or Platt recalibration fixes stated
  confidence. A perfectly calibrated model with no information beyond the market still
  has zero EV after vig.

---

## 9. The model ladder

Add a rung only when it beats the one below on the same games, timestamps, line source, and
folds.

| Rung | Model | Target | Why it is here |
| --- | --- | --- | --- |
| 0 | Residual = 0 (market only) | $r^{\text{final}}$ | Records the market's own loss; everything is scored against it |
| 1 | Calibrated market: intercept and slope on $L$, by total band, week, and era | $r^{\text{final}}$ | Cheap test for extreme-total bias; motivated by Arscott and the NFL extreme-total work |
| 2 | Ridge or lasso on a compact block (§9.1) | $r^{\text{final}}$, $r^{\text{move}}$ | Interpretable incremental signal; lasso and forward selection beat all-features in comparable NFL work |
| 3 | Distributional: NGBoost or GAMLSS, $\mathcal{N}(\mu(x),\sigma(x)^2)$ on the residual | Distribution of $r^{\text{final}}$ | Feeds §8 directly. Falsified if predicted variance does not track squared residuals out of sample |
| 4 | Gradient boosting, shallow and early-stopped on chronological folds | Residual or total, then priced | Nonlinear interactions; overfit risk at about 800 FBS games a season |
| 5 | Possession or drive simulation (competing-risk drive outcomes, semi-Markov possessions) | Joint team scores | Team totals, correlation, overtime tail, key numbers from one engine. Highest engineering cost |

### 9.1 First feature block

- Decision-time total; absolute spread, as a strength-asymmetry control.
- Home and away offense, defense, and pace ratings, fit per §7.4–7.5.
- Matchup terms: home offense minus away defense, away offense minus home defense, and the
  mean of the two pace priors.
- Clock-rule era flag; neutral-site flag.
- Roster and staff turnover as uncertainty terms, which can also feed $\sigma(x)$ at rung 3.

### 9.2 Frontier families

Full reasoning and falsification tests are in
[fbs-totals-frontier-models.md](fbs-totals-frontier-models.md) §3. None has a published
FBS totals application.

| Priority | Families |
| --- | --- |
| Priority experiment | GAMLSS/NGBoost; dynamic Bayesian latent-state ratings (Kalman updating instead of rolling windows); TabPFN walk-forward; simple era-weighted training around 2023; meta-labeling for bet selection |
| Secondary | BART; copula joint-score models; survival drive models; matrix factorization; temporal GNNs; symbolic regression |
| Conditional | HMM or change-point detection (validate against known coaching and QB changes); Hawkes processes; semi-Markov possessions; multi-task learning; coach embeddings; multi-book market-as-sensor models (2020 on only) |
| Weak fit or not recommended | Normalizing flows; deep ensembles; sequence models; player embeddings; reinforcement learning for staking |

**Market as sensor.** Given the PFF movement result, a model of $r^{\text{move}}$ built
from multi-book quotes is more promising than the survey's "conditional" label suggests.
Keep the survey's warning, though: a good closing-line predictor can have zero edge on the
game.

---

## 10. Validation

**Calendar, reconciled with §5**

1. **Forecast-skill folds, 2013 on.** Expanding window, leave one season forward: train
   through $s-1$, test on $s$. Score against the CFBD line with proper scores only. No ROI
   and no CLV in this layer.
2. **Economic folds, mid-2020 on.** Same design, restricted to games with a timestamped
   price at the decision time. ROI and CLV come only from here.
3. **Within a test season**, update ratings through the previous completed week and predict
   the whole next slate together. Freeze architecture and hyperparameters for the season.
4. **Holdout.** 2025 is heavily looked-at in this repo already. Treat **2026, graded
   prospectively**, as the untouched confirmation set. Once a season has influenced a
   modeling choice, a later season has to replace it.
5. **2020 and 2023** are stress seasons (COVID scheduling; the clock rule). Report them
   separately rather than pooling them silently.

**Leakage checks.** The general rules are in root `CLAUDE.md` and the evaluation standard.
These are the totals-specific ones the sources name:

- **Close leaking into an open-time model.** Query on `snapshot_time <= decision_time`
  instead of trusting column names. CFBD has no snapshot time, so CFBD-era models may use
  `overUnderOpen` only.
- **Full-season opponent adjustments applied to early games.** Rebuild ratings as of each
  week.
- **Preseason inputs revised after publication**, such as returning production and
  recruiting. Archive the published snapshot, not a later re-scrape.
- **Conference membership.** Use membership as of that season.
- **TabPFN context sets.** Unit-test that no future game ever enters the in-context
  training set.
- **Graph and embedding models.** Build graphs strictly causally in time.
- **Threshold and subgroup mining**, as in the wind examples. Predeclare, report the
  neighboring thresholds, and count trials.

**Uncertainty.** Bootstrap by week or season, not by game. Games in a week share rating
error, weather systems, and market conditions.

---

## 11. What to report

Report the evaluation standard's **Tier 1** list. Mapped to totals:

- **Proper score against the same-time de-vigged market.** CRPS or log score on the total's
  distribution, relative to rung 0. CFBD-era folds have no price, so "de-vigged" means the
  line itself as the market median.
- **Calibration slope and intercept**, plus a reliability plot of $p_{\text{o}}$, and PIT
  coverage for distributional models.
- **CLV**: mean, median, and positive rate against a fixed benchmark close (gated Pinnacle
  from 2020, per [greenline-clv-market-close-2026-09-22.md](greenline-clv-market-close-2026-09-22.md)).
  Signed so positive favors the side bet: close minus bet total for an over, and bet total
  minus close for an under.
- **ROI with an interval, bet count, independent events, drawdown**: economic folds only.
- **Fold and season stability, trial count, and the untouched holdout.**

The sources' own metric tables ask the same four questions: final-total forecast, residual
forecast, probability forecast, and execution. The standard makes them binding.

---

## 12. Selection and staking

- **Selection.** Bet when §8's EV clears a predeclared threshold at the offered price. Track
  results by edge bucket: larger modeled edges have to win more often, or the edge is not
  real. The Greenline rule search registered the opposite pattern as a hypothesis for
  weeks 4+: PFF's top edge quintile was its worst (see
  [greenline-totals-rule-search-2026-09-22.md](greenline-totals-rule-search-2026-09-22.md)).
- **Meta-labeling.** A secondary classifier trained on strictly earlier primary-model
  outputs decides when to trust a forecast. It is falsified if it cannot beat a fixed edge
  threshold on ROI across seasons.
- **Staking belongs to [`research/bankroll/`](../../bankroll/CLAUDE.md).** That unit's rules
  apply: win rates come from a Beta posterior, never a point estimate, and sizing is
  fractional Kelly with a drawdown cap. This guide sets no staking rule.

---

## 13. Build order, given what exists

The source documents each gave a build order from zero. The repo is not at zero.

| Step | Status | Next action |
| --- | --- | --- |
| 1. Audit lines | Partly done: floor, provider mix, fields (§2, §5) | Open item (§14): open-vs-close timing agreement against the-odds-api from 2020 |
| 2. Core game, drive, play tables | Done (warehouse) | — |
| 3. Point-in-time pace and efficiency | Built: weekly as-of ridge PPP and pace ratings, no priors ([weekly-ratings-2026-09-23.md](../../../docs/weekly-ratings-2026-09-23.md)). Beat raw and train mean on 2021–25; 0.33 MAE behind the open; early weeks indistinguishable from the mean | λ re-tuned on total loss over pre-2021 seasons: unchanged in effect (40/4 vs 40/8, [weekly-lambda-total-2026-09-23.md](../../../docs/weekly-lambda-total-2026-09-23.md)). A tuned Ridge/Elastic Net recombination of the nine ridge_v1 as-of features (tuning-lab run `run-de1927346ab0`, inner folds 2015–19) matches `ridge_v1`'s own total on 2021–25: −0.035 MAE, −0.10 to +0.03, descriptive (spent holdout); re-weighting the components adds nothing. Next: neutral-pace snapshots; garbage-time ablation (§14 item 5) |
| 4. Previous-season priors and blend | Built in reduced form ($b$, $c$, $b_D$, $a$; no $q$, $\kappa$), prior-centered ridge refit at each cutoff. No-go: early gain −0.24 MAE vs ridge_v1, lost when the carryover is inflated by half ([weekly-priors-2026-09-23.md](../../../docs/weekly-priors-2026-09-23.md)) | At total-tuned λ (80/8) the priors improve early (−0.36) and later (−0.11) but lose it under more prior weight; still no-go ([weekly-lambda-total-2026-09-23.md](../../../docs/weekly-lambda-total-2026-09-23.md)). Carryover scale tuned pre-2021: k = 1.0, frozen as prior_v3 ([prior-scale-2026-09-23.md](../../../docs/prior-scale-2026-09-23.md)). Next: the one confirmatory 2026 look when the regular season completes |
| 5. Rung 0 and 1 baselines | Not recorded for $r^{\text{final}}$ by era | Record the market's own loss per season and era |
| 6. Rung 2 on the residual | The 2022–25 harness (predicts the total, not the residual) is a null | Refit on $r^{\text{final}}$ and $r^{\text{move}}$ with the §9.1 block |
| 7. Distribution and pricing | Not built | Rung 3, priced with §8 |
| 8. Validation | Harness is walk-forward | Split forecast folds from economic folds (§10) |
| 9. Metrics | Standard exists; the tuning lab (`python -m models.tuning run`) writes a model card per run with trial counts, fold stability, intervals, and calibration | Tier 1 card per model |
| 10. Boosting, simulation, frontier | Not started | Only after 5–9 |

---

## 14. Open items

Each of these would produce a number, so each needs its own dated doc and script when run.
None is answered here.

1. **Open/close timing fidelity.** On 2020+ games, how well do CFBD's `overUnderOpen` and
   `overUnder` match the-odds-api's first and last snapshots for the same book?
2. **Market loss by era.** Rung 0 and rung 1 residual loss per season, and whether the
   calibration slope differs from 1 by total band. This is the combined-total version of
   Arscott's question. Lead, not an answer: on 2021–25 Bovada opens, totals landed about
   15% of the way from the open toward a pooled mean (slope 0.15, 0.06–0.23;
   [weekly-ratings-2026-09-23.md](../../../docs/weekly-ratings-2026-09-23.md)).
3. **Size of the 2023 clock effect** on plays, possessions, and totals in the warehouse,
   replacing the anecdotal 7.8%. Also whether the market's totals had caught up by a given
   week of 2023.
4. **Year-over-year stability** of neutral pace, possessions, plays per drive, and success
   rate, split by era. The priors doc lists this as unverified.
5. **Garbage-time ablation**: filtered against unfiltered pace and efficiency features, on
   $r^{\text{final}}$.
6. **Does the PFF passing-grade movement signal reach $r^{\text{final}}$?** Or is it CLV
   only?
7. **Offseason carryover.** Fitted values of $b$, $c$, and $q$ (§7.4) for offense, defense,
   and pace: how much of last season's adjusted rating survives, and how much returning
   production changes that.
8. **Play-caller table.** Offensive play-caller by team-season, with the date of each
   change, so the pace prior can separate coordinator changes from head-coach changes. No
   such table exists (§7.4).

---

## 15. What this guide does not support

- **No totals edge.** Nothing here shows one. The repo's clean tests of the game total are
  nulls or bounds (§2).
- **No transfer of outside results.** Arscott's result is about team totals. The NFL
  results conflict. The wind thresholds are anecdotal.
- **No fixed parameters.** The shrinkage strengths, the four-game threshold, and the prior
  weights are starting points to fit, not values to hard-code.
- **No ROI or CLV from 2013–2019 CFBD lines alone.** There is no price, no timestamp, and,
  before 2018, no book (§5).
- **Frontier families are hypotheses.** "No published FBS application found" is a search
  result from the 2026-09-08 survey, not proof of absence and not evidence of promise.

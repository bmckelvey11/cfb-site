# Team rating models: theory

This page collects the modelling ideas behind the team ratings: what a rating system should
represent, how it should learn from games, and where its uncertainty comes from. It is a
reference for reasoning, not a list of work. What is planned, in what order, and what each
step must pass lives in [`rating-model-roadmap.md`](rating-model-roadmap.md). How the live
Glicko rating works today is in [`glicko-method.md`](glicko-method.md).

**Source.** Most of this page is a design review Blake shared on 2026-10-17, of a document
named `glicko-college-football.md` that is not in this repo. It also cites the totals research
in [`research/totals/docs/`](../../research/totals/docs/). Each idea below carries a **Here**
note saying what this repo has already built or tested, so it can be read against the record.
None of the ideas below has been tested here unless its Here note says so.

## 1. Where the review and this repo disagree

The review assumes the Glicko design under review is an offense / defense / pace
points-per-possession (PPP) model. **The live Glicko rating is not.** It is one number per
team, learned from final margins (see [`glicko-method.md`](glicko-method.md)). Offense,
defense and pace ratings exist here as a separate model: the weekly ridge fit `ridge_v1`
([`docs/weekly-ratings-2026-09-23.md`](../../docs/weekly-ratings-2026-09-23.md)). Two of the
review's main recommendations have already been tested here:

- **"Build a dynamic PPP Kalman filter next."** This was built and tested as `kalman_v1`. It
  forecast totals worse than the static weekly ridge in all five seasons of 2021–25, and it
  stopped at its screen gate
  ([`docs/dynamic-ratings-2026-09-23.md`](../../docs/dynamic-ratings-2026-09-23.md)). The
  review's top recommendation is therefore a known null in its simplest form. A new attempt
  needs a reason the richer version would succeed where that one failed.
- **"Make it market-residual."** That is already how this repo scores any model
  ([`docs/model-evaluation-standard.md`](../../docs/model-evaluation-standard.md)). Glicko v1
  failed that test, with an encompassing slope against the Bovada open of 0.06
  [−0.08, 0.20]. P1 passed it, at 0.19 [0.05, 0.33], but on a second look at the same seasons.
  The real test is the sealed 2026 confirmation.

So the review is mostly right in direction. It underrates how much of it is already in place,
and how much of its main build suggestion has already failed once.

## 2. Two questions a rating can answer

A **strength model** answers "how good is each team, and how sure are we?" A **market model**
answers "where is the line wrong?" The two are different targets:

$$
\begin{gathered}
\text{Edge}_{g,t} = \mathbb{E}\left[Y_g \mid X_{g,t}\right] - \text{Market}_{g,t} \\[1em]
\begin{array}{rl}
\text{where}\quad Y_g: & \text{the outcome of game } g \text{ being bet: home margin, game total, or one team's score, points} \\
X_{g,t}: & \text{everything known at decision time } t\text{: ratings, features, and the market itself} \\
\text{Market}_{g,t}: & \text{the market's number for } Y_g \text{ available at } t\text{: home margin } = -\text{spread}\text{, or the total} \\
\text{Edge}_{g,t}: & \text{points by which the model expects the outcome to beat the line; positive favours the over or the home side}
\end{array}
\end{gathered}
$$

A model can forecast $Y_g$ well and still have no edge. If the market already knows
everything the model knows, the edge is noise around zero. That is why a lower forecast
error than Elo is not evidence of a betting edge. Glicko v1 beat Elo by 0.33 CRPS and still
sat 0.46 points of MAE behind the Bovada open.

**Here:** the encompassing slope is this repo's version of the test. It regresses
$Y_g - \text{Market}$ on $\mathbb{E}[Y_g] - \text{Market}$, and a slope clear of 0 means the
disagreement carries information.

## 3. A football-native state

Chess Glicko tracks one strength per player. Football scores come from two units facing each
other, at a pace both teams influence. The review's proposed state for team $i$ at week $t$:

$$
\begin{gathered}
O_{i,t} = O_{i,t-1} + \eta^{O}_{i,t} \qquad D_{i,t} = D_{i,t-1} + \eta^{D}_{i,t} \qquad P_{i,t} = P_{i,t-1} + \eta^{P}_{i,t} \\[1em]
\begin{array}{rl}
\text{where}\quad O_{i,t}: & \text{offense, points per possession above league average; + is better} \\
D_{i,t}: & \text{defense, points per possession allowed vs average; } - \text{ is better} \\
P_{i,t}: & \text{pace, possessions per game above average} \\
\eta^{O}, \eta^{D}, \eta^{P}: & \text{weekly random drift, mean 0, each with its own variance}
\end{array}
\end{gathered}
$$

Each unit's strength carries over week to week and drifts by a small random amount. The drift
variance is the dial between "a team is what it was" (small drift) and "only recent games
matter" (large drift).

A game links the states to what is observed:

$$
\begin{gathered}
\mu^{PPP}_{h} = \alpha_t + O_{h,t} - D_{a,t} + H^{PPP}_t + X^{PPP}_{h,a,t} \qquad
\mu^{PPP}_{a} = \alpha_t + O_{a,t} - D_{h,t} + X^{PPP}_{a,h,t} \qquad
\mu^{poss} = \beta_t + P_{h,t} + P_{a,t} + X^{pace}_{h,a,t} \\[1em]
\begin{array}{rl}
\text{where}\quad \mu^{PPP}_{h}, \mu^{PPP}_{a}: & \text{expected points per possession for the home and away offense} \\
\alpha_t: & \text{league-average points per possession in season/week } t \\
H^{PPP}_t: & \text{home edge in points per possession} \\
X^{PPP}, X^{pace}: & \text{matchup and context terms (weather, travel, regime), zero if unused} \\
\mu^{poss}: & \text{expected possessions per team in the game} \\
\beta_t: & \text{league-average possessions per team}
\end{array}
\end{gathered}
$$

Each team's expected scoring rate is the league average, plus its offense, minus the opposing
defense, plus the home edge for the home side. Expected points are then roughly $\mu^{PPP}
\times \mu^{poss}$. Keeping pace separate matters. Otherwise a fast, mediocre offense, which
scores a lot because it has many possessions, looks the same as an efficient one.

**Here:** `ridge_v1` uses exactly this decomposition, but fits it statically each week. The
dynamic version is `kalman_v1`, which was a null (§1). The live Glicko collapses it to one
number per team: $r_h - r_a \approx (O_h - D_a) - (O_a - D_h)$, scaled by possessions.

## 4. Observation noise: how much one game should count

Glicko and `kalman_v1` both treat a game's result as the truth plus Gaussian noise of fixed
variance. Football results are noisier than that, and noisy in uneven ways: possession
count, defensive and special-teams scores, short fields, turnovers, overtime and garbage
time. The options, from simplest to richest:

| Option | What it does | Review's view |
| --- | --- | --- |
| Fixed Gaussian variance | Every game counts the same | Benchmark only |
| Student-t residuals | Shrinks the pull of extreme results smoothly, with no hard cap | Strong default |
| Heteroskedastic variance | A game with more meaningful possessions counts more | Strong addition |
| Count model (Poisson / negative binomial) | Models scores as counts directly | Advanced |

A simple heteroskedastic form:

$$
\begin{gathered}
R_g = R_0 + \frac{R_1}{\max\left(n_g, c\right)} \\[1em]
\begin{array}{rl}
\text{where}\quad R_g: & \text{observation variance of game } g\text{'s PPP, (points per possession)}^2 \\
R_0: & \text{noise floor that no number of possessions removes} \\
R_1: & \text{noise that averages away with more possessions} \\
n_g: & \text{competitive possessions in game } g \\
c: & \text{a floor on } n_g \text{, so a game with very few competitive possessions does not get near-infinite variance}
\end{array}
\end{gathered}
$$

A game's PPP is an average over its possessions, so its noise shrinks roughly as one over
the possession count. With $R_0 = 0.01$, $R_1 = 1.5$ and $c = 10$, a 15-possession game has
variance 0.11 and a 25-possession game 0.07. The longer game moves the ratings about 1.5
times as much.

**Here:** the live Glicko has a fixed $\sigma$ and no cap ($C = \infty$). The P2 test tried a
robust clip on the surprise, a cousin of Student-t. It moved CRPS by less than 0.001
([`glicko-p2-2026-10-15.md`](glicko-p2-2026-10-15.md)). Bundle C tests a game-type noise
multiplier (×1.5 for bowls and FBS-vs-FCS games).

## 5. Garbage time and competitive weighting

A hard rule, such as "drop possessions once the lead is above 28 in the fourth quarter", throws
away information at an arbitrary edge. The softer alternative weights each possession by how
likely it was to be competitive:

$$
\begin{gathered}
w_p = \Pr\left(\text{competitive} \mid \text{margin}_p, \text{clock}_p, \text{quarter}_p, \text{context}_p\right) \\[1em]
\begin{array}{rl}
\text{where}\quad w_p: & \text{weight of possession } p \text{, from 0 (pure garbage time) to 1 (fully competitive)} \\
\text{margin}_p, \text{clock}_p, \text{quarter}_p: & \text{score gap, time left and period when possession } p \text{ starts} \\
\text{context}_p: & \text{anything else that signals effort, such as starters in or out (rarely observed)}
\end{array}
\end{gathered}
$$

Weighted PPP, explosiveness and pace are then computed with $w_p$. A 35-point
fourth-quarter possession might get $w_p = 0.1$, and a one-score third-quarter possession
$w_p = 1$. The robustness test is to compare five definitions: all possessions, standard
removal, continuous weighting, regulation only, and offense-only points. If the ratings
change a lot across them, the signal is fragile.

**Here:** not built for ratings. The pace work uses neutral-situation snaps for seconds per
snap, which is a hard filter.

## 6. Not all points are offensive points

$$
\begin{gathered}
\text{Points} = \text{Offensive} + \text{Defensive return} + \text{Special-teams return} + \text{Safeties} \\[1em]
\begin{array}{rl}
\text{where}\quad \text{Offensive}: & \text{points scored on a team's own offensive possessions} \\
\text{Defensive return}: & \text{points from interception or fumble returns} \\
\text{Special-teams return}: & \text{points from kick or punt returns, and blocked kicks} \\
\text{Safeties}: & \text{2-point safeties scored by the defense}
\end{array}
\end{gathered}
$$

A pick-six is 7 points that the offense did not score and the defense did not "allow" in the
usual sense. Counting it as offensive PPP makes the scoring team's offense look better and
the other defense worse. The cleaner design rates offense and defense on offensive
possessions only. Non-offensive scores are then a separate, rare and noisy component, added
back when forecasting a score.

**Here:** Glicko uses final margins, so every point counts. Whether `ridge_v1`'s PPP leaves out
return scores has not been checked for this page.

## 7. Uncertainty that follows events, not a free volatility

Glicko-2 gives each player a volatility parameter, which says how erratic they are. With
about 12 games a season, one team's volatility cannot be estimated reliably, and it soaks up
noise. The alternative is process variance that rises with observable events:

$$
\begin{gathered}
q^{(k)}_{i,t} = q^{(k)}_{base} + q^{(k)}_{days}\,\Delta d_{i,t} + q^{(k)}_{off}\,\mathbb{1}[\text{offseason}] + q^{(k)}_{roster}\,Z_{i,t} \\[1em]
\begin{array}{rl}
\text{where}\quad q^{(k)}_{i,t}: & \text{variance added to team } i\text{'s unit } k \text{ before week } t \text{, points}^2 \\
k: & \text{the unit: offense, defense, pace, or a single overall rating} \\
q_{base}: & \text{variance added every step} \\
q_{days}: & \text{variance per day idle; } \Delta d_{i,t} \text{ is days since the team's last game} \\
q_{off}: & \text{variance added once at the offseason} \\
q_{roster}: & \text{variance per unit of disruption; } Z_{i,t} \text{ scores events such as a new starting QB, a coaching change, or heavy portal turnover}
\end{array}
\end{gathered}
$$

Every term is a reason to be less sure, tied to something visible. It is easier to check
than a hidden per-team volatility, and it generalises from team to team.

**Here:** the live Glicko already has the first three terms, for the overall rating only.
$\tau^2 = 2.25$ per idle week is the days term, and $\delta^2 = 36$ is the offseason term. It
has no roster term.

## 8. Preseason: separate the mean from the uncertainty

The review splits the offseason into two jobs. The first is where each unit starts:

$$
\begin{gathered}
\mu_{i,pre} = w_1 \cdot \text{last rating} + w_2 \cdot \text{multi-year baseline} + w_3 \cdot \text{returning production} + w_4 \cdot \text{QB continuity} + w_5 \cdot \text{talent} + w_6 \cdot \text{coaching continuity} \\[1em]
\begin{array}{rl}
\text{where}\quad \mu_{i,pre}: & \text{team } i\text{'s starting rating for the new season, per unit (offense and defense separately)} \\
w_1, \ldots, w_6: & \text{weights fit on earlier seasons only; each input is z-scored or in rating points}
\end{array}
\end{gathered}
$$

The second is how sure the start is:

$$
\begin{gathered}
\sigma^2_{i,pre} = \sigma^2_{i,post} + \sigma^2_{off} + \sigma^2_{roster} + \sigma^2_{data} \\[1em]
\begin{array}{rl}
\text{where}\quad \sigma^2_{i,post}: & \text{the team's end-of-season variance, points}^2 \\
\sigma^2_{off}: & \text{generic offseason change} \\
\sigma^2_{roster}: & \text{extra variance from roster disruption} \\
\sigma^2_{data}: & \text{extra variance where the inputs are missing or thin (FCS teams, newly promoted teams)}
\end{array}
\end{gathered}
$$

Splitting offense from defense matters. A team can keep its quarterback and line while
losing its whole secondary.

**Here:** the live Glicko uses only $w_1$ (0.7 carryover) toward a conference mean, and a
flat $\delta^2$. P2 added returning production and recruiting to the mean. It helped in
2014–19 and hurt in 2021–25. The likely reason is that CFBD's returning-production figure
ignores incoming transfers. Bundle B tries a 3-season history ($w_2$) and a transfer-aware
returning production. Tuning gave the returning-production term weight 0. Preseason inputs
are only valid if their historical snapshots are frozen as of publication. Most CFBD
preseason tables are current values that were revised later.

## 9. Covariance between teams

A diagonal filter updates only the two teams in a game. But a result is also evidence about
everyone those teams played. Carrying the covariance between teams captures that. If A beat B
and B later beats C badly, A's rating rises too. The review suggests a middle ground: a 3×3
covariance within each team (offense, defense, pace), and only a simplified covariance across
teams.

**Here:** bundle A (`GlickoFull`) carries the full cross-team covariance for the one-number
rating. It was frozen 2026-10-17. On 2021–25, for reference only, it improves CRPS by 0.023,
and it awaits its holdout. A dense covariance across every FBS and FCS team is cheap at
about 260 teams, so the review's cost worry does not bite here.

## 10. Regimes: the game changed under the data

Scoring conditions are not stable across seasons. The changes most likely to matter:

- The 2023 clock rules cut possessions. Pre- and post-2023 pace are not directly comparable.
- Season and conference scoring baselines.
- Overtime rules by era.
- 2020, the COVID season.
- Neutral sites, domes, altitude, travel and time zones.
- Weather, but only as forecast at decision time.

**Here:** the Glicko never scores 2020. Bundle C tests a home edge trending by season, and
travel and time-zone terms. The totals research covers the 2023 clock break
([`research/totals/docs/totals-modeling-guide.md`](../../research/totals/docs/totals-modeling-guide.md)).

## 11. Scores as a joint distribution

Margin and total are not independent. Pace, weather, turnovers and game state move both
teams' scores together. A score model that simulates home and away points jointly gives
consistent margin, total and team-total probabilities from one source. The market's own
version is a useful baseline:

$$
\begin{gathered}
\hat{S}_h = \frac{T + M}{2} \qquad \hat{S}_a = \frac{T - M}{2} \\[1em]
\begin{array}{rl}
\text{where}\quad \hat{S}_h, \hat{S}_a: & \text{market-implied home and away scores, points} \\
T: & \text{the market game total, points} \\
M: & \text{the market home margin, points } (= -\text{spread})
\end{array}
\end{gathered}
$$

With a total of 52 and the home team favoured by 7, the implied score is home 29.5, away
22.5.

**Here:** the over-zero unit found structure in team-score distributions, from zero-point
floors ([`models/over_zero/`](../../models/over_zero/)). A joint score model would build on that.

## 12. Calibration is its own layer

Probabilities from a Gaussian or simulation model are rarely calibrated as they come out. A
separate map from raw to reliable probabilities is fit on earlier seasons only, then frozen.
Isotonic regression needs a large sample; Platt or beta calibration need less. Check slope,
intercept, Brier, log loss, CRPS, PIT histograms and coverage by uncertainty bucket.

**Here:** the Glicko's σ_pred of 13.5 is a one-parameter calibration of the margin spread. Its
calibration slope moved from 1.09 to 1.005.

## 13. Model families compared

| Model | Best use | Review's view | Here |
| --- | --- | --- | --- |
| Elo | Baseline | Required benchmark only | Built; Glicko beats it by 0.41 CRPS |
| Glicko / Glicko-2 | Uncertainty prototype | Diagnostic, not the final model | Live as a margin filter (P1.1) |
| Dynamic ridge O/D | Transparent benchmark | Mandatory | `ridge_v1`, weekly |
| Dynamic PPP Kalman | Core production candidate | Best next build | `kalman_v1`: null vs ridge |
| Hierarchical Bayesian state-space | Full uncertainty and pooling | Only after simpler models pass | Not built |
| Gradient-boosted residual model | Nonlinear market overlay | Challenger once features are clean | Not built |
| Joint Poisson / negative-binomial score model | Team totals, score distributions | High-priority research | Not built; over-zero work is closest |
| Stacking / ensemble | Combining signals | Final stage only | Not built |
| Market-anchored Bayesian model | Forecasting around the consensus | Likely strongest betting design | Not built |

## What this page does not support

- **No idea here is evidence.** Each is a hypothesis, until a declared test in this repo
  scores it.
- **Rankings from this review.** "Strong default" and "best next" are the reviewer's
  opinions, not results. One of them, the dynamic PPP Kalman filter, already failed here once.

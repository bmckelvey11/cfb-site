# College Football Opponent Adjustment, Preseason Priors, and Model Comparison

## Scope

This is a single consolidated report covering opponent adjustment, preseason priors, prior decay, transfer-era roster modeling, two-way crossed team/opponent random effects, and head-to-head model comparison. The intended applications are FBS game totals and opener-to-close line movement. Every historical feature must be generated from information available before the target kickoff or market timestamp.

## Notation guide

Subscript $i$ identifies the focal team, $j$ its opponent, $g$ a game, $p$ a play, $t$ a chronological update, and $k$ an iterative fitting step or statistic where explicitly stated. A hat denotes an estimate or forecast.

| Symbol | Definition | Interpretation |
|---|---|---|
| $y_p$ | Play-level response | Usually offensive EPA or a 0/1 success indicator. EPA is the change in expected points attributable to a play.[^1] |
| $y_{ig}$ | Team-game response | EPA/play, success rate, points/drive, possessions, or seconds/play for team $i$ in game $g$ |
| $O_i$, $u_i^{off}$ | Offensive team effect | Amount by which team $i$'s offense changes the response relative to average |
| $D_i$, $d_i^{def}$ | Defensive team effect | Opponent-suppression effect; the sign depends on the chosen equation |
| $R_{i,t}$ | Elo rating | Overall team-strength scalar at time $t$ |
| $\theta_{i,t}$ | Generic latent rating | Can represent offense, defense, pace, or another unit-level process |
| $\mu$, $\alpha$, $\beta_0$ | Population intercept | Average response for reference conditions |
| $H$ | Venue indicator | Often +1 home, -1 away, and 0 neutral from the offense's perspective; this is CFBD's public ridge coding.[^2] |
| $h$, $\beta_H$ | Home-field coefficient | Venue effect in the response's units |
| $w_g$ | Game weight | Equal game weight, eligible-play count, reliability weight, or recency weight, depending on specification |
| $\epsilon$ | Residual error | Observed response minus systematic prediction |
| $\lambda$ | Ridge penalty | Larger values cause stronger coefficient shrinkage; the numerical value depends on scale and software conventions.[^3] |
| $\sigma_e$ | Residual standard deviation | Remaining observation-level variation |
| $\sigma_{off}$, $\sigma_{def}$ | Random-effect standard deviations | Genuine between-team variation in offense and defense |
| $\tau$ | Prior or hierarchical standard deviation | Controls partial pooling around a prior or group mean |
| $\rho$ | Offense-defense correlation | Population association between a program's latent offensive and defensive effects |
| $n_0$ | Prior effective sample size | Number of pseudo-plays, pseudo-drives, or pseudo-games represented by the preseason prior |
| $n_{i,t}^{eff}$ | Current-season effective sample size | Information accumulated before time $t$, adjusted for dependence or reliability |

### Defensive sign convention

Under $y=\mu+O_i+D_j$, an elite defense normally receives a negative coefficient because it lowers offensive production. Under $y=\mu+u_i^{off}-d_j^{def}$, an elite defense receives a positive $d_j^{def}$. The second form is easier downstream because higher values mean better units for both offense and defense. Store the convention in feature names and metadata rather than silently negating effects later.

## 1. Opponent-adjustment methods

### Iterative/additive adjustment

**Summary:** repeatedly estimate performance above expectation after removing the current estimate of opponent strength.

This section uses the additive sign convention $y=\mu+O_i+D_j$, so a good defense has a **negative** $D$. A basic offensive update is

$$
\begin{gathered}
O_i^{(k+1)}=
\frac{\sum_{g\in G_i}w_g\left(y_{ig}-\mu-D_{j(g)}^{(k)}-hH_{ig}\right)}
{\sum_{g\in G_i}w_g} \\[1em]
\begin{array}{rl}
\text{where}\quad O_i^{(k+1)}: & \text{team } i\text{'s offensive rating after iteration } k+1 \text{ (response units, e.g. EPA/play; } +\text{ = better offense)} \\
G_i: & \text{team } i\text{'s eligible games played before the cutoff} \\
j(g): & \text{the opponent team } i \text{ faced in game } g \\
w_g: & \text{game weight (plays, reliability, or recency); } w_g \ge 0 \\
y_{ig}: & \text{team } i\text{'s offensive response in game } g \text{ (e.g. EPA/play)} \\
\mu: & \text{league-average response} \\
D_{j(g)}^{(k)}: & \text{opponent's defensive rating from the previous iteration; } -\text{ = better defense} \\
h: & \text{home-field effect in response units} \\
H_{ig}: & +1 \text{ if } i \text{ is home, } -1 \text{ away, } 0 \text{ neutral}
\end{array}
\end{gathered}
$$

Read the term in parentheses as "what the offense did, minus what an average offense would have done in that game." An average offense facing opponent $j$ at that venue is expected to produce $\mu+D_j+hH$; anything above that is credited to the offense. The weighted mean of those per-game residuals is the new rating.

The defensive update mirrors it, subtracting the current offensive ratings of the teams that defense faced:

$$
\begin{gathered}
D_j^{(k+1)}=
\frac{\sum_{g\in G_j}w_g\left(y_{i(g)g}-\mu-O_{i(g)}^{(k)}-hH_{i(g)g}\right)}
{\sum_{g\in G_j}w_g} \\[1em]
\begin{array}{rl}
\text{where}\quad D_j^{(k+1)}: & \text{team } j\text{'s defensive rating after iteration } k+1 \text{ (}-\text{ = better defense)} \\
G_j: & \text{team } j\text{'s eligible games before the cutoff} \\
i(g): & \text{the offense team } j \text{ faced in game } g \\
y_{i(g)g}: & \text{that offense's response in game } g \\
O_{i(g)}^{(k)}: & \text{that offense's rating from the previous iteration} \\
H_{i(g)g}: & \text{venue indicator from the offense's perspective}
\end{array}
\end{gathered}
$$

**Worked example (illustrative numbers).** League average $\mu=0.00$ EPA/play, $h=0.02$. Team A gains $+0.15$ EPA/play at home against a defense rated $D=-0.10$. The per-game residual is $0.15-0-(-0.10)-0.02(1)=+0.23$. Holding a strong defense near its usual output earns more credit than the raw $+0.15$ suggests.

Alternate the two updates until the largest change falls below a tolerance. After each pass, subtract the mean from both rating vectors. Without that centering the system is unidentified: adding a constant $c$ to every $O$ and subtracting $c$ from every $D$ leaves every prediction unchanged.

This is the transparent family behind least-squares and recursive average-opponent ratings, but it should not be labeled the exact modern SP+ formula because SP+ is proprietary. Massey's published method treats games as regression observations, estimates ratings with a common normalization, and can include global home field and offense/defense decomposition. A published FBS pace model uses the same recursive idea for possessions, updating each team's expected pace relative to opponents until the largest rating change is at most 0.0001.[^4][^5]

**Strength:** easy to audit as “performance above opponent expectation.” **Weakness:** sparse or weakly connected early schedules need damping, priors, or pseudo-games; otherwise conference clusters can float relative to one another.

### Ridge offense-defense regression

**Summary:** estimate every offense, defense, and home-field effect simultaneously while shrinking weakly identified team effects toward average.

For play-level EPA, keeping the additive convention ($D<0$ is a good defense):

$$
\begin{gathered}
y_p=\mu+O_{o(p)}+D_{d(p)}+hH_p+\epsilon_p \\[1em]
\begin{array}{rl}
\text{where}\quad y_p: & \text{EPA on play } p \\
o(p),\ d(p): & \text{the offense and the defense on the field for play } p \\
O_{o(p)}: & \text{that offense's effect (EPA/play; } +\text{ = better)} \\
D_{d(p)}: & \text{that defense's effect (EPA/play allowed; } -\text{ = better)} \\
\mu: & \text{league-average EPA/play} \\
h,\ H_p: & \text{home-field effect and venue indicator } (+1/-1/0) \text{ from the offense's side} \\
\epsilon_p: & \text{play-level noise}
\end{array}
\end{gathered}
$$

Every play is one row. Its design-matrix row has a 1 in the offense's column, a 1 in the defense's column, and the venue code. One regression then separates the teams, because each offense is seen against many defenses and each defense against many offenses.

Estimate the coefficients by minimizing

$$
\begin{gathered}
\sum_p\left(y_p-\mu-O_{o(p)}-D_{d(p)}-hH_p\right)^2
+\lambda_O\sum_i O_i^2+\lambda_D\sum_iD_i^2 \\[1em]
\begin{array}{rl}
\text{where}\quad \lambda_O,\ \lambda_D: & \text{ridge penalties for offense and defense; } \ge 0 \text{, larger = more shrinkage} \\
\sum_i O_i^2,\ \sum_i D_i^2: & \text{sum of squared team effects across all teams}
\end{array}
\end{gathered}
$$

The first sum is ordinary least squares: it rewards ratings that reproduce each play. The two penalty sums charge a cost for every team rating that moves away from zero. A team with 60 plays cannot justify a large rating, because the fit it buys is small next to the penalty. A team with 800 plays can. $\mu$ and $h$ are left out of the penalty so the intercept and home field are not shrunk. Separate $\lambda_O$ and $\lambda_D$ allow offense and defense to have different reliability, although the public CFBD example uses a common penalty.

With $\lambda=0$ this is plain least squares, and it breaks down on sparse schedules. As $\lambda\to\infty$ every team rating goes to 0, which is league average.

CFBD's implementation builds offense and defense indicators, codes HFA as +1/-1/0, drops FBS-FCS games, and searches ridge values from 75 to 325. The author reports that full-season play data often select roughly 150–200 and that partial-season data can require stronger regularization. Those values are not portable constants because response scaling, sample size, feature standardization, and library objective definitions change the effective penalty. Working Python code is available in the associated repository.[^2][^6]

### Bayesian hierarchical adjustment

**Summary:** estimate offense and defense through probability distributions that partially pool sparse teams while preserving posterior uncertainty.

A robust play-level specification is

$$
\begin{gathered}
y_p\sim t_\nu(\eta_p,\sigma_e),
\qquad
\eta_p=\mu+O_i+D_j+hH_p \\[1em]
\begin{array}{rl}
\text{where}\quad t_\nu(\eta_p,\sigma_e): & \text{Student-}t\text{ distribution with center } \eta_p \text{ and scale } \sigma_e \\
\nu: & \text{degrees of freedom; small (3 to 7) = heavy tails, } \nu\to\infty \text{ = normal} \\
\eta_p: & \text{expected EPA on play } p \\
i,\ j: & \text{offense and defense on play } p \\
O_i,\ D_j: & \text{offense and defense effects (additive: } D<0 \text{ is a good defense)}
\end{array}
\end{gathered}
$$

$$
\begin{gathered}
O_i\sim N(m_{c(i),O},\tau_O^2),
\qquad
D_i\sim N(m_{c(i),D},\tau_D^2) \\[1em]
\begin{array}{rl}
\text{where}\quad c(i): & \text{team } i\text{'s conference or parent group} \\
m_{c,O},\ m_{c,D}: & \text{average offense and defense effect in group } c \\
\tau_O,\ \tau_D: & \text{spread of teams around their group mean (same units as } y\text{)} \\
N(m,\tau^2): & \text{normal distribution with mean } m \text{ and variance } \tau^2
\end{array}
\end{gathered}
$$

The first line is the likelihood: how plays are generated given the ratings. The Student-$t$ has heavier tails than a normal, so one 80-yard touchdown moves the ratings less than it would under squared error. The second line is the prior: before seeing a team's plays, the model expects it to sit near its conference average, with typical deviations of $\tau$.

The posterior balances the two. A team with few plays stays close to $m_c$. A team with many plays can move far from it. A small $\tau$ pools hard, so every team looks like its conference. A large $\tau$ pools little and approaches unpenalized least squares.

The group means should themselves get a prior, $m_{c,O}\sim N(0,\tau_{conf}^2)$. Without it, a conference linked to the rest of FBS by only a few nonconference games can drift to an extreme level with nothing pulling it back.

Hierarchical attack/defense models with home effects are established in team-sport research, and dynamic sports-rating models allow team strength to evolve through time. No public walk-forward FBS study was located that proves this specification beats ridge-adjusted EPA against betting markets **[unverified]**. Its documented advantages are partial pooling, team-specific priors, and uncertainty propagation—not established market superiority.[^7][^8]

### Elo-style updating

**Summary:** update an overall team rating sequentially according to how surprising each result was.

$$
\begin{gathered}
R_{i,t+1}=R_{i,t}+K M_t(S_{i,t}-E_{i,t}) \\[1em]
\begin{array}{rl}
\text{where}\quad R_{i,t}: & \text{team } i\text{'s rating before game } t \text{ (rating points)} \\
S_{i,t}: & \text{result: } 1 \text{ win, } 0.5 \text{ tie, } 0 \text{ loss} \\
E_{i,t}: & \text{pregame win probability implied by the rating gap and home field; } 0<E<1 \\
K: & \text{update size (rating points per unit of surprise)} \\
M_t: & \text{optional margin-of-victory multiplier; } M_t=1 \text{ ignores margin}
\end{array}
\end{gathered}
$$

$S-E$ is the surprise. It is positive when a team does better than expected and negative when it does worse, and the rating moves in proportion to it. The opponent receives the opposite update in a zero-sum implementation.

A common generic choice for $E$, taken from chess Elo and **not** CFBD's unpublished curve, is

$$
\begin{gathered}
E_{i,t}=\frac{1}{1+10^{-(R_{i,t}-R_{j,t}+HFA)/400}} \\[1em]
\begin{array}{rl}
\text{where}\quad R_{j,t}: & \text{opponent's pregame rating} \\
HFA: & \text{home-field bonus in rating points (} +\text{ for the home team, } -\text{ away, } 0 \text{ neutral)} \\
400: & \text{scale; a 400-point edge means roughly 10-to-1 odds}
\end{array}
\end{gathered}
$$

**Worked example (illustrative).** Two teams at 1500 on a neutral field give $E=0.5$. With $K=20$ and $M=1$, the winner gains $20(1-0.5)=+10$ and the loser drops 10. If a 1700 team beats a 1500 team, $E\approx0.76$, so the favorite gains only about $20(0.24)\approx+4.8$. An expected result carries little information.

CFBD states that its Elo incorporates result, rating difference, scoring margin, and home-field context, but it does not publish the exact expectation curve, $K$, or margin transform. An FBS rating is unchanged when the opponent lacks an Elo rating. Elo is naturally chronological and computationally cheap, but one scalar does not distinguish offense, defense, or pace; it is therefore better as an orthogonal form feature or prior than as the primary totals adjustment.[^9]

## 2. FCS, home field, garbage time, and small samples

| Method | FCS handling | Home field | Garbage time | Small-sample treatment |
|---|---|---|---|---|
| Iterative/additive | Exclude or include separately rated FCS teams. FEI excludes FBS-FCS games because it lacks trusted FCS unit ratings and mismatches can distort possession efficiency.[^10] | Estimate a global $h$ jointly; partially pooled team HFA is possible | Filter before aggregation. FEI excludes specified clock-kill and possession-based blowout states.[^10] | Add priors, pseudo-games, or damping; no universal public SP+ shrinkage constant exists **[unverified]** |
| Ridge | CFBD's public example excludes FBS-FCS plays.[^2] | Include an ordinarily unpenalized global HFA term | Apply a deterministic filter before fitting and run an all-play sensitivity model | Tune penalties using only prior data; stronger shrinkage is commonly selected with partial seasons in CFBD's example.[^2] |
| Crossed random effects | Exclude FCS, estimate individual FCS effects, or use an FCS hierarchy | Fixed global HFA or partially pooled venue effects | Same preprocessing as ridge; a robust likelihood can reduce outlier leverage | ML/REML variance components generate data-dependent partial pooling |
| Bayesian hierarchy | Model FCS teams under subdivision/conference priors or exclude when coverage is incomplete | Put HFA under a population prior; add team deviations only with strong pooling | Deterministic filtering or likelihood weights based on game state | Posterior partial pooling; hyperparameters must be selected or validated historically |
| Elo | Ignore unrated opponents, initialize FCS ratings, or run a complete FBS/FCS graph | Add HFA before calculating expected result | Cap or transform scoring margin | Lower $K$, regress offseason ratings, or use uncertainty-aware Glicko/TrueSkill variants |

Garbage-time rules should be frozen before model comparison. Filtering changes the estimand: removing blowout snaps isolates competitive-state efficiency but discards information about depth, backups, and mismatch domination. For totals, maintain both competitive-state unit ratings and separate depth/blowout indicators if they add walk-forward value.

Random play-level cross-validation is inappropriate because plays from the same game can appear in training and validation. Tune and evaluate chronologically with game- or week-level grouping. This recommendation is statistically standard, but a published FBS comparison quantifying the exact optimism from random play splits was not located **[unverified]**.

## 3. Efficiency and pace

**Summary:** adjust both efficiency and pace, but estimate them as separate processes with different responses and contextual controls.

For efficiency, build opponent-adjusted offense and defense features for EPA/play, success rate, passing EPA, rushing EPA, early-down efficiency, explosiveness, and points/drive. EPA/play is pace-neutral, and adjusted EPA corrects performance for opponent quality rather than play volume. The cfbfastR ratings documentation similarly separates adjusted offense/defense from pace.[^11][^1]

For totals, use a decomposition:

$$
\begin{gathered}
\widehat{T}=
\widehat{N}_{h}\,\widehat{\text{PPD}}_h+
\widehat{N}_{a}\,\widehat{\text{PPD}}_a+
\widehat{\text{STD}} \\[1em]
\begin{array}{rl}
\text{where}\quad \widehat{T}: & \text{predicted combined final score (points)} \\
\widehat{N}_h,\ \widehat{N}_a: & \text{predicted offensive drives for the home and away team} \\
\widehat{\text{PPD}}_h,\ \widehat{\text{PPD}}_a: & \text{predicted offensive points per drive, each against that opponent's defense} \\
\widehat{\text{STD}}: & \text{predicted non-offensive points (defensive and special-teams scores, safeties); optional}
\end{array}
\end{gathered}
$$

Each product is "how many chances times how much per chance." $\widehat{N}$ comes from the pace stack and $\widehat{\text{PPD}}$ from the opponent-adjusted efficiency stack, so the two can be modeled and checked separately.

**Worked example (illustrative).** Home 12.5 drives at 2.4 PPD gives 30.0 points. Away 12.0 drives at 1.9 PPD gives 22.8. Add 1.5 non-offensive points and $\widehat{T}\approx54.3$. If the market sits at 58, the decomposition shows where the gap comes from. Roughly 1.5 more drives per team at the same efficiency would close it, which points to a pace disagreement rather than an efficiency one.

A high total can come from more opportunities, better scoring efficiency, or both. The decomposition makes it auditable which one the model is betting on. The drive counts of the two teams are strongly correlated, because possessions alternate. Model them jointly, or model total game drives and split them, rather than forecasting them independently.

| Pace variable | Meaning | Main contamination |
|---|---|---|
| Plays/game | Scrimmage snaps | Opponent pace, conversions, pass incompletions, game script |
| Possessions/game | Offensive drives | Both teams' drive duration, turnovers, end-half effects |
| Plays/drive | Sustained-drive length | Offensive success and defensive inability to end drives |
| Seconds/play | Time between snaps under a specified clock definition | Play type, clock stoppages, substitutions, data errors |
| Neutral seconds/play | Seconds/play after excluding hurry-up, clock-kill, and blowout states | Filter definition |
| Neutral pass rate | Pass tendency in selected neutral states | Sack/scramble coding and state-selection rules |

A published FBS procedure defines pace as expected possessions against an average-tempo opponent and recursively removes opponent pace. Its motivation is that raw plays/game confounds opponent tempo and run/pass clock effects. For neutral seconds/play, offense should receive the primary timing effect; for possessions/game and plays/game, both teams' pace, efficiency, and drive behavior matter. The relative contribution must be estimated **[unverified]**.[^4]

## 4. Circularity, clustering, and leakage

**Circularity:** opponent adjustment is a jointly estimated system, not a logical loop. Ratings are identified by schedule links, constraints, an intercept, and shrinkage. Massey's least-squares description explicitly uses chains of games and a common normalization to identify relative ratings.[^5]

**Conference clustering:** FBS schedules form dense conference communities with limited interconference edges. Network research on Division I-A football finds that interconference pairings and outcomes govern flow between conference communities. Early conference levels are therefore weakly identified. Mitigations include preseason team priors, partially pooled conference effects, graph-connectivity audits, and honest uncertainty intervals.[^12]

**Leakage:** for a Week 5 target, every aggregate, opponent effect, regularization choice, calibration transform, roster input, and market feature must use information available before the target timestamp. Joining final-season adjusted ratings backward to early games leaks later opponent results even if the target game's outcome is excluded.

Use an append-only snapshot table keyed by season, team, statistic, model version, and `as_of_utc`. At each cutoff: fit only prior data, store team ratings and predictions, then reveal subsequent outcomes. A public weekly ridge replication refits cumulatively through each week, illustrating the correct snapshot direction, although its random internal cross-validation is not ideal for betting-market deployment.[^13]

For opener-to-close modeling, “pregame” is insufficiently precise. Features must exist by the opener timestamp. Injury, weather, depth-chart, and availability reports released afterward are valid only for a later live-update model.

## 5. Preseason priors

### SP+

**Summary:** combine prior SP+ performance with returning or incoming production, recent program history, recruiting/transfers, and coaching-change effects.

Public component weights have changed. For 2024, Connelly described prior SP+ plus returning production as more than half of the projection, recruiting including transfers as about one-third, and recent history as a smaller component. In 2022, prior SP+ plus returning production exceeded two-thirds and recruiting was around one-fifth. By March 2026, Connelly reported that direct recruiting influence had fallen from roughly 20–25% a decade earlier to about 1–2%, while returning production, recent history, and coaching-change effects carried more weight. Therefore, no one historical recipe should be treated as timeless.[^14][^15][^16]

The 2025 returning-production formula weighted offensive-line snaps 40%, WR/TE receiving yards 35%, QB passing yards 22%, and RB rushing yards 3%. Defense used snaps 66%, tackles 19%, and tackles for loss 15%. Incoming transfer production was credited to the destination team, with half-credit for lower-division transfers.[^17]

### FPI

**Summary:** predict offense, defense, and special teams from prior opponent-adjusted unit performance, returning starters, recruiting, and coaching continuity.

ESPN's methodology says prior unit performance is the largest preseason component and uses opponent-adjusted EPA. Returning starters rank second and interact with prior quality; experienced transfer quarterbacks receive partial continuity credit; recruiting uses a multi-year composite; and coaching tenure is included. Current coefficients, non-QB portal treatment, and the precise in-season decay are not public **[unverified]**.[^18]

### Implementable specification

$$
\begin{gathered}
\theta_{i,0}=\alpha+f(\theta_{i,-1:-4})+g(\text{RP}_i)+q(\text{Talent}_i)+r(\text{Portal}_i)+c(\text{Coach}_i) \\[1em]
\begin{array}{rl}
\text{where}\quad \theta_{i,0}: & \text{team } i\text{'s preseason rating for the new season (same units as the in-season rating)} \\
\alpha: & \text{intercept (league-average preseason rating)} \\
\theta_{i,-1:-4}: & \text{team } i\text{'s final ratings from the previous one to four seasons} \\
\text{RP}_i: & \text{position-weighted returning production (share, 0 to 1)} \\
\text{Talent}_i: & \text{roster talent composite (recruiting and transfer ratings)} \\
\text{Portal}_i: & \text{incoming and outgoing transfer production and quality} \\
\text{Coach}_i: & \text{head-coach, coordinator, and scheme continuity indicators} \\
f,g,q,r,c: & \text{mappings learned from past seasons (linear or smooth)}
\end{array}
\end{gathered}
$$

Each term answers one question. $f$ asks how good the team was, and it usually weights last season most while regressing toward $\alpha$. $g$ asks how much of that team is back. $q$ and $r$ ask how good the new players are. $c$ asks whether the system is the same.

Interactions matter. A team with a great prior rating and low returning production should regress harder than one with both high, so $f$ and $g$ are not independent in practice. A product term $\theta_{i,-1}\times\text{RP}_i$ is the simplest way to capture that. The functions are learned mappings, not claimed public SP+ or FPI coefficients.

Estimate separate priors for offense, defense, possession pace, and snap pace. Use nested season-held-out validation: train coefficients through season $s-1$, generate season-$s$ priors, and never tune those weights on season $s$'s outcomes.

## 6. Prior decay

No reproducible current SP+ or FPI week-by-week weight schedule was located. SP+ says early ratings are primarily preseason projections and that preseason information is phased out gradually. Claims that current-season data universally overtakes the prior in Weeks 4–6 are therefore hypotheses, not documented constants **[unverified]**.[^19]

An effective-sample formulation is

$$
\begin{gathered}
\theta_{i,t}=w_{i,t}\theta_{i,0}+(1-w_{i,t})\widehat{\theta}_{i,t},
\qquad
w_{i,t}=\frac{n_0}{n_0+n_{i,t}^{eff}} \\[1em]
\begin{array}{rl}
\text{where}\quad \theta_{i,t}: & \text{blended rating used to forecast games after time } t \\
\theta_{i,0}: & \text{preseason prior (Section 5)} \\
\widehat{\theta}_{i,t}: & \text{current-season opponent-adjusted estimate from games completed before } t \\
w_{i,t}: & \text{weight on the prior; } 0\le w\le1 \\
n_0: & \text{how many observations the prior is "worth" (plays, drives, or games)} \\
n_{i,t}^{eff}: & \text{effective current-season observations for team } i \text{ before } t \text{ (same units as } n_0\text{)}
\end{array}
\end{gathered}
$$

The prior counts as $n_0$ imaginary observations, and the season so far counts as $n^{eff}$ real ones. The blend is their weighted average. With no games played, $n^{eff}=0$, $w=1$, and the rating equals the prior. When the season sample equals $n_0$, the two are weighted equally.

**Worked example (illustrative).** Offense prior $n_0=200$ plays. After three games the team has $n^{eff}=400$ eligible plays, so $w=200/600=1/3$. A prior of $+0.10$ EPA/play and a season estimate of $+0.25$ blend to $\tfrac13(0.10)+\tfrac23(0.25)=+0.20$. A defense with $n_0=400$ in the same week would still weight its prior at $1/2$.

Counting information instead of weeks handles unequal schedules, byes, FCS-heavy starts, and varying snap counts. Tune separate $n_0$ values for offense, defense, possession pace, and seconds/play using nested walk-forward validation. A statistic that stabilizes slowly gets a larger $n_0$.

This blend is also what a normal-normal Bayesian update produces. If the prior has variance $\tau_0^2$ and each observation has noise variance $\sigma^2$, then $n_0=\sigma^2/\tau_0^2$. A confident prior is equivalent to a large $n_0$.

A dynamic alternative is $\theta_{i,t}=\theta_{i,t-1}+\eta_{i,t}$, where the innovation $\eta_{i,t}\sim N(0,\sigma_\eta^2)$ lets the true rating drift during the season. A larger $\sigma_\eta^2$ makes old games count for less. Dynamic sports-rating research selects temporal behavior by one-step-ahead prediction, which aligns with the no-lookahead requirement.[^7]

## 7. Regression and stability

One public FBS analysis using 2012–2022 data reported year-over-year correlations of 0.377 for offensive EPA/play and 0.322 for defensive EPA/play; points per game and points allowed were 0.355 and 0.318. The study is an independent analysis rather than peer-reviewed evidence and does not document a complete opponent-adjustment pipeline, so the exact values should be treated as provisional. They nevertheless support meaningful offseason regression and somewhat stronger shrinkage for defense.[^20]

No adequately documented source was found for consistent year-over-year FBS correlations of neutral seconds/play, possessions/game, plays/drive, success rate, or situation-neutral pass rate across stable clock-rule definitions **[unverified]**. Recompute these using CFBD data:

- Restrict to FBS-vs-FBS and apply frozen competitive-state filters.
- Construct one team-season estimate for each raw and adjusted statistic.
- Compare season $s$ with $s+1$ using Pearson, Spearman, and measurement-error-aware reliability.
- Split pre-2020 and 2021+ eras.
- Evaluate predictive value, not just correlation, in held-out seasons.

For empirical-Bayes shrinkage of a raw team statistic toward the league mean:

$$
\begin{gathered}
B_{ik}=\frac{\tau_k^2}{\tau_k^2+s_{ik}^2},
\qquad
\widetilde{x}_{ik}=B_{ik}x_{ik}+(1-B_{ik})\mu_k \\[1em]
\begin{array}{rl}
\text{where}\quad x_{ik}: & \text{team } i\text{'s observed value of statistic } k \text{ (e.g. success rate)} \\
\mu_k: & \text{league mean of statistic } k \\
\tau_k^2: & \text{true between-team variance of } k \text{ (signal)} \\
s_{ik}^2: & \text{sampling variance of } x_{ik} \text{ (noise; shrinks as sample size grows)} \\
B_{ik}: & \text{reliability, the share of the observed deviation kept; } 0\le B\le1 \\
\widetilde{x}_{ik}: & \text{shrunken estimate}
\end{array}
\end{gathered}
$$

$B$ is the signal share of the total variance. When the sample is noisy relative to real team differences, $B$ is small and the estimate is pulled most of the way back to $\mu_k$. Estimate $\tau_k^2$ as the observed variance across teams minus the average sampling variance, floored at zero.

**Worked example (illustrative).** Success rate: league mean $0.42$, $\tau=0.04$. A team observed at $0.50$ over 150 plays has $s=\sqrt{0.5\cdot0.5/150}\approx0.041$, so $B=0.0016/(0.0016+0.0017)\approx0.49$. The shrunken value is $0.42+0.49(0.08)\approx0.46$. With 600 plays, $s\approx0.020$, $B\approx0.80$, and the estimate is about $0.48$.

Different statistics receive different shrinkage because their reliability differs. $B$ plays the same role as the year-over-year correlation above: a statistic with low season-to-season correlation needs a small $B$ when used as next season's forecast.

## 8. Transfer-portal era

SP+'s roster treatment has evolved. In 2022, incoming transfer recruiting rankings entered with slight weight. By 2023–24, transfer quality was included in recruiting and attrition updates were reflected in returning production. For 2025, incoming player production entered the destination team's returning-production calculation and lower-division transfers received half-credit. By 2026, Connelly reported that direct recruiting weight had fallen to approximately 1–2% and included incoming-transfer quality within recent recruiting.[^15][^16][^21][^14][^17]

Average returning production reported by ESPN fell from 76.7% in 2021 to 62.9% in 2022, 60.2% in 2023, 59.9% in 2024, 53.2% in 2025, and 51.3% in 2026. The 2021 value is affected by pandemic eligibility and is not a clean pre-portal baseline. These figures document increased churn but do not prove that continuity has become unimportant.[^22]

Separate roster features into:

- Incumbent continuity under the same staff and scheme.
- Incoming proven FBS production.
- Lower-division production with translation uncertainty.
- Talent without production.
- Head coach, coordinator, scheme, and quarterback continuity.
- Concentration of continuity at high-leverage positions.

Fit interactions by era and origin level, with strong regularization because the 2021+ sample contains few seasons. Claims that returning production is either obsolete or more valuable in the portal era remain **[unverified]** until tested in expanding-window held-out seasons.

## 9. Two-way crossed team/opponent random effects

### Basic model

**Summary:** estimate focal-team offense and opponent defense as two crossed, partially pooled effects.

This section switches to the **"higher is better" convention**: the defense enters with a minus sign, so a good defense has a **positive** $d^{def}$.

$$
\begin{gathered}
y_{ig}=\beta_0+\beta_H H_{ig}+u_i^{off}-d_j^{def}+\epsilon_{ig} \\[1em]
\begin{array}{rl}
\text{where}\quad y_{ig}: & \text{team } i\text{'s offensive response in game } g \text{ (e.g. EPA/play)} \\
j: & \text{team } i\text{'s opponent in game } g \\
\beta_0: & \text{league-average response (fixed intercept)} \\
\beta_H,\ H_{ig}: & \text{home-field coefficient and venue code } (+1/-1/0) \text{ from } i\text{'s side} \\
u_i^{off}: & \text{team } i\text{'s offensive random effect (} +\text{ = better offense)} \\
d_j^{def}: & \text{team } j\text{'s defensive random effect (} +\text{ = better defense, so it lowers } y\text{)} \\
\epsilon_{ig}: & \text{game-level residual}
\end{array}
\end{gathered}
$$

This is the same structure as the ridge model in Section 1 with $O_i=u_i^{off}$ and $D_j=-d_j^{def}$. The difference is that the team effects are treated as draws from a distribution, and the spread of that distribution is estimated from the data.

The effects are crossed because every team can appear as a focal offense and opposing defense, each offense faces many defenses, and each defense faces many offenses. Crossed models estimate variation associated with both classification variables rather than treating opponents as nested within teams.[^23][^24]

Assume

$$
\begin{gathered}
u_i^{off}\sim N(0,\sigma_{off}^2),
\qquad
d_j^{def}\sim N(0,\sigma_{def}^2),
\qquad
\epsilon_{ig}\sim N(0,\sigma_e^2) \\[1em]
\begin{array}{rl}
\text{where}\quad \sigma_{off}^2: & \text{true variance of offensive quality across teams} \\
\sigma_{def}^2: & \text{true variance of defensive quality across teams} \\
\sigma_e^2: & \text{game-to-game noise variance around a matchup's expected value}
\end{array}
\end{gathered}
$$

All three variances are in squared response units and are estimated from the data by ML or REML. They set how much each team's estimate is shrunk. The estimate for team $i$ is, roughly, its raw opponent-adjusted average multiplied by

$$
\begin{gathered}
\frac{\sigma_{off}^2}{\sigma_{off}^2+\sigma_e^2/n_i} \\[1em]
\begin{array}{rl}
\text{where}\quad n_i: & \text{number of games (observations) for team } i
\end{array}
\end{gathered}
$$

This factor has the same form as the empirical-Bayes $B$ in Section 7. A team with few games, or a unit whose true spread $\sigma^2$ is small next to the noise, is pulled strongly toward zero, which is league average. Teams with larger, stable samples can stay farther from average. If defense varies less across teams than offense does ($\sigma_{def}<\sigma_{off}$), defenses are shrunk harder automatically, with no separate tuning. Mixed models stabilize group effects through a shared population distribution.[^25]

For offense $A$ against defense $B$ at a neutral site ($H=0$):

$$
\begin{gathered}
\widehat{y}_{A,B}=\widehat{\beta}_0+\widehat{u}_A^{off}-\widehat{d}_B^{def} \\[1em]
\begin{array}{rl}
\text{where}\quad \widehat{\beta}_0: & \text{estimated league average} \\
\widehat{u}_A^{off}: & \text{A's estimated offensive effect (BLUP)} \\
\widehat{d}_B^{def}: & \text{B's estimated defensive effect (BLUP; } +\text{ = better defense)}
\end{array}
\end{gathered}
$$

**Worked example (illustrative).** With $\widehat{\beta}_0=0.05$ EPA/play, $\widehat{u}_A=+0.12$, and $\widehat{d}_B=+0.08$, the forecast is $0.05+0.12-0.08=0.09$ EPA/play. A's offense is better than B's defense by 0.04 above the league average.

Opponent-adjusted offense against an average defense is $\widehat{\beta}_0+\widehat{u}_A^{off}$. Expected production by an average offense against defense $B$ is $\widehat{\beta}_0-\widehat{d}_B^{def}$. These conditional random-effect predictions, or BLUPs in a Gaussian frequentist model, combine team evidence with population-level shrinkage.[^26][^27]

### Correlated unit effects

A richer model gives each program a joint offense-defense vector:

$$
\begin{gathered}
\begin{bmatrix}
u_i^{off}\\d_i^{def}\end{bmatrix}
\sim \operatorname{MVN}
\left(
\begin{bmatrix}0\\0\end{bmatrix},
\begin{bmatrix}
\sigma_{off}^2 & \rho\sigma_{off}\sigma_{def}\\
\rho\sigma_{off}\sigma_{def} & \sigma_{def}^2
\end{bmatrix}
\right) \\[1em]
\begin{array}{rl}
\text{where}\quad \operatorname{MVN}: & \text{multivariate normal distribution} \\
u_i^{off},\ d_i^{def}: & \text{the same program's offensive and defensive effects (both } +\text{ = better)} \\
\rho: & \text{correlation between them across programs; } -1\le\rho\le1
\end{array}
\end{gathered}
$$

The diagonal holds the two variances from the basic model. The off-diagonal term is the covariance. With $\rho>0$, programs that are good on offense also tend to be good on defense, which is plausible given shared talent and resources. The practical payoff is borrowing strength across units. If a team's offense is well measured and strongly positive, the model nudges its noisily measured defense upward too, by an amount set by $\rho$.

$\rho$ measures the population association between latent offensive and defensive strength. It can capture shared program resources or complementary game environments but is not causal. A formula such as `y ~ home + (1 | offense_team) + (1 | defense_team)` estimates separate crossed variances but ordinarily not the covariance between the same program's unit effects. In `brms`, group-level terms sharing an ID and grouping factor can be estimated as correlated.[^28][^29]

Estimate the covariance only when historical windows support it. A full covariance matrix can be weakly identified from a sparse early-season sample **[unverified]**.

### Play-level model

$$
\begin{gathered}
\text{EPA}_p=\beta_0+u_{o(p)}^{off}-d_{d(p)}^{def}+
\mathbf{x}_p^T\boldsymbol{\beta}+b_{g(p)}+\epsilon_p \\[1em]
\begin{array}{rl}
\text{where}\quad \text{EPA}_p: & \text{expected points added on play } p \\
o(p),\ d(p),\ g(p): & \text{the offense, defense, and game that play } p \text{ belongs to} \\
\mathbf{x}_p: & \text{vector of play-context controls (e.g. venue, weather, rule-era dummy)} \\
\boldsymbol{\beta}: & \text{fixed coefficients on those controls} \\
b_{g(p)}: & \text{game random intercept, } b_g\sim N(0,\sigma_b^2) \\
\epsilon_p: & \text{play-level residual, } \epsilon_p\sim N(0,\sigma_e^2)
\end{array}
\end{gathered}
$$

$b_g$ absorbs whatever is shared by every play in a game, such as wind, officiating, or a sloppy field. Without it the model treats 70 plays from one game as 70 independent pieces of evidence. That overstates how much it knows about both teams, and it under-shrinks their effects. If the EPA model already values down, distance, field position, and clock state, add only controls that address residual contextual imbalance and demonstrate out-of-sample value.

For success rate:

$$
\begin{gathered}
\text{Success}_p\sim \operatorname{Bernoulli}(\pi_p),
\qquad
\operatorname{logit}(\pi_p)=\ln\frac{\pi_p}{1-\pi_p}=\eta_p=\beta_0+u_{o(p)}^{off}-d_{d(p)}^{def}+
\mathbf{x}_p^T\boldsymbol{\beta} \\[1em]
\begin{array}{rl}
\text{where}\quad \text{Success}_p: & 1 \text{ if play } p \text{ met the success threshold, else } 0 \\
\pi_p: & \text{probability that play } p \text{ is a success} \\
\eta_p: & \text{linear predictor on the log-odds scale} \\
u^{off},\ d^{def}: & \text{offense and defense effects in log-odds (} +\text{ = better for each unit)}
\end{array}
\end{gathered}
$$

The team effects are log-odds effects, not percentage points. Convert back with $\pi=1/(1+e^{-\eta})$. Because the curve is steepest at $\pi=0.5$, the same log-odds effect is worth more percentage points near 50% than near the extremes.

**Worked example (illustrative).** $\beta_0=-0.32$ gives a league success rate of $1/(1+e^{0.32})\approx0.42$. An offense with $u=+0.20$ facing an average defense has $\eta=-0.12$ and $\pi\approx0.47$, which is about +5 percentage points. Against a defense with $d=+0.20$ it returns to 0.42.

`lme4` supports linear and generalized linear mixed models for Gaussian, binomial, and other response families.[^30]

### Points per drive and pace

A Gaussian crossed model is a useful points-per-drive baseline, but drive scoring has a large zero mass and discrete outcomes. Ordinal or hurdle models can represent no score, field goal, touchdown, and exceptional outcomes more faithfully. Published American-football research has used partially regularized ordinal regression for opponent-adjusted team scoring and complementary-unit effects.[^31]

For possessions:

$$
\begin{gathered}
\text{Poss}_{ig}=\beta_0+a_i^{pace}+q_j^{\text{opp-pace}}+
\mathbf{x}_{ig}^T\boldsymbol{\beta}+\epsilon_{ig} \\[1em]
\begin{array}{rl}
\text{where}\quad \text{Poss}_{ig}: & \text{offensive possessions for team } i \text{ in game } g \\
a_i^{pace}: & \text{team } i\text{'s own volume tendency (} +\text{ = more possessions)} \\
q_j^{\text{opp-pace}}: & \text{how opponent } j \text{ changes } i\text{'s possession count (} +\text{ = more)} \\
\mathbf{x}_{ig},\ \boldsymbol{\beta}: & \text{game controls (e.g. overtime, weather, rule era) and their coefficients} \\
\epsilon_{ig}: & \text{residual}
\end{array}
\end{gathered}
$$

Both effects carry a plus sign because pace is not good or bad, only more or less. $a_i^{pace}$ is the focal team's volume tendency. $q_j^{\text{opp-pace}}$ is the opponent's influence through its tempo, drive duration, and possession exchange. A slow, ball-control opponent has negative $q$ and removes possessions from both teams. For neutral seconds/play, offense should ordinarily receive the primary timing effect. For possessions/game, both teams matter.

### Relationship to ridge

The Gaussian crossed model is closely related to ridge:

$$
\begin{gathered}
\min_{\beta_0,\beta_H,u,d}\ \sum_{ig}
\left(y_{ig}-\beta_0-\beta_H H_{ig}-u_i^{off}+d_j^{def}\right)^2
+\lambda_{off}\sum_i(u_i^{off})^2
+\lambda_{def}\sum_j(d_j^{def})^2 \\[1em]
\begin{array}{rl}
\text{where}\quad \text{residual}: & y_{ig} \text{ minus the model's prediction } \beta_0+\beta_H H_{ig}+u_i^{off}-d_j^{def} \\
\lambda_{off},\ \lambda_{def}: & \text{ridge penalties on the offensive and defensive effects}
\end{array}
\end{gathered}
$$

The $+d_j^{def}$ inside the square is the minus sign from the model being subtracted: residual $=y-(\ldots-d)$. With the variances known, maximizing the mixed-model likelihood over $u$ and $d$ gives exactly this objective, with

$$
\begin{gathered}
\lambda_{off}=\frac{\sigma_e^2}{\sigma_{off}^2},
\qquad
\lambda_{def}=\frac{\sigma_e^2}{\sigma_{def}^2} \\[1em]
\begin{array}{rl}
\text{where}\quad \sigma_e^2: & \text{residual (noise) variance} \\
\sigma_{off}^2,\ \sigma_{def}^2: & \text{between-team variance of offensive and defensive effects}
\end{array}
\end{gathered}
$$

The penalty is a noise-to-signal ratio. When game noise is large relative to real team differences, the penalty is large and the ratings shrink hard.

**Worked example (illustrative).** Team-game EPA/play with $\sigma_e=0.15$ and $\sigma_{off}=0.08$ gives $\lambda_{off}=0.0225/0.0064\approx3.5$. Each offense's rating is shrunk as if it carried about 3.5 extra games of league-average performance.

The equality holds for a plain sum of squares. Libraries that divide the loss by $n$, or standardize columns (scikit-learn, glmnet), rescale $\lambda$. That is why the relationship is often written $\lambda\propto\sigma_e^2/\sigma^2$, and why CFBD's 150–200 range is not comparable to this number.

Ridge tunes penalties directly; the mixed model estimates variance components by ML or REML and derives pooling from them. Research directly connects random-effect/error variances to ridge penalties. REML accounts for fixed-effect estimation when estimating variance components, but comparisons across different fixed-effect structures should rely on ML or predictive validation rather than raw REML likelihoods.[^32][^33][^34]

### Preseason-informed effects

A zero-centered random effect shrinks every team toward national average. Replace it with team-specific preseason means:

$$
\begin{gathered}
u_{i,0}^{off}\sim N(\mathbf{z}_{i,O}^T\boldsymbol{\gamma}_O,\tau_O^2),
\qquad
d_{i,0}^{def}\sim N(\mathbf{z}_{i,D}^T\boldsymbol{\gamma}_D,\tau_D^2) \\[1em]
\begin{array}{rl}
\text{where}\quad u_{i,0}^{off},\ d_{i,0}^{def}: & \text{team } i\text{'s season-start offensive and defensive effects (both } +\text{ = better)} \\
\mathbf{z}_{i,O},\ \mathbf{z}_{i,D}: & \text{preseason covariate vectors: prior ratings, returning and incoming production, talent, staff continuity} \\
\boldsymbol{\gamma}_O,\ \boldsymbol{\gamma}_D: & \text{coefficients mapping covariates to a prior mean, fit on past seasons} \\
\tau_O,\ \tau_D: & \text{unexplained team spread left after the covariates}
\end{array}
\end{gathered}
$$

The only change from the basic model is the center of the distribution. Each team now shrinks toward $\mathbf{z}^T\boldsymbol{\gamma}$, its own preseason projection, instead of toward 0. A top program with two games of noisy data stays near its projection rather than collapsing toward average. $\tau$ here is smaller than $\sigma_{off}$ in the basic model, because the covariates already explain part of the team-to-team spread. That residual spread is what $\tau$ measures.

This is the model-based version of the $n_0$ blend in Section 6, with $n_0\approx\sigma_e^2/\tau^2$ per observation.

A dynamic extension is

$$
\begin{gathered}
\begin{bmatrix}
u_{i,t}^{off}\\d_{i,t}^{def}\end{bmatrix}
=
\begin{bmatrix}
u_{i,t-1}^{off}\\d_{i,t-1}^{def}\end{bmatrix}
+\boldsymbol{\eta}_{i,t},
\qquad
\boldsymbol{\eta}_{i,t}\sim \operatorname{MVN}(\mathbf{0},\mathbf{Q}) \\[1em]
\begin{array}{rl}
\text{where}\quad t: & \text{week index} \\
\boldsymbol{\eta}_{i,t}: & \text{2-vector of week-to-week changes in team } i\text{'s true offense and defense} \\
\mathbf{Q}: & 2\times2 \text{ covariance of those changes: } \begin{bmatrix} q_{off}^2 & q_{od}\\ q_{od} & q_{def}^2\end{bmatrix}
\end{array}
\end{gathered}
$$

Each week, a team's true offense and defense take a random step, and the data then pull the estimate toward what was observed. This is a Kalman-filter setup. The diagonal of $\mathbf{Q}$ sets how fast each unit is allowed to change. $\mathbf{Q}=\mathbf{0}$ gives the static model, where every past game counts equally. A large $\mathbf{Q}$ makes the model chase the last few games. The off-diagonal $q_{od}$ lets an injury or scheme change move both units together.

Estimate $\mathbf{Q}$ only on historical training windows, by one-step-ahead predictive likelihood.

### FCS treatment and validation

Options are: exclude FBS-FCS games; estimate individual FCS effects with adequate FCS coverage; or assign FCS teams subdivision/conference priors. A hierarchical prior such as $u_i^{off}\sim N(\mu_{s(i),O},\tau_{s(i),O}^2)$, where $s(i)$ is team $i$'s subdivision or FCS conference and $\mu_{s,O}$, $\tau_{s,O}$ are that group's mean and spread, is preferable to treating every FCS opponent as identical, but only if group parameters use pre-cutoff information.

Mixed-model validation distinguishes future games for previously observed teams from predictions for entirely new clusters. Existing-team forecasts may use historical BLUPs; new-team forecasts must use fixed effects and population or covariate-informed priors. Fit through cutoff $t$, save effects and predictions, score later games, and never split random plays across training and validation.[^35]

## 10. Model comparison

No method dominates every objective. Iterative adjustment is most transparent, ridge is the strongest low-complexity production baseline, crossed random effects estimate unit-specific pooling automatically, Bayesian hierarchy is most flexible for priors and uncertainty, and Elo is cheapest for sequential updates. Which wins for FBS totals or line movement remains **[unverified]** until identical timestamped folds are compared.

### Structural differences

| Method | Team representation | Opponent adjustment | Shrinkage | Time treatment | Uncertainty |
|---|---|---|---|---|---|
| Iterative/additive | Offense and defense point estimates | Repeatedly remove current opponent estimates | Added via damping, pseudo-games, or priors | Refit through each cutoff; optional recency weights | Usually absent unless bootstrapped |
| Ridge | Penalized offense and defense coefficients | Joint offense/defense design matrix | Tuned $\lambda$, optionally separate by unit | Rolling refits; decay supplied manually | Often treated as point estimates |
| Crossed random effects | Population-distributed offense and defense effects | Focal-team and opponent effects in one likelihood | ML/REML variance components and BLUP partial pooling | Static unless refitted or extended dynamically | Random-effect and predictive uncertainty available |
| Bayesian hierarchy | Posterior distributions for units, groups, and time states | Joint multilevel likelihood | Explicit priors and posterior pooling | Dynamic state evolution can be native | Full posterior propagation |
| Elo | Usually one overall scalar | Expected result from rating difference | $K$, initialization, and offseason regression | Native sequential updating | Ordinary Elo lacks uncertainty |

### Pros, cons, and roles

| Method | Does best | Does worse | Recommended role |
|---|---|---|---|
| Iterative/additive | Transparent average-opponent interpretation; easy manual auditing; natural for recursive pace | Sparse-schedule stability, uncertainty, and automatic shrinkage | Sanity check and transparent pace benchmark; published FBS recursive pace offers a concrete implementation.[^4] |
| Ridge | Speed, numerical stability, reproducibility, and direct control over shrinkage | Natural uncertainty, correlated unit effects, and rich priors | First production baseline; CFBD supplies public coding details and working code.[^2][^6] |
| Crossed random effects | Separate offense/defense reliability, automatic partial pooling, team/opponent clustering | Boundary variance estimates, static behavior unless extended, and distributional assumptions | Preferred second-stage challenger to ridge |
| Bayesian hierarchy | Team-specific priors, FBS/FCS hierarchies, correlated unit effects, dynamic states, uncertainty propagation | Computation, prior sensitivity, convergence checks, and weak identification | Long-term architecture after simpler models establish benchmarks |
| Elo | Cheap online updates, chronological integrity, and intuitive surprise-based movement | Unit separation, pace representation, and calibrated uncertainty | Orthogonal form feature or prior, not primary totals adjustment |

### Crossed random effects versus ridge

Independent Gaussian random effects imply quadratic shrinkage, so these methods are close relatives. Ridge asks which penalty predicts best; the mixed model asks how much offense, defense, and residual variance the observed training data support. The variance ratio corresponds approximately to the ridge penalty.[^32]

Crossed effects are better when offense and defense need different pooling, team/opponent clustering must be represented explicitly, and sparse-team uncertainty matters. Ridge is better when fitting speed, direct penalty control, robustness to variance-boundary estimates, and simple weekly deployment dominate. Do not assume REML pooling is more predictive: compare both on identical outer folds.

### Crossed random effects versus Bayesian hierarchy

The two can encode essentially the same likelihood. A frequentist mixed model estimates variance components by ML/REML and returns BLUPs; a Bayesian model places priors on coefficients and variance components and integrates over their posterior uncertainty. Generalized mixed models stabilize group estimates through a shared mixing distribution, while Bayesian software can estimate correlated group effects under explicit priors.[^28][^25]

The crossed mixed model is the cleaner diagnostic baseline. Bayesian hierarchy is better when preseason information must create team-specific prior means, FCS teams borrow strength across levels, ratings evolve every week, or uncertainty in pace and efficiency must propagate into a total. Bayesian flexibility can underperform if priors, covariance parameters, or dynamic states are weakly identified **[unverified]**.

### Ridge versus iterative adjustment

Iterative adjustment alternates offense and opponent estimates; ridge solves the coupled system under an explicit penalty. Ridge is usually more stable on collinear or sparse schedules. Iterative adjustment is easier to inspect manually and maps naturally to recursive average-opponent pace definitions.[^4]

Use iterative ratings as a logic and sign-convention check. Use ridge as the production baseline. Large disagreement should trigger audits of schedule connectivity, FCS handling, observation weights, centering, and feature signs.

### Elo versus unit models

Elo updates overall strength directly from result surprise. CFBD confirms that rating difference, result, scoring margin, and home context enter its implementation, though exact parameters are unpublished. Ridge, crossed effects, and hierarchical models instead explain strength through offense, defense, and pace.[^9]

Elo is better for inexpensive game-by-game updating and broad form. Unit models are better for totals because equally rated teams can produce radically different scoring environments. Elo should supplement the efficiency and pace stack rather than replace it.

### Method by problem

| Problem | Best starting method | Reason | Upgrade path |
|---|---|---|---|
| Opponent-adjusted EPA/play | Ridge | Fast, stable, reproducible public example | Robust crossed or dynamic Bayesian unit effects |
| Team-game success rate | Crossed Gaussian baseline or binomial GLMM | Direct offense/opponent decomposition and separate variances | Bayesian binomial hierarchy with preseason means |
| Neutral seconds/play | Ridge or crossed Gaussian | Continuous response and clear focal-offense effect | Dynamic timing effect with rule-season intercepts |
| Possessions/game | Iterative pace plus crossed Gaussian | Transparent average-opponent pace plus focal/opponent decomposition | Joint Bayesian possessions and drive-length model |
| Points/drive | Crossed Gaussian baseline | Easy initial unit decomposition | Ordinal or hurdle hierarchy for zero-heavy discrete scores[^31] |
| Early-season ratings | Preseason-informed crossed effects | Automatic pooling toward team-specific expectation | Dynamic multivariate Bayesian model |
| Opener-to-close movement | Regularized downstream regression using frozen ratings | Simplicity aids attribution and guards overfit | Nonlinear model only after calibration and residual audits |
| Real-time updating | Elo | Native sequential operation | Dynamic filter with separate offense, defense, and pace |

### Fair evaluation

Hold raw data, garbage-time rules, FCS handling, feature timestamps, and downstream target models constant. Otherwise, the comparison measures pipeline changes rather than adjustment methods.

At every historical cutoff, store adjusted features, uncertainty where available, predicted total, predicted line movement, de-vigged market benchmark, effective sample size, and feature-availability flags. Evaluate:

- Realized-total MAE and RMSE, plus incremental error relative to the de-vigged closing total.
- Error and calibration for $\text{ActualTotal}-\text{CloseTotal}$, the realized total minus the de-vigged closing total (points; $+$ means the game went over the close).
- Directional accuracy and MAE for $\text{Close}-\text{Open}$, the closing total minus the opening total (points; $+$ means the market moved up), conditional on predicted move size.
- Performance after vig and realistic line availability.
- Season-by-season stability, early/late splits, FCS exposure, conference connectivity, and garbage-time sensitivity.

Use nested walk-forward selection and an untouched outer season or rolling outer fold. Mixed-model validation must distinguish future observations for known teams from entirely unseen clusters, because unseen teams cannot use fitted random effects. Select a method only for repeatable incremental value over the de-vigged market and ridge baseline—not in-sample fit or visually pleasing rankings.[^35]

## Evidence matrix

| Method | Handles small samples? | Leakage risk | Out-of-sample evidence | Source |
|---|---|---|---|---|
| Iterative/additive | Only with priors, damping, or pseudo-games | High if final-season opponent ratings are backfilled | No public FBS totals/CLV walk-forward comparison located **[unverified]** | Massey method[^5]; recursive pace[^4] |
| Ridge offense/defense/HFA | Yes through L2 shrinkage | High if penalties or ratings use future games | Reproducible implementation; no de-vigged-market OOS test in source | CFBD method[^2]; code[^6] |
| Crossed random effects | Yes through variance-component partial pooling | High if BLUPs are generated from full-season data | General mixed-model methodology is established; direct FBS betting comparison not found **[unverified]** | Mixed models[^25]; CV distinctions[^35] |
| Bayesian hierarchical/dynamic | Yes through priors and posterior pooling | Moderate to high if priors/hyperparameters use test seasons | Dynamic ratings use one-step prediction; direct CFB market evidence not found **[unverified]** | Dynamic ratings[^7] |
| Elo | Yes through initialization, $K$, and regression | Low when strictly sequential | CFBD ratings exist, but exact method and market evidence are unpublished | CFBD Elo[^9] |
| SP+ preseason prior | Yes through historical and roster features | High if revised roster/rating data are backfilled | Creator reported 58% ATS in the first five weeks of 2019; not independent long-run validation[^36] | SP+ descriptions[^15][^14] |
| FPI preseason prior | Yes through prior unit performance and continuity | Moderate; coefficients and decay are undisclosed | Components selected for prediction, but public market-relative OOS tables were not found **[unverified]** | ESPN methodology[^18] |
| Adjusted pace | Yes with recursion plus a preseason prior | High if final-season possession data are backfilled | Published FBS procedure, not evaluated against totals markets | Pace method[^4] |

## Implementation order

1. **Build immutable timestamped snapshots.** Version plays, filters, rosters, ratings, priors, and market observations by `as_of_utc`; reject any feature timestamp later than the prediction timestamp.
2. **Fit ridge unit baselines.** Produce offense/defense/HFA estimates for EPA, success rate, drive efficiency, and pace using nested walk-forward tuning.
3. **Build a separate possession stack.** Forecast drives, plays/drive, neutral seconds/play, and points/drive instead of relying on raw plays/game.
4. **Challenge ridge with crossed effects.** Fit independent offense/opponent random effects first, then add preseason-informed means. Add correlated units only if outer-fold results improve.
5. **Add dynamic Bayesian states last.** Introduce time evolution, FCS hierarchies, and full uncertainty propagation one layer at a time, requiring each layer to beat the previous model and de-vigged market baseline.

---

## References

1. [What Is EPA in College Football? Expected Points Added ...](https://cfbfastr.sportsdataverse.org/articles/college-football-expected-points-model-fundamentals-part-iv.html) - EPA (expected points added) is the change in expected points across a single play. How it is calcula...

2. [CFBD Blog - Opponent Adjusted Stats using Ridge Regression](https://radsportsanalytics.com/blog/opponent-adjusted-stats-ridge-regression/) - "The biggest variable in football is the fact that each team plays a different schedule against team...

3. [5.1 - Ridge Regression | STAT 897D](https://online.stat.psu.edu/stat857/node/155/)

4. [5.2 Dynamic Bayesian...](https://arxiv.org/html/2207.13747v1)

5. [Massey Ratings Descriptionmasseyratings.com › theory](https://masseyratings.com/theory/ls.htm)

6. [GitHub - jbuddavis/opponentAdjustedStats](https://github.com/jbuddavis/opponentAdjustedStats) - Contribute to jbuddavis/opponentAdjustedStats development by creating an account on GitHub.

7. [Dynamic Rating of Sports Teams](https://academic.oup.com/jrsssd/article-pdf/49/2/261/49931241/jrsssd_49_2_261.pdf) - Summary. We consider the problem of dynamically rating sports teams on the basis of categorical outc...

8. [The role of passing network indicators in modeling football outcomes: an application using Bayesian hierarchical models](https://link.springer.com/article/10.1007/s10182-021-00411-x) - ## Abstract

Passes are undoubtedly the more frequent events in football and other team sports. Pass...

9. [Elo ratings | CFBD](https://api.collegefootballdata.com/elo-ratings) - Documentation and API reference for the College Football Data API.

10. [Talking Tech: Calculating Elo Ratings for College Football](https://blog.collegefootballdata.com/talking-tech-elo-ratings/) - Given the Elo rating of a team as well as its opponent, this function will calculate the team's prob...

11. [Load college football season power ratings from the ... - cfbfastR](https://cfbfastr.sportsdataverse.org/reference/load_cfb_ratings.html) - Loads season-end team power ratings from the cfbfastR modeling suite – one row per team with overall...

12. [mucha.dvi](https://www.math.ucla.edu/~mason/papers/bcsmonthly.pdf)

13. [Ridge Regression Adjusted Statistics](https://jfking50.github.io/sports%20analytics/adjust-stats/) - The idea for this post started off as essentially a replication of this post but using R and Tidymod...

14. [2026 college football SP+ rankings for all 138 FBS teams - ESPN](https://www.espn.com/college-football/story/_/id/48306284/2026-college-football-sp+-rankings-138-fbs-teams) - Combine last year's SP+ ratings and adjustments based on current returning production numbers, and y...

15. [Post-spring college football SP+ rankings and takeaways - ESPN](https://www.espn.com/college-football/insider/story/_/id/40186201/college-football-2024-post-spring-sp+-rankings-takeaways) - With the 2024 portal cycle and spring football in the books, it's time to look at the updated SP+ ra...

16. [College football SP+ preseason projections for 2022](https://www.espn.com/college-football/insider/story/_/id/33244513/college-football-sp+-preseason-projections-2022) - We take our first look at SP+ projections for the coming season, ranking every team from No. 1 to No...

17. [College football 2025 returning production for all 136 FBS ...](https://www.espn.com/college-football/insider/story/_/id/43952974/2025-college-football-returning-production-rankings-136-teams) - What teams have the most (and least) coming back, and what will it all mean next season?

18. [Introducing ESPN's Preseason FPI 1.0](https://www.espn.com/blog/statsinfo/post/_/id/114555/introducing-espns-preseason-fpi-1-0) - It's never too early to look ahead to the college football season. Our first iteration of preseason ...

19. [2026 college football SP+ rankings for all 138 FBS teams](https://www.espn.com/college-football/story/_/id/49868647/2026-college-football-sp+-rankings-all-138-fbs-teams) - The updated SP+ rankings, plus strength of schedule and résumé SP+, after this weekend's results.

20. [EPA, Point Differential, and Over-Analytics](https://skolarshipanalytics.wordpress.com/2023/12/01/epa-point-differential-and-over-analytics/) - Every week, statistics nerds like me release chart after chart full of complicated metrics with name...

21. [College football's post-spring SP+ rankings and takeaways - ESPN](https://www.espn.com/college-football/insider/story/_/id/37720386/college-football-post-spring-sp+-rankings-takeaways) - Bill Connelly is a writer for ESPN. Recent recruiting. It is determined by the past few years of rec...

22. [Final preseason college football SP+ rankings, takeaways for 2026](https://www.espn.com/college-football/story/_/id/49593338/final-preseason-college-football-sp+-rankings-takeaways-2026) - Bill Connelly looks at what the SP+ projections and production numbers mean heading into the season.

23. [Chapter 11 Multilevel Generalized Linear Models](https://bookdown.org/roback/bookdown-BeyondMLR/ch-GLMM.html) - An applied textbook on generalized linear models and multilevel models for advanced undergraduates, ...

24. [Nested and crossed random effects in lme4 - Stats & bats](https://www.muscardinus.be/statistics/nested.html) - A class groups a number of students and a school groups a number of classes. There is a one-to-many ...

25. [Generalized Linear Mixed Models](https://academic.oup.com/book/11531/chapter/160310517) - Abstract. This chapter gives an introduction to linear and generalized linear mixed models. The prim...

26. [7 Linear mixed models - Quantitative Methods for Linguistic Data](https://people.linguistics.mcgill.ca/~morgan/qmld-book/lmem.html) - Quantitative Methods for Linguistic Data

27. [Module 1B Linear Mixed Models](https://bookdown.org/epeterson_2010/bios526_book/Module_1B_LMM.html)

28. [Set up a model formula for use in brms — brmsformula](https://paulbuerkner.com/brms/reference/brmsformula.html) - All group-level terms sharing the same ID will be modeled as correlated. correlations between the co...

29. [Advanced Bayesian Multilevel Modeling with the R Package ...](https://journal.r-project.org/articles/RJ-2018-017/index.html) - Group-level terms with the same ID will then be modeled as correlated if they share same grouping fa...

30. [Linear Mixed-Effects Models using Eigen and S4 • lme4](https://lme4.github.io/lme4/index.html) - Fit linear and generalized linear mixed-effects models. The models and their components are represen...

31. [Partially Regularized Ordinal Regression to Adjust Teams' Scoring ...](https://arxiv.org/html/2506.03057v1)

32. [Estimation of variance components, heritability and the ridge penalty in high-dimensional generalized linear models](https://www.tandfonline.com/doi/full/10.1080/03610918.2019.1646760) - For high-dimensional linear regression models, we review and compare several estimators of variances...

33. [Estimating Parameters in Linear Mixed-Effects Models](https://www.mathworks.com/help/stats/estimating-parameters-in-linear-mixed-effects-models.html) - The two most commonly used approaches to parameter estimation in linear mixed-effects models are max...

34. [[PDF] Testing random effects](https://pages.stat.wisc.edu/~ane/st572/notes/lec21.pdf)

35. [Cross-validating mixed-effects models](https://cran.r-project.org/web/packages/cv/vignettes/cv-mixed.html)

36. [Preseason SP+ college football rankings: Alabama back at No. 1](https://www.espn.com/college-football/story/_/id/28687236/preseason-sp+-college-football-rankings-alabama-back-no-1) - Last week we published my initial returning production rankings for 2020, based on players graduatin...


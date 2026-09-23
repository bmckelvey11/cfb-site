# Weekly PPP and pace ratings vs the mean and the Bovada open (Release B)

**Question.** Do weekly, as-of opponent-adjusted team points-per-possession and pace
ratings forecast FBS game totals better than simpler baselines — an unadjusted
season-to-date version and a pooled train mean — on seasons they were not tuned on? And how
do they compare with the Bovada open?

**Answer.** Yes against both baselines, not against the open. On 2,618 FBS-vs-FBS games
from 2021–2025 where both teams had played at least three FBS games, the ridge rating's
total is 1.14 points closer than the raw version and 0.84 points closer than the train mean
(mean absolute error; both intervals clear of zero, every season the same sign, unchanged
at half and double the tuned penalty). It is 0.33 points further from the total than the
Bovada open label, every season. Its disagreement with the open carries no detectable
information about where the total lands.

## Summary

- **What was built.** Each week, every FBS team gets three ratings fit only on games
  already played: offense $O$ and defense $D$ (points per possession above or below league
  average) and pace $P$ (possessions per game above or below average). Two teams' ratings
  combine into a forecast of the game total ([exactly what is predicted](#what-we-are-predicting)).
  `ridge_v1` adjusts for opponents and pulls thin samples toward average
  ([how ridge works](#how-ridge-regression-works)); `raw_v1` does neither.
- **Scoreboard.** Average miss (MAE) on the same 2,618 games: Bovada open 12.60, ridge
  12.94, train mean 13.78, raw 14.08 points.
- **Beats both baselines.** Ridge is 1.14 points closer than raw and 0.84 closer than the
  train mean, in all five seasons, and still at half or double the penalty.
- **Trails the open.** Ridge is 0.33 points further from the total in all five seasons,
  and its disagreement with the open carries no detectable information (slope $b$ = 0.03,
  −0.13 to 0.20; a weak null, see the last section).
- **Weak early.** When a team has fewer than three games, ridge cannot be told apart from
  the mean, trails the open by 0.65 and runs 1.36 points low. Priors (step 4) are the fix
  to test.
- **Fitted values, at season end.** League average is about 2.2 points per possession and
  11.5–12.1 possessions per team. The home edge is worth 2.5–4.2 points of margin (larger
  in early-season fits) and cancels in the total. One standard deviation of a team's offense or defense rating is about 0.45 points
  per possession, roughly 5 points a game ([Fitted coefficients](#fitted-coefficients)).
- **Not a betting result.** This measures forecast error only. There is no price and no
  capture time, and no wager is graded.

Reproduce:

```text
python -m scripts.weekly_ratings_eval --tune-seasons 2014-2019 --score-seasons 2021-2025
python -m scripts.weekly_ratings_coefs
```

Scripts: [`scripts/weekly_ratings.py`](../scripts/weekly_ratings.py) (fits),
[`scripts/weekly_ratings_eval.py`](../scripts/weekly_ratings_eval.py) (tuning and scoring),
[`scripts/weekly_ratings_coefs.py`](../scripts/weekly_ratings_coefs.py) (the coefficient
tables and the encompassing intercept, read from the two outputs below).
Tests: [`tests/test_weekly_ratings.py`](../tests/test_weekly_ratings.py). Design and
equations: [`superpowers/specs/2026-09-22-weekly-ratings-design.md`](superpowers/specs/2026-09-22-weekly-ratings-design.md).
Outputs (gitignored): `data/processed/ratings/weekly_ratings_eval.json` (every number
below, input and code sha256s) and `weekly_ratings_snapshots.csv` (39,924 team rows).

## What we are predicting

The output is one number per game: the forecast **full-game points total**,
$\widehat{\text{Total}}_g$. That is both teams' final points added together, overtime
included, the same quantity a totals (over/under) line is set on.

- **Which games.** FBS vs FBS, regular season, week 2 onward. Scored on 2021–2025.
- **When.** Once a week, frozen at that week's first kickoff. Every game that week, from
  the first midweek game to the last Saturday game, uses that one snapshot.
- **From what.** Only this season's completed FBS-vs-FBS games before the cutoff: each
  team's regulation points and regulation possessions, who the opponent was, and the venue.
  It uses no previous seasons, rosters, injuries, weather or betting market.
- **Not predicted.** The winner, the margin or spread, whether the total goes over the
  open, or any probability. The model implies each team's regulation points on the way, but
  it is scored only on its miss against the actual total, $|\widehat{\text{Total}}_g-\text{Total}_g|$.

The regressions never fit the total directly. They fit two smaller targets, then multiply,
because points = possessions × points per possession:

| Step | Target it fits | One row is | Code |
| --- | --- | --- | --- |
| Offense and defense | $y_{ig}$: a team's regulation points ÷ its regulation possessions | one team in one game (two rows per game) | `fit_ppp()`, weighted by possessions |
| Pace | $N_g$: both teams' regulation possessions ÷ 2 | one game | `fit_pace()` |
| Total | $\widehat{\text{Total}}_g$: possessions × both teams' rates + average overtime points | one upcoming game | `forecast_total()` |

The split lets opponent adjustment work separately on how fast a team plays and how
efficiently it scores. Each part has its own amount of noise, so each gets its own penalty.

**A worked game.** Navy vs Army, 2025 week 16, at a neutral site ($H=0$). It is the only
game forecast from the 2025 last-cutoff snapshot used in the
[coefficient tables](#fitted-coefficients). It was picked for that reason, not because it
is typical. Ratings after 10 games each:

| Rating | Navy | Army |
| --- | ---: | ---: |
| $O$ | +0.317 | −0.037 |
| $D$ | +0.166 | −0.016 |
| $P$ | −0.508 | −1.271 |

With $\mu=2.262$, $\nu=11.508$ and $c_t=0.617$:

1. Possessions: $\widehat{N}=11.508-0.508-1.271=9.73$ per team. That is 1.8 below average,
   because both teams play slowly.
2. Navy's rate is $\mu+O_{\text{Navy}}+D_{\text{Army}}=2.262+0.317-0.016=2.563$ points per
   possession. Army's is $2.262-0.037+0.166=2.391$.
3. Regulation points: Navy $9.73\times2.563=24.9$, Army $9.73\times2.391=23.3$.
4. Total: $9.73\times(2.563+2.391)+0.617=48.8$.

The raw forecast was 49.0 and the Bovada open 37.5. The game finished 17–16, a total of 33,
on 8 possessions each at 2.13 and 2.00 points per possession. Ridge missed by 15.8, worse
than its 12.9 average miss. The open missed by 4.5. The ratings had the direction of pace
right but not the size. They see only this season's points and possessions, and the open
can price anything else.

## How ridge regression works

**The problem.** Each team-game row says: this team scored $y$ points per possession
against this opponent at this venue. We want one offense number and one defense number per
team that explain all the rows at once. An offense then gets credit only for scoring beyond
what each opponent's defense usually allows, and a defense likewise. Choosing every $O$,
$D$, $\mu$ and $h$ to make the squared misses as small as possible is ordinary least
squares (OLS). That is the opponent adjustment.

OLS alone fails here in two ways:

1. **Noise.** After two games, a team that scored 56 on a bad defense gets an extreme
   rating. OLS takes every game at face value and cannot tell that two games are a thin
   sample.
2. **No unique answer.** Adding 0.1 to every offense and subtracting 0.1 from $\mu$ fits
   exactly as well. Early in the season, some groups of teams have no opponents in common
   at all. OLS has no way to choose among tied answers.

**Ridge's fix: a charge for every rating away from 0.** Ridge minimizes the same squared
misses plus $\lambda$ times the sum of the squared team ratings. 0 is league average, so a
rating moves away from average only as far as the evidence pays for. Among tied answers,
the one centred on 0 is cheapest, so the answer is unique. $\mu$, $h$ and $\nu$ are not
charged: they are league-wide, every game informs them, and charging them would bias the
league level.

**The phantom-possession picture.** For one team taken alone, the ridge answer has a
closed form:

$$
\begin{gathered}
\widehat{O}_i=\frac{n_i\,\bar{r}_i+\lambda_{\text{PPP}}\times0}{n_i+\lambda_{\text{PPP}}} \\[1em]
\begin{array}{rl}
\text{where}\quad \widehat{O}_i: & \text{team } i\text{'s ridge offense rating, points per possession} \\
n_i: & \text{team } i\text{'s regulation possessions before the cutoff} \\
\bar{r}_i: & \text{possession-weighted mean of } y_{ig}-\mu-D_{j(g)}-hH_{ig}\text{: scoring beyond what each opponent allows} \\
\lambda_{\text{PPP}}: & \text{penalty, possessions; } 40 \\
0: & \text{the league-average residual the penalty pulls toward}
\end{array}
\end{gathered}
$$

Read it as an average of the team's own $n_i$ possessions and $\lambda_{\text{PPP}}=40$
phantom possessions played at exactly league average. Early in the season the phantoms
dominate; late, the real possessions do. Defense works the same way. Pace does too, with
$\lambda_{\text{pace}}=8$ phantom league-average games. At 11.9 possessions a game (the
season-end $\nu$, averaged over 2021–2025), the weight on a team's own data is:

| Games played | Offense and defense | Pace |
| ---: | ---: | ---: |
| 1 | 0.23 | 0.11 |
| 3 | 0.47 | 0.27 |
| 6 | 0.64 | 0.43 |
| 11 | 0.77 | 0.58 |

So a team that is truly 1 point per possession better than average rates about +0.47
after three games and +0.77 at season end. The real fit is not isolated: each team's
$\bar{r}_i$ depends on its opponents' ratings, which are shrunk too. So the table is a
guide, not the exact answer. `fit_ppp()` and `fit_pace()` solve the joint problem exactly:

$$
\begin{gathered}
\widehat{\beta}=\left(X^\top WX+\Lambda\right)^{-1}X^\top Wy \\[1em]
\begin{array}{rl}
\text{where}\quad \widehat{\beta}: & \text{all coefficients stacked: } \mu,\ h,\ \text{every } O_k,\ \text{every } D_k \text{ (pace: } \nu \text{ and every } P_k\text{)} \\
X: & \text{one row per team-game: 1 for } \mu\text{, } H_{ig} \text{ for } h\text{, 1 in team } i\text{'s } O \text{ column, 1 in opponent } j\text{'s } D \text{ column} \\
W: & \text{diagonal row weights: } w_{ig} \text{ possessions (pace: 1 per game)} \\
y: & \text{row targets: } y_{ig} \text{ (pace: } N_g\text{)} \\
\Lambda: & \text{diagonal penalty: 0 for } \mu \text{ and } h\text{, } \lambda_{\text{PPP}} \text{ for each team rating (pace: 0 for } \nu\text{, } \lambda_{\text{pace}} \text{ for each } P_k\text{)}
\end{array}
\end{gathered}
$$

With $\Lambda=0$ this is weighted OLS, which fails for the two reasons above; the $\Lambda$
term is the whole of "ridge". `_solve()` hands that system to `np.linalg.lstsq`, which also
copes when $h$ has no data yet (an early fit with only neutral-site games).

- **Choosing $\lambda$.** Too small and ratings chase noise; too large and every team looks
  average. Each $\lambda$ was chosen by predicting the next week's games on 2014–2019 only,
  trying six values ([loss curve](#fitted-coefficients)), then frozen for 2021–2025.
- **It is a prior in disguise.** Ridge gives the same answer as a Bayesian estimate with a
  normal prior centred on league average for every team. Here that centre is 0 for every
  team every season. Step 4 (priors) moves it to each team's previous-season rating with
  the same machinery.
- **`raw_v1` has neither part.** There is no opponent term and no penalty: a team's plain
  average minus the league average, at full strength after one game. The ridge − raw gap of
  1.14 points is what adjustment and shrinkage buy together.

## Model and variables

Every equation below is fit or evaluated at one weekly cutoff $t$. Each block declares its
symbols. The [name table](#symbols-in-code-and-outputs) after the last block maps each
symbol to its name in code, the snapshot CSV and the eval JSON.

### Offense and defense

$$
\begin{gathered}
\min_{\mu,\,h,\,O,\,D}\;\sum_{(i,g)\in F_t} w_{ig}\left(y_{ig}-\mu-O_i-D_{j(g)}-hH_{ig}\right)^2+\lambda_{\text{PPP}}\sum_{k}\left(O_k^2+D_k^2\right) \\[1em]
\begin{array}{rl}
\text{where}\quad F_t: & \text{team-game rows of season } s \text{ with kickoff strictly before cutoff } t \text{, gated games removed} \\
y_{ig}: & \text{team } i\text{'s regulation points (Q1–Q4 line scores) per regulation possession in game } g \\
w_{ig}: & \text{team } i\text{'s regulation possessions in game } g \text{ (the row weight)} \\
\mu: & \text{league points per possession at } t \text{ (unpenalized)} \\
O_i: & \text{team } i\text{'s offense effect, points per possession; } +\text{ = better offense} \\
D_{j(g)}: & \text{opponent } j\text{'s defense effect, points per possession allowed; } -\text{ = better defense} \\
h: & \text{home effect, points per possession (unpenalized)} \\
H_{ig}: & +1 \text{ home, } -1 \text{ away, } 0 \text{ at a neutral site} \\
\lambda_{\text{PPP}}: & \text{ridge penalty, in possessions; tuned to } 40
\end{array}
\end{gathered}
$$

`fit_ppp()` solves this directly. It is weighted least squares on two rows per game, one
for each side's scoring against the other's defense, plus a charge for moving any team away
from league average. For one team in isolation, the offense rating is about
$n\bar{r}/(n+\lambda_{\text{PPP}})$ after $n$ possessions at an adjusted average $\bar{r}$
([phantom possessions](#how-ridge-regression-works)).
With $\lambda_{\text{PPP}}=40$ and 36 possessions (about three games) at $+1.10$, that is
$36\times1.10/76=+0.52$. The team's own average gets half the weight once $n=40$, which is
where "about three games" in the Method comes from. The real fit couples teams through
their opponents.

### Pace

$$
\begin{gathered}
\min_{\nu,\,P}\;\sum_{g\in G_t}\left(N_g-\nu-P_{\text{h}(g)}-P_{\text{a}(g)}\right)^2+\lambda_{\text{pace}}\sum_{k}P_k^2 \\[1em]
\begin{array}{rl}
\text{where}\quad G_t: & \text{games behind } F_t \text{ (same cutoff, same gate)} \\
N_g: & \text{possessions per team in game } g \text{: both teams' regulation drives} \div 2 \\
\nu: & \text{league possessions per team per game at } t \text{ (unpenalized)} \\
\text{h}(g),\ \text{a}(g): & \text{home and away team of game } g \\
P_k: & \text{team } k\text{'s pace effect, possessions per team per game; } +\text{ = more possessions} \\
\lambda_{\text{pace}}: & \text{ridge penalty, in games; tuned to } 8
\end{array}
\end{gathered}
$$

`fit_pace()` gives each game weight 1, and both teams feed one shared count, so their
effects add. The isolated-team shrinkage is $n\bar{r}/(n+\lambda_{\text{pace}})$ after $n$
games with mean residual $\bar{r}$, so a team's own pace gets half weight only after 8
games. Pace is shrunk harder than offense and defense.

### Total

$$
\begin{gathered}
\widehat{\text{Total}}_g=\widehat{N}_g\left(\widehat{\text{PPP}}^{\text{h}}_g+\widehat{\text{PPP}}^{\text{a}}_g\right)+c_t \\[0.5em]
\widehat{N}_g=\nu+P_{\text{h}}+P_{\text{a}},\qquad
\widehat{\text{PPP}}^{\text{h}}_g=\mu+O_{\text{h}}+D_{\text{a}}+hH_g,\qquad
\widehat{\text{PPP}}^{\text{a}}_g=\mu+O_{\text{a}}+D_{\text{h}}-hH_g \\[1em]
\begin{array}{rl}
\text{where}\quad \widehat{\text{Total}}_g: & \text{forecast full-game points total, overtime included} \\
\widehat{N}_g: & \text{forecast possessions per team} \\
\widehat{\text{PPP}}^{\text{h}}_g,\ \widehat{\text{PPP}}^{\text{a}}_g: & \text{forecast home and away points per possession} \\
H_g: & +1 \text{, or } 0 \text{ at a neutral site} \\
c_t: & \text{fit-set mean overtime points per game (total} - \text{both teams' Q1–Q4 line scores)}
\end{array}
\end{gathered}
$$

`forecast_total()` computes this. The home term adds $h$ to one rate and subtracts it from
the other, so it cancels in the total. It matters only for fitting $O$ and $D$ without
home/away bias. A team with no games before $t$ rates 0 under `ridge_v1`; under `raw_v1`
it has no rating and no forecast. With the 2025 last-cutoff values, two average teams give
$2\mu\nu+c_t=2(2.262)(11.508)+0.617=52.68$ points. The derivatives around that point
explain the ratings' scale:

- $+1$ point per possession of $O$ or $D$ adds $\nu\approx11.5$ points to the total.
- $+1$ possession per team of $P$ adds $2\mu\approx4.5$ points.

### Scoring metrics

$$
\begin{gathered}
\text{MAE}_F=\frac{1}{n}\sum_{g}\left|\widehat{\text{Total}}^{F}_g-\text{Total}_g\right|,\qquad
\text{RMSE}_F=\sqrt{\frac{1}{n}\sum_{g}\left(\widehat{\text{Total}}^{F}_g-\text{Total}_g\right)^2},\qquad
\text{Bias}_F=\frac{1}{n}\sum_{g}\left(\widehat{\text{Total}}^{F}_g-\text{Total}_g\right) \\[0.5em]
\Delta_{A-B}=\frac{1}{n}\sum_{g}\left(\left|\widehat{\text{Total}}^{A}_g-\text{Total}_g\right|-\left|\widehat{\text{Total}}^{B}_g-\text{Total}_g\right|\right),\qquad
\text{MDE}=(1.96+0.84)\,\widehat{\text{SE}}\left(\Delta_{A-B}\right) \\[1em]
\begin{array}{rl}
\text{where}\quad g,\ n: & \text{a scored game, and the number of games (every forecast is scored on the same games)} \\
\text{Total}_g: & \text{actual full-game points total, overtime included} \\
\widehat{\text{Total}}^{F}_g: & \text{forecast } F\text{'s total, points; } F\in\{\text{open, train mean, raw, ridge}\} \\
\text{Bias}_F: & \text{points; } +\text{ = forecast too high} \\
\Delta_{A-B}: & \text{paired MAE difference, points; } -\text{ = } A \text{ is closer to the total} \\
\widehat{\text{SE}}: & \text{standard deviation of } \Delta \text{ over 10,000 week-cluster bootstrap draws} \\
\text{MDE}: & \text{smallest true } |\Delta| \text{ detected with 80\% power at a two-sided 5\% level}
\end{array}
\end{gathered}
$$

`accuracy()` and `paired_mae_diff()` compute these. $\Delta$ equals $\text{MAE}_A-\text{MAE}_B$,
but it is computed per game, so the bootstrap keeps the pairing. The bootstrap resamples
whole season-weeks because every game in a week shares one snapshot. Worked number: ridge
− raw is $\Delta=-1.14$ with $\widehat{\text{SE}}=0.122$, so the MDE is
$2.8\times0.122=0.34$. The estimated gap is more than three times the MDE.

### Encompassing regression

$$
\begin{gathered}
\text{Total}_g-L_g=a+b\left(\widehat{\text{Total}}^{F}_g-L_g\right)+e_g \\[1em]
\begin{array}{rl}
\text{where}\quad \text{Total}_g: & \text{actual full-game points total} \\
L_g: & \text{Bovada open label, points} \\
\widehat{\text{Total}}^{F}_g: & \text{forecast } F\text{'s total, points} \\
a: & \text{intercept, points: where the total lands vs the open when } F \text{ agrees with it} \\
b: & \text{slope, unitless: share of } F\text{'s disagreement with the open that shows up in the total} \\
e_g: & \text{residual, points}
\end{array}
\end{gathered}
$$

`encompassing_slope()` fits this by OLS on the primary games. $b\approx0$ means the
forecast adds nothing the open lacks. $b>0$ with an interval clear of 0 means it carries
information the open does not. $b=1$ would mean its disagreements are right on average at
full size. $b<0$ means the total moves away from the forecast, so the forecast's
disagreements point the wrong way.

### Symbols in code and outputs

JSON keys below sit under `results.primary` or `results.early` unless they start with
`tuning` or `market`. For example: `verdicts.ridge_vs_raw.diff`,
`paired_vs_open.ridge.ci95`, `encompassing_vs_open.ridge.slope`.

| Symbol | Meaning | Units and sign | In code | In outputs |
| --- | --- | --- | --- | --- |
| $t$ | weekly cutoff: earliest kickoff of the week | timestamp | `week_cutoffs()`, `cut` | CSV `as_of_ts`, `as_of_week` |
| $F_t$, $G_t$ | rows and games before $t$, gate applied | — | `fit_set()` | — |
| $y_{ig}$ | team regulation points per possession | points/possession | `_team_rows()`: `y = pts / w`, `pts` from `home_reg`/`away_reg` | — |
| $w_{ig}$ | team regulation possessions | possessions | `w`, from `home_poss`/`away_poss` | CSV `n_possessions` (summed over games) |
| $H_{ig}$, $H_g$ | venue | +1 home, −1 away, 0 neutral | `H`, from `neutral` | — |
| $N_g$ | possessions per team in a game | possessions | `N = (home_poss + away_poss) / 2` | — |
| $\mu$ | league points per possession | points/possession | `Ratings.mu` | CSV `mu` |
| $h$ | home edge | points/possession; + = home scores more | `Ratings.h` (0 in `raw_v1`) | CSV `h` |
| $O_i$ | offense rating | points/possession; + = better | `Ratings.table["O"]` | CSV `O` |
| $D_j$ | defense rating | points/possession allowed; − = better | `Ratings.table["D"]` | CSV `D` |
| $\nu$ | league possessions per team per game | possessions | `Ratings.nu` | CSV `nu` |
| $P_k$ | pace rating | possessions per team; + = faster | `Ratings.table["P"]` | CSV `P` |
| $c_t$ | fit-set mean overtime points | points | `Ratings.c`, mean of `ot` | CSV `c` |
| $\lambda_{\text{PPP}}$ | offense/defense penalty | possessions | `lam_ppp`, grid `LAMBDA_PPP_GRID` | CSV `lambda_ppp`; JSON `tuning.ppp` |
| $\lambda_{\text{pace}}$ | pace penalty | games | `lam_pace`, grid `LAMBDA_PACE_GRID` | CSV `lambda_pace`; JSON `tuning.pace` |
| — | games behind a rating | games | `_evidence()` | CSV `n_games` |
| — | fewer of the two teams' prior games; primary if ≥ 3 | games | `min_prior_games`, `MIN_PRIOR_GAMES` | JSON `results.populations` |
| $\text{Total}_g$ | actual total | points | `total` | — |
| $L_g$ | Bovada open label | points | `load_opens()`: `overUnderOpen` → `open` | JSON `market` |
| $\widehat{\text{Total}}^{F}_g$ | forecast $F$'s total | points | `forecast_total()`; columns `open`, `mean`, `raw`, `ridge`, `ridge_x0.5`, `ridge_x2` | JSON `accuracy_pooled.<F>` |
| MAE, RMSE, Bias | accuracy | points; bias + = too high | `accuracy()` | JSON `mae`, `rmse`, `bias` |
| $\Delta_{A-B}$ | paired MAE difference | points; − = $A$ closer | `paired_mae_diff(df, A, B)` | JSON `diff`, `ci95`, `se`, `mde80`, `by_season` |
| — | verdict | improves / matches / worse | `classify_verdict()` | JSON `verdict`, `stable_under_stress` |
| $a$, $b$ | encompassing intercept and slope | $a$ points; $b$ unitless | `encompassing_slope()` | JSON `slope`, `ci95`; $a$ printed by `weekly_ratings_coefs` |

## Method

- **Ratings.** Guide §7.1–7.3 without priors
  ([`totals-modeling-guide.md`](../research/totals/docs/totals-modeling-guide.md)).
  Team points per possession is $\mu+O_i+D_j+hH$, weighted by possessions; possessions per
  team is $\nu+P_{\text{h}}+P_{\text{a}}$; the total is possessions times the two teams'
  rates plus the average overtime points ([equations](#model-and-variables)).
  - `ridge_v1`: ridge penalty toward 0 (league average); $\mu$, $\nu$, $h$ unpenalized.
  - `raw_v1`: season-to-date means minus the league mean; no adjustment, no shrinkage.
- **Points and possessions.** Points are Q1–Q4 line scores. Drive score fields are never
  read: from 2021 on, 19–58 FBS games a season have drive points above the final score.
  Possessions are regulation drives. So $O$ is a **team** rate: a team's own defensive and
  return touchdowns are in it.
- **Gate.** A game with no drives, or whose two teams' drive counts differ by more than 2,
  is withheld from fits (12–31 games a season, about 2%). It can still be scored.
- **As of.** Week $w$'s ratings are fit on the season's games that kicked off strictly
  before week $w$'s earliest kickoff, through the Release A `snapshot()`. Week 1 is not
  rated.
- **Tuning.** On 2014–2019 only (85 weekly cutoffs), by one-step-ahead component loss:
  possession-weighted squared error of points per possession for $\lambda_{\text{PPP}}$,
  squared error of possessions for $\lambda_{\text{pace}}$. Picks: $\lambda_{\text{PPP}}=40$
  possessions, $\lambda_{\text{pace}}=8$ games; neither on its grid's edge. A penalty of 40
  possessions means a team needs about three games before its own results outweigh league
  average.
- **Scoring.** 2021–2025, penalties frozen. Four forecasts of the full-game total on the
  same games: the Bovada `overUnderOpen` label (fixed book, no fallback), the mean total of
  every FBS-vs-FBS game since 2014 before the cutoff, `raw_v1`, `ridge_v1`. Differences are
  paired per game; intervals are a week-cluster bootstrap (whole season-weeks resampled,
  10,000 draws, seed 20260922) because every game in a week shares one snapshot. The MDE
  beside each interval is 2.8 × the bootstrap SE (80% power, two-sided 5%).
- **Verdict rule**, declared before scoring: *improves* if the pooled interval is below 0
  and at most one season disagrees; *worse* if it is above 0; *matches* otherwise.
- **Trials:** 12 tuning grid points (tune seasons only), 2 methods scored, 1 book, 2
  stress variants (penalties ×0.5 and ×2).

## Data

- `data/raw/games_<s>.json`, `drives_<s>.json` for 2014–2025, `lines_<s>.json` for
  2021–2025. 2020 is loaded for the train mean only; it is neither tuned nor scored.
- Scored: 3,488 week-2+ FBS-vs-FBS regular-season games, 3,480 with a Bovada open.
  Primary population (both teams ≥3 prior ungated FBS-vs-FBS games): 2,618. Early (some team
  <3): 862.

## Numbers

**Primary population, pooled 2021–2025 (n = 2,618; 61 season-week clusters).**

| Forecast | MAE | RMSE | Bias (forecast − actual) |
| --- | ---: | ---: | ---: |
| Bovada open label | 12.60 | 15.86 | −0.22 |
| `ridge_v1` | 12.94 | 16.35 | −0.18 |
| Train mean | 13.78 | 17.19 | +2.23 |
| `raw_v1` | 14.08 | 17.69 | −0.24 |

**Paired MAE differences** (first minus second; negative = first is closer).

| Comparison | Difference | 95% interval | MDE | Per season 2021 / 22 / 23 / 24 / 25 | Verdict |
| --- | ---: | --- | ---: | --- | --- |
| ridge − raw | −1.14 | −1.39 to −0.91 | 0.34 | −1.40 / −0.73 / −0.92 / −1.43 / −1.21 | improves, stable |
| ridge − train mean | −0.84 | −1.09 to −0.59 | 0.36 | −0.47 / −1.31 / −1.31 / −0.34 / −0.78 | improves, stable |
| ridge − open | +0.33 | +0.19 to +0.48 | 0.21 | +0.46 / +0.49 / +0.21 / +0.18 / +0.35 | (reported) |
| raw − train mean | +0.30 | −0.10 to +0.70 | 0.58 | +0.92 / −0.58 / −0.39 / +1.09 / +0.43 | (reported) |

Stress: at penalties ×0.5 the two verdict differences are −0.89 and −0.59, at ×2 they are
−1.22 and −0.93; every interval stays below zero, so both verdicts hold.

**Encompassing slope against the open**, $b$ in the
[encompassing regression](#encompassing-regression):

| Forecast | $b$ | 95% interval | $a$ (points) |
| --- | ---: | --- | ---: |
| `ridge_v1` | 0.03 | −0.13 to 0.20 | +0.21 |
| `raw_v1` | −0.09 | −0.16 to −0.01 | +0.21 |
| Train mean | 0.15 | 0.06 to 0.23 | −0.15 |

The $a$ column was added after the run. It is a point estimate with no interval, from the
OLS identity $a=\overline{\text{Total}_g-L_g}-b\,\overline{\widehat{\text{Total}}^{F}_g-L_g}$ (bars are means
over the primary games) and the pooled biases above: $\overline{\text{Total}_g-L_g}=+0.22$ because
the open ran 0.22 low. With $b$ near 0, ridge's and raw's intercepts are simply that
shortfall. The train mean's $a$ is lower because its +2.23 bias pulls
$\overline{\widehat{\text{Total}}^{F}_g-L_g}$ to +2.45.

**Early population** (week 2+, a team with <3 prior games; n = 862, 23 clusters): open
12.59, ridge 13.24, train mean 13.47. Ridge − mean −0.23 (−0.56 to +0.14, MDE 0.50):
cannot tell. Ridge − open +0.65 (+0.21 to +1.13). Ridge's early bias is −1.36 points.

## Fitted coefficients

Every table here is printed by `python -m scripts.weekly_ratings_coefs`. Season rows use
each season's **last cutoff** (week 15–16, about 11 games per team). That is the most
evidence any snapshot has, not what a typical scored week used, so the in-season min–max
sits beside each league value. All values are `ridge_v1` unless marked raw.

**Penalties.** Tuning loss summed over the 85 cutoffs of 2014–2019. PPP loss is the
possession-weighted squared error of points per possession; pace loss is the squared error
of possessions per team.

| $\lambda_{\text{PPP}}$ (possessions) | Loss | Above best | $\lambda_{\text{pace}}$ (games) | Loss | Above best |
| ---: | ---: | ---: | ---: | ---: | ---: |
| 5 | 104,482 | 7.5% | 0.5 | 15,134 | 14.8% |
| 10 | 100,046 | 3.0% | 1 | 14,295 | 8.4% |
| 20 | 97,258 | 0.1% | 2 | 13,602 | 3.1% |
| **40** | 97,157 | 0.0% | 4 | 13,207 | 0.1% |
| 80 | 100,255 | 3.2% | **8** | 13,188 | 0.0% |
| 160 | 105,817 | 8.9% | 16 | 13,458 | 2.1% |

Both curves are flat around the pick: the neighbour on the low side ($\lambda_{\text{PPP}}=20$,
$\lambda_{\text{pace}}=4$) is 0.1% worse. The ×0.5 stress run lands on those neighbours
and ×2 on the 2–3% worse side ($\lambda_{\text{PPP}}=80$, $\lambda_{\text{pace}}=16$);
both verdicts held at each.

**League-level coefficients**, last cutoff (in-season min–max):

| Season | As of week | $\mu$ (points/possession) | $\nu$ (possessions/team) | $h$ (points/possession) | $c_t$ (points) |
| --- | ---: | --- | --- | --- | --- |
| 2021 | 15 | 2.251 (2.14–2.25) | 12.130 (12.13–12.46) | 0.103 (0.10–0.47) | 0.452 (0.06–0.46) |
| 2022 | 15 | 2.214 (2.21–2.31) | 12.132 (12.11–12.39) | 0.119 (0.12–0.51) | 0.574 (0.54–1.00) |
| 2023 | 15 | 2.201 (2.14–2.20) | 11.956 (11.79–12.04) | 0.134 (0.13–0.56) | 0.584 (0.52–0.96) |
| 2024 | 16 | 2.254 (2.09–2.26) | 11.817 (11.73–11.97) | 0.170 (0.16–0.35) | 0.467 (0.18–0.50) |
| 2025 | 16 | 2.262 (1.99–2.29) | 11.508 (11.22–11.52) | 0.182 (0.18–0.51) | 0.617 (0.00–0.78) |

- $\mu$ stays near 2.2 points per possession. $\nu$ held at 12.13 in 2021–2022, then fell
  each season to 11.51 possessions per team in 2025.
- At season end, $h$ is 0.10–0.18. The home rate gets $+h$ and the away rate $-h$, so the
  home-minus-away margin it implies is $2h\nu$: 2.5 points in 2021, 4.2 in 2025. It cancels
  in the total.
- Early-season $h$ runs as high as 0.47–0.56. A likely reason is that early fits have too
  little evidence to separate teams, so $h$ absorbs how strong home teams are in early
  mismatches. That was not tested.
- $c_t$ is 0.45–0.62 points of overtime per game at season end. It is a fit-set average,
  so it is noisy early: 0.00 when no earlier game went to overtime.

**Team ratings spread**, standard deviation across teams with ≥3 games, last cutoff:

| Season | Teams | $O$ raw | $O$ ridge | $D$ raw | $D$ ridge | $P$ raw | $P$ ridge |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| 2021 | 130 | 0.576 | 0.438 | 0.579 | 0.447 | 0.705 | 0.388 |
| 2022 | 131 | 0.614 | 0.472 | 0.513 | 0.386 | 0.759 | 0.418 |
| 2023 | 133 | 0.595 | 0.468 | 0.500 | 0.392 | 0.664 | 0.378 |
| 2024 | 134 | 0.559 | 0.429 | 0.563 | 0.431 | 0.848 | 0.458 |
| 2025 | 136 | 0.602 | 0.467 | 0.566 | 0.436 | 0.777 | 0.418 |

One SD of ridge $O$ or $D$ is 0.39–0.47 points per possession, about 4.5–5.7 points a game
at $\nu\approx11.5$–12. Ridge SDs are 21–25% below raw for $O$ and $D$, and 43–46% below
for $P$. At season end (about 11 games, 130 possessions per team) the isolated-team
weights are 0.77 for offense and defense and 0.58 for pace. The pooled ridge/raw SD ratios
are 0.77, 0.77 and 0.55. That is close to what shrinkage alone predicts, which suggests
opponent adjustment changes the spread little on net. It is a consistency check, not a
decomposition.

**2025 examples**, last cutoff, three lowest and three highest:

| Rating | Lowest | Highest |
| --- | --- | --- |
| $O$ | Massachusetts −1.09, Charlotte −0.97, Wyoming −0.83 | Notre Dame +1.07, Vanderbilt +1.10, Indiana +1.18 |
| $D$ | Texas Tech −1.18, Ohio State −1.11, Indiana −1.00 | Sam Houston +0.87, UAB +0.87, Massachusetts +1.11 |
| $P$ | Army −1.27, Air Force −0.91, Ohio State −0.89 | Florida International +0.85, Buffalo +0.94, Texas Tech +1.17 |

The signs read as designed: good defenses are negative, slow triple-option teams are
negative on pace. Some worked scales, using the derivatives in [Total](#total):

- Indiana's $+1.18$ offense is about $1.18\times11.51\approx+13.6$ points a game over an
  average offense against an average defense.
- Army's $-1.27$ pace is about $1.27\times4.52\approx5.7$ fewer total points from tempo
  alone.

## What this changes downstream

- **Guide §13 step 3 is built.** Point-in-time PPP and pace ratings exist, with as-of
  snapshots, and the ridge version clears the go/no-go bar against simpler baselines. It is
  the base rating for Release C and for priors (step 4), where only the penalty's target
  changes.
- **Opponent adjustment and shrinkage are what earn the gain.** The raw version is no
  better than a pooled mean (−0.10 to +0.70). Averaging a team's own games, even after three
  of them, is too noisy to use.
- **The open stays the benchmark to beat, and ridge does not beat it.** Ridge is 0.33
  points worse on average and its disagreement with the open has no detectable value
  ($b$ = 0.03). Nothing here is a reason to trust a ratings-vs-open gap.
- **Early weeks need priors.** Where some team has fewer than three games, ridge cannot be
  told apart from the pooled mean and is 0.65 points behind the open, and its −1.36 bias
  says the early current-season league levels run low. That is the step-4 problem, now
  measured.

## What this does not support

- **No betting value.** This is forecast error of a point total against a labeled vendor
  number with no capture time and no price ([Release A](pregame-replay-2026-09-22.md)). It
  grades no wager and supports no return, cover-rate or closing-line claim.
- **Not "−0.84 against the mean is all team-rating skill".** The pooled mean carries a
  +2.23 bias from scoring drift since 2014, and ridge uses current-season league levels, so
  part of that gap is a level correction. Ridge − raw (same league levels, −1.14) is the
  comparison that isolates adjustment and shrinkage. A current-season-mean baseline was not
  declared before scoring and is not added here.
- **Not "ratings add nothing beyond the open".** The encompassing slope uses an estimated
  regressor: rating noise biases $b$ toward zero, so $b\approx0$ is a weak null, not
  evidence of absence.
- **The train mean's slope of 0.15 is not an established market miscalibration.** It says
  totals landed about 15% of the way from the open toward the pooled mean, which would mean
  the opens are slightly too spread out. Its interval is clear of zero, but this is one
  comparison among several, on unpriced, untimed opens; it is a lead for guide §14 item 2,
  not a finding.
- **Not a statement about FBS–FCS games, 2020, week 1, or seasons before 2021** against
  the open.
- **Not a tuned final model.** No garbage-time filter, no neutral pace, no priors, one
  penalty per rating.
- **The coefficient tables are not the typical scored snapshot.** They are last-cutoff
  values, after about 11 games; mid-season snapshots carry less evidence and more
  shrinkage. The early-season reading of $h$ is a guess, not a result.

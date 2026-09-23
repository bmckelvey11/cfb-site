# Weekly PPP and pace ratings vs the mean and the vendor open (Release B) — design

**Status:** implemented 2026-09-23 (`d9367c1` fits, `e2c0ffd` evaluation). Result:
[`docs/weekly-ratings-2026-09-23.md`](../../weekly-ratings-2026-09-23.md).
**Builds on:** Release A, [`docs/pregame-replay-2026-09-22.md`](../../pregame-replay-2026-09-22.md)
and `scripts/pregame_replay_audit.py` (`snapshot()`).
**Spec it implements:** [`research/totals/docs/totals-modeling-guide.md`](../../../research/totals/docs/totals-modeling-guide.md)
§7.1–7.3 and §13 step 3 ("point-in-time pace and efficiency ... not built").

## Goal

Build weekly, as-of opponent-adjusted **points-per-possession** (offense $O$, defense $D$)
and **pace** ($P$) ratings, turn them into a game-total forecast, and score that forecast
against a train mean, a raw season-to-date version, and the Bovada open label on outer
seasons. Every rating row says what it knew and when.

## Scope

In: guide §13 step 3 only. A ridge-adjusted rating (`ridge_v1`) and an unadjusted rating
(`raw_v1`), weekly snapshots, one λ per rating tuned on earlier seasons, evaluation on
2021–2025.

Out, each with its later home:

| Not in this release | Where it goes |
| --- | --- |
| Previous-season priors, prior-centered ridge (guide §7.4–7.5) | Next release (guide §13 step 4) |
| Garbage-time filter | Guide open item 5, an ablation on these ratings |
| Neutral seconds-per-play pace | Guide §7.2 caution, "test both"; later |
| Ridge/elastic net as a model on a feature block, Optuna | Release C, in the totals harness |
| Bet grading, return figures, cover rates, closing-line comparisons, thresholds | Release D+, governed by `docs/model-evaluation-standard.md` |
| GUI, warehouse tables, `games.csv`/`features.json`/`FEATURE_REGISTRY` writes | Not in any release so far |

## Inputs

Read-only, each file's sha256 recorded in the manifest, as in Release A.

| File | Used for |
| --- | --- |
| `data/raw/games_<s>.json` | kickoff (`startDate`), `week`, `seasonType`, `completed`, `homeClassification`/`awayClassification`, `neutralSite`, `homePoints`/`awayPoints`, `homeLineScores`/`awayLineScores` |
| `data/raw/drives_<s>.json` | possession counts only (`gameId`, `offense`, `isHomeOffense`, `startPeriod`) |
| `data/raw/lines_<s>.json` | Bovada `overUnderOpen`, scored seasons only |

Bovada is the fixed market provider: it is the only book with opens on nearly every
FBS-vs-FBS regular-season game in every scored season (732–762 a season, 2021–2025). No
fallback to another book, no close, no imputation. No book has opens in 2019–2020.

## Definitions

- **Possession:** a drive with `startPeriod` in 1–4. Overtime drives are excluded.
- **Team regulation points:** the sum of the team's Q1–Q4 line scores. Line scores are
  present and sum to the final score in every FBS-vs-FBS regular-season game checked.
  Drive score fields (`startOffenseScore`/`endOffenseScore`) are **never read**: from 2021
  on, 19–58 games a season have drive points above the game's final score.
- **Team-game row** $(i,g)$: $y_{ig}$ = team $i$'s regulation points ÷ its regulation
  possessions; weight $w_{ig}$ = those possessions; $H_{ig}$ = +1 home, −1 away, 0 at a
  neutral site. This is **team** points per possession: a team's own defensive and return
  touchdowns land in its numerator. Docs say so wherever the rating is named.
- **Game row** $g$: $N_g$ = both teams' regulation possessions ÷ 2.
- **Population:** FBS vs FBS, regular season, completed. FBS–FCS games are dropped from
  fits and from scoring.
- **Data-quality gate (fits only):** a game is dropped from fits, and counted, when it has
  no drive rows or when the two teams' regulation drive counts differ by more than 2.
  Possessions alternate, so a larger gap means missing drives; about 2% of games. A gated
  game can still be a scored game; only its own evidence is withheld.
- **Garbage time:** not filtered. Declared as `garbage_filter = "none"` on every row.

## Cutoff and snapshots

Week $w$'s cutoff $t$ is the earliest kickoff among season $s$'s week-$w$ games. The fit set
$F_t$ is every row of season $s$ with kickoff strictly before $t$, selected with
`snapshot()` from `scripts/pregame_replay_audit.py`, not a reimplementation. Every week-$w$
game is forecast from that one frozen snapshot. That is stricter than per-game: a Tuesday
game in week $w$ does not inform the Saturday games of week $w$.

Week 1 is never rated: its fit set is empty. A team with no games before the cutoff rates 0
(league average) under `ridge_v1` and has no `raw_v1` rating.

Snapshot row: `season, as_of_week, as_of_ts, team, method, O, D, P, n_games,
n_possessions, lambda_ppp, lambda_pace, garbage_filter, fcs_policy`, plus per-snapshot
`mu, nu, h, c`. Source and code hashes live in the manifest.

## Ratings

### ridge_v1

$$
\begin{gathered}
\min_{\mu,\,h,\,O,\,D}\;\sum_{(i,g)\in F_t} w_{ig}\left(y_{ig}-\mu-O_i-D_{j(g)}-hH_{ig}\right)^2+\lambda_{\text{PPP}}\sum_{k}\left(O_k^2+D_k^2\right) \\[1em]
\begin{array}{rl}
\text{where}\quad F_t: & \text{team-game rows of season } s \text{ with kickoff strictly before cutoff } t \\
y_{ig}: & \text{team } i\text{'s regulation points (line scores) per regulation possession in game } g \\
w_{ig}: & \text{team } i\text{'s regulation possessions in game } g \\
\mu: & \text{league points per possession at } t \text{ (unpenalized)} \\
O_i: & \text{offense effect, points per possession; } +\text{ = better offense} \\
D_{j(g)}: & \text{opponent's defense effect, points per possession allowed; } -\text{ = better defense} \\
h,\ H_{ig}: & \text{home effect (unpenalized); } H=+1 \text{ home, } -1 \text{ away, } 0 \text{ neutral} \\
\lambda_{\text{PPP}}: & \text{penalty, in possessions; } \ge 0
\end{array}
\end{gathered}
$$

This is guide §7.1 with a ridge penalty toward 0, the league average, in place of a prior.
The first sum rewards ratings that reproduce the games played; the second charges for
moving any team away from average. Treating one team in isolation, its offense rating is
roughly $n\bar{y}/(n+\lambda_{\text{PPP}})$ after $n$ possessions at an adjusted average
$\bar{y}$: with $\lambda_{\text{PPP}}=20$ and 36 possessions at $+1.10$, that is
$36\times1.10/56=+0.71$. The real fit couples teams through their opponents. It is solved
directly, $(X^\top WX+\Lambda)\beta=X^\top Wy$, with $\Lambda$ zero on $\mu$ and $h$.

Pace is the same construction on game rows (guide §7.2):

$$
\begin{gathered}
\min_{\nu,\,P}\;\sum_{g\in G_t}\left(N_g-\nu-P_{\text{h}(g)}-P_{\text{a}(g)}\right)^2+\lambda_{\text{pace}}\sum_{k}P_k^2 \\[1em]
\begin{array}{rl}
\text{where}\quad G_t: & \text{games of season } s \text{ with kickoff strictly before cutoff } t \text{ (the games behind } F_t\text{)} \\
N_g: & \text{possessions per team in game } g \text{ (regulation)} \\
\nu: & \text{league possessions per team per game at } t \text{ (unpenalized)} \\
\text{h}(g),\ \text{a}(g): & \text{home and away team of game } g \\
P_k: & \text{team } k\text{'s pace effect, possessions per team per game; } +\text{ = more possessions} \\
\lambda_{\text{pace}}: & \text{penalty, in games; } \ge 0
\end{array}
\end{gathered}
$$

Both teams feed one shared count, so their effects add. Each game has weight 1. With
$\nu=12.0$, a $+0.8$ team meeting a $-0.5$ team is expected to have $12.3$ possessions
each.

### raw_v1

The same structure with no opponent adjustment, no shrinkage and no home term: $O_i$ is
team $i$'s possession-weighted mean offensive points per possession minus $\mu$, $D_j$ is
the mean it allowed minus $\mu$, $P_i$ is its mean $N_g$ minus $\nu$, with $\mu$ and $\nu$
the fit-set means. A team is rated once it has one game.

## Total forecast

$$
\begin{gathered}
\widehat{T}_g=\widehat{N}_g\left(\widehat{\text{PPP}}^{\text{h}}_g+\widehat{\text{PPP}}^{\text{a}}_g\right)+c_t \\[0.5em]
\widehat{N}_g=\nu+P_{\text{h}}+P_{\text{a}},\qquad
\widehat{\text{PPP}}^{\text{h}}_g=\mu+O_{\text{h}}+D_{\text{a}}+hH_g,\qquad
\widehat{\text{PPP}}^{\text{a}}_g=\mu+O_{\text{a}}+D_{\text{h}}-hH_g \\[1em]
\begin{array}{rl}
\text{where}\quad \widehat{T}_g: & \text{forecast full-game points total} \\
H_g: & +1 \text{, or } 0 \text{ at a neutral site} \\
c_t: & \text{fit-set mean of overtime points (actual total} - \text{both teams' Q1–Q4 line scores)}
\end{array}
\end{gathered}
$$

Guide §7.3 forecasts the regulation total. The open prices the full game, so $c_t$ adds the
fit set's average overtime points back, and every forecast here targets the same full
total. Defensive and return scores are already inside each team's rate. With the guide's
worked example (55.0 before $c_t$) and an illustrative $c_t=0.8$, the forecast is 55.8.
`raw_v1` uses $h=0$.

## λ tuning

- Grids: $\lambda_{\text{PPP}}\in\{5,10,20,40,80,160\}$ possessions,
  $\lambda_{\text{pace}}\in\{0.5,1,2,4,8,16\}$ games.
- Loss: one-step-ahead. At every cutoff from week 2 of **2014–2019**, fit on $F_t$ and
  score that week's rows: possession-weighted squared error of $y$ for PPP, squared error
  of $N$ for pace. Sum over all cutoffs; pick the minimum of each grid.
- The two fits share no parameters, so the grids tune independently: **12 tuning trials**.
- 2020 is excluded (COVID schedules, conference-only slates). No scored season is read
  during tuning.

## Evaluation

**Scored seasons:** 2021–2025, λ frozen from tuning.

**Forecasts**, always compared on the same games:

1. Bovada open label.
2. Train mean: mean full total of FBS-vs-FBS regular-season games with kickoff before the
   cutoff, back to 2014.
3. `raw_v1` total.
4. `ridge_v1` total.

**Populations**, fixed before scoring:

- **Primary:** both teams have ≥3 prior FBS-vs-FBS games this season, and a Bovada open
  exists. All four forecasts defined.
- **Early:** weeks 2+ where a team has <3 prior games. `ridge_v1`, train mean and open
  only.

**Metrics**, per season and pooled: count, MAE, RMSE, bias (mean forecast − actual).

- **Paired MAE difference** (forecast minus comparator) for `ridge_v1` against the open,
  the train mean and `raw_v1`, and for `raw_v1` against the train mean. Interval: 95%,
  week-cluster bootstrap (resample whole season-weeks, 10,000 draws, fixed seed), because
  every game in a week shares one snapshot.
- **Encompassing slope**, per forecast $F$:

$$
\begin{gathered}
T_g-L_g=a+b\left(\widehat{T}^{F}_g-L_g\right)+e_g \\[1em]
\begin{array}{rl}
\text{where}\quad T_g: & \text{actual full-game points total} \\
L_g: & \text{Bovada open label (points)} \\
\widehat{T}^{F}_g: & \text{forecast } F\text{'s total (points)} \\
a,\ b: & \text{intercept and slope, fit by OLS} \\
e_g: & \text{residual (points)}
\end{array}
\end{gathered}
$$

The slope asks whether the forecast's disagreement with the open predicts where the total
lands relative to the open. $b\approx0$ means the forecast adds nothing the open lacks;
$b>0$ with an interval clear of 0 means it carries information the open does not. $b=1$
would mean the forecast's disagreements are right on average at full size. Same
week-cluster bootstrap interval.

**Verdict rule**, declared before scoring, applied to a paired MAE difference with pooled
interval $[\ell, u]$ and per-season point estimates:

- **worse** if $\ell>0$;
- **improves** if $u<0$ and the point estimate is negative in all but at most one scored
  season;
- **matches** otherwise.

Applied to `ridge_v1` vs `raw_v1` and `ridge_v1` vs train mean. The open is reported, not
gated.

**Stress:** rerun scoring with both λ ×0.5 and ×2. A verdict that changes under either is
reported as **unstable**.

**Trial count**, in the manifest: 12 tuning grid points (tuning seasons only), 2 methods
scored, 1 provider, 2 stress variants.

**Word check:** stdout and the manifest contain no return, cover-rate, closing-line or
betting-threshold terms, grepped as in Release A.

## Files and outputs

- `scripts/weekly_ratings.py`: `build_games`, `fit_set`, `fit_ppp`, `fit_pace`,
  `fit_ridge`, `fit_raw`, `forecast_total` — the reusable ratings.
- `scripts/weekly_ratings_eval.py`: `load`, `tune`, `run_season`, `paired_mae_diff`,
  `encompassing_slope`, `classify_verdict`, CLI. Split from the fits past ~400 lines, so
  Release C can import ratings without the evaluation.
- Command:
  `python -m scripts.weekly_ratings_eval --tune-seasons 2014-2019 --score-seasons 2021-2025`
- Outputs (gitignored), under `data/processed/ratings/`:
  - `weekly_ratings_snapshots.csv`: every (season, as_of_week, team, method) row.
  - `weekly_ratings_eval.json`: command, code and source sha256s, λ grid losses and picks,
    per-season and pooled metrics, verdicts, stress runs, trial count, population counts
    and drop reasons.
- Placement: root `scripts/` and root `docs/`, following
  `build_ppa_opponent_adjusted_ratings.py`. `research/totals/CLAUDE.md` sends built totals
  work to `models/totals/`, which is mid-rename to an untracked `models/middle/`; a
  committed file there would break a clean checkout. Release C is where the harness
  consumes these snapshots.

## Tests

`tests/test_weekly_ratings.py`, in-memory, no `CFB_DATA_ROOT`, no network:

1. **Leakage:** a game after the cutoff with an extreme score, and a game tied at the
   cutoff, leave the snapshot unchanged.
2. **Recovery:** a noiseless synthetic round-robin with known $O$, $D$, $h$, $P$; a tiny λ
   recovers them, with signs right (good defense negative; $H$ = +1/−1/0).
3. **Shrinkage:** a very large λ drives every rating to 0 and $\mu$ to the weighted league
   mean.
4. **Possessions and points:** overtime drives are excluded from counts; points come from
   Q1–Q4 line scores, and corrupting a drive's score fields changes nothing; a game whose
   drive counts differ by 3 is gated out of the fit and counted.
5. **Total:** the guide §7.3 worked example gives 55.0 with $c_t=0$.
6. **Verdict rule:** each branch of `classify_verdict`.

## Docs

- `docs/weekly-ratings-<date>.md`: question, method, data and date range, numbers,
  verdicts, what the result does not support; points at the script. One row in
  `docs/README.md` under "Betting analysis (cross-unit)".
- `research/totals/docs/totals-modeling-guide.md` (living): update the §7 status line and
  the §13 step-3 row to point at the record, in the same commit.
- Check the guide §2 table and `docs/ppa-opponent-adjusted-ratings-2026-09-16.md` for any
  claim the record changes; update living docs, never rewrite dated ones.

## Commits

1. `docs`: this spec.
2. `feat`: ratings fit, snapshots, tests 1–5.
3. `feat`: tuning, evaluation, verdict (test 6), finding doc, guide update.

## What this design does not claim

- No betting value. A rating that beats the mean is forecast skill, not a price.
- No early-season quality: without priors, week 2–4 ratings are mostly shrinkage to
  average. That is the next release's problem, and the early population is reported so the
  gap is visible.
- The open has no capture time (Release A). Week-$w$ ratings use games through week
  $w-1$, roughly the information set of an open posted after the previous Saturday;
  plausible, not provable.

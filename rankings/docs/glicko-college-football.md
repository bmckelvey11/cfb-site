# Using Glicko for College Football

**Implementation status — 2026-09-29:** Stages 1–3 are implemented in
`models/shared/ratings/glicko`, including
chronological replay, immutable state/update records, an explicit warehouse reader,
and expanding-season benchmark evaluation. Stage 4's frozen-feature interface is
implemented; fitting roster effects and demonstrating locked early-season gains
remain research work. Stage 5 remains conditional on the simpler model's validation.
Weekly frozen replay is the default (updated 2026-09-29): ratings freeze Tuesday
00:00 Eastern and completed results update at the following weekly boundary. Historical
result timestamps are optional under this documented assumption; observed timing remains
available. Defaults remain untuned. The first
historical walk-forward evaluation (`models/shared/ratings/glicko/docs/backtest-2026-09-29.md`)
was completed 2026-09-29: improved forecasts versus the tested simple baselines,
but no demonstrated spread-betting edge. This does not satisfy the promotion gate
for the later research stages.
The linked implementation guide records exact scope, input requirements, and
approximations; the original design discussion below is retained as supplied.

## Executive recommendation

Glicko can be used for college football, but the production model should be **Glicko-inspired rather than a literal chess implementation**. Preserve Glicko's central contribution—a time-varying strength estimate paired with explicit uncertainty—while adapting the observation model for football's scoring margin, points per possession, home-field effects, sparse schedules, offseason discontinuities, FCS opponents, and separate offensive and defensive quality.

The recommended staged architecture is:

1. A single dynamic team-strength model expressed in expected neutral-field points.
2. A joint offense/defense model using points per possession.
3. A separate pace model for possessions.
4. Hierarchical FBS/FCS preseason priors and offseason uncertainty inflation.
5. Chronological validation against Elo, ridge ratings, market prices, and simpler carry-forward models.

Glickman's original system introduced rating deviation to describe uncertainty around estimated strength, while Glicko-2 added a volatility state. Glickman and Stern also developed a state-space model for football scores, providing a more direct conceptual bridge from Glicko to dynamic football ratings.[cite:4][cite:16][cite:53]

---

## Why Glicko fits college football

College football has several properties that make explicit rating uncertainty valuable:

- Teams play relatively few games.
- Schedule strength varies dramatically.
- Teams can change substantially during the offseason.
- Early-season estimates depend heavily on prior information.
- FCS teams and new or transitioning programs are weakly identified.
- Injuries, quarterback changes, transfers, and coaching changes can alter team strength abruptly.

A conventional Elo model tracks a single point estimate. Glicko adds a rating deviation (RD), allowing the model to distinguish between a team whose strength is well established and one with the same estimated strength but little supporting evidence.[cite:4]

The limitation is that standard Glicko was designed for paired win/loss outcomes. A football model intended to forecast spreads and totals should learn from scoring margin or possession efficiency instead of throwing away information by reducing every game to a binary result.

---

## Model choices

| Model | Strength | Limitation | Recommended role |
|---|---|---|---|
| Elo | Simple, stable, transparent | No explicit uncertainty | Baseline |
| Glicko | Adds rating uncertainty | Natively win/loss oriented | Direct prototype |
| Glicko-2 | Adds dynamic volatility | Team volatility may be weakly identified from short seasons | Challenger model |
| Dynamic margin model | Uses football's continuous outcome | Requires an adapted observation model | Recommended overall-rating model |
| Dynamic offense/defense model | Supports spreads, totals, and unit analysis | More parameters and identification constraints | Recommended production model |
| Ridge offense/defense ratings | Stable and easy to fit | No native sequential RD | Mandatory benchmark |
| Bayesian state-space model | Full uncertainty and hierarchical pooling | Greater complexity | Advanced production model |

Start with ordinary Glicko-style uncertainty before adding Glicko-2 volatility. With only one game per team most weeks, separate team-level volatility can add estimation noise unless it is strongly regularized.

---

## Overall team-strength model

Let team $i$ have a latent strength $r_{i,t}$ before game $t$, expressed in neutral-field points. Let $P_{i,t}$ be the variance of that rating and $RD_{i,t}=\sqrt{P_{i,t}}$.

For home team $h$ and away team $a$, expected home margin is:

$$
\widehat{M}_t=r_{h,t}-r_{a,t}+H_t+X_t\beta
$$

where:

- $H_t$ is home-field advantage.
- $X_t\beta$ includes only information available before kickoff.
- $M_t$ is home points minus away points.

The prediction residual is:

$$
e_t=M_t-\widehat{M}_t
$$

### Robust margin observation

A Gaussian residual is simple but sensitive to blowouts. Three practical alternatives are:

#### Logarithmic margin

$$
f(M)=\operatorname{sign}(M)\log(1+|M|)
$$

#### Capped margin

$$
f(M)=\max(-c,\min(M,c))
$$

#### Student-t likelihood

$$
M_t\sim t_{\nu}(\widehat{M}_t,\sigma_M)
$$

The Student-t approach is the most principled of the three because it downweights extreme observations without imposing an arbitrary hard cap.

### Sequential state evolution

Before a game, allow team strength to drift:

$$
r_{i,t}^{-}=r_{i,t-1}^{+}+\omega_{i,t},
\qquad
\omega_{i,t}\sim N(0,q_{i,t})
$$

where $-$ means pregame, $+$ means postgame, and $q_{i,t}$ is process variance added since the team's previous game.

Under a diagonal Gaussian approximation:

$$
K_{h,t}=\frac{P^{-}_{h,t}}
{P^{-}_{h,t}+P^{-}_{a,t}+R_t}
$$

$$
K_{a,t}=\frac{P^{-}_{a,t}}
{P^{-}_{h,t}+P^{-}_{a,t}+R_t}
$$

$$
r^{+}_{h,t}=r^{-}_{h,t}+K_{h,t}e_t
$$

$$
r^{+}_{a,t}=r^{-}_{a,t}-K_{a,t}e_t
$$

Here, $R_t$ is game-level measurement variance. A team with greater uncertainty receives a larger update, which is the key Glicko-like behavior.

---

## Separate offense and defense

Glicko can be extended to offense and defense, but not by naively running two independent binary Glicko systems. The preferred approach is a joint dynamic model in which each offensive observation updates the attacking offense and opposing defense simultaneously.

For team $i$, maintain:

- $O_{i,t}$: offensive efficiency above average.
- $D_{i,t}$: defensive quality above average; higher is better.
- $P^O_{i,t}$: offensive rating variance.
- $P^D_{i,t}$: defensive rating variance.
- $RD^O_{i,t}=\sqrt{P^O_{i,t}}$.
- $RD^D_{i,t}=\sqrt{P^D_{i,t}}$.

Separate uncertainties matter. A quarterback change should primarily increase offensive RD, while major defensive turnover should primarily increase defensive RD.

### Matchup equations

For home team $h$ against away team $a$:

$$
\widehat{PPP}_{h,t}
=
\mu_t+O_{h,t}-D_{a,t}+H^{PPP}_t+X^h_t\beta
$$

$$
\widehat{PPP}_{a,t}
=
\mu_t+O_{a,t}-D_{h,t}+X^a_t\beta
$$

where $PPP$ is points per possession and $\mu_t$ is the era-specific Division I average.

The residuals are:

$$
e_{h,t}=PPP_{h,t}-\widehat{PPP}_{h,t}
$$

$$
e_{a,t}=PPP_{a,t}-\widehat{PPP}_{a,t}
$$

The home residual updates home offense and away defense. The away residual updates away offense and home defense.

### Diagonal Gaussian update

For home offense versus away defense:

$$
K^O_{h,t}
=
\frac{P^O_{h,t}}
{P^O_{h,t}+P^D_{a,t}+R^{PPP}_t}
$$

$$
K^D_{a,t}
=
\frac{P^D_{a,t}}
{P^O_{h,t}+P^D_{a,t}+R^{PPP}_t}
$$

$$
O^+_{h,t}=O^-_{h,t}+K^O_{h,t}e_{h,t}
$$

$$
D^+_{a,t}=D^-_{a,t}-K^D_{a,t}e_{h,t}
$$

If home offense performs better than expected, its offensive rating increases and the opposing defensive rating declines. Apply symmetrical equations to away offense and home defense.

### Variance update

A simple scalar approximation is:

$$
(P^O_{h,t})^+
=
\max\left(\epsilon,
P^O_{h,t}(1-K^O_{h,t})
\right)
$$

$$
(P^D_{a,t})^+
=
\max\left(\epsilon,
P^D_{a,t}(1-K^D_{a,t})
\right)
$$

A full multivariate Kalman or Bayesian model should retain cross-covariances created by repeated matchups. The diagonal version is easier to build and serves as a strong first implementation.

### Identification constraints

Offense and defense are not jointly identified without constraints. Adding the same constant to every offense and defense leaves $O_i-D_j$ unchanged.

After each update batch, impose:

$$
\sum_i O_{i,t}=0
$$

$$
\sum_i D_{i,t}=0
$$

In a Bayesian implementation, zero-centered hierarchical priors can provide the same identification. Ratings can then be published as points per possession above or below the Division I average.

---

## Pace and totals

Do not let offensive ratings absorb tempo. Maintain a separate pace state $Pace_{i,t}$ for each team.

Expected possessions can be modeled as:

$$
\log(\widehat{Poss}_t)
=
\alpha+
\gamma_h Pace_{h,t}+
\gamma_a Pace_{a,t}+
Z_t\delta
$$

Then compute expected total points:

$$
\widehat{Total}_t
=
\widehat{Poss}_t
\left(
\widehat{PPP}_{h,t}+
\widehat{PPP}_{a,t}
\right)
$$

Expected margin is:

$$
\widehat{Margin}_t
=
\widehat{Poss}_t
\left(
\widehat{PPP}_{h,t}-
\widehat{PPP}_{a,t}
\right)
$$

This separates scoring opportunity from scoring efficiency. A fast offense is not automatically a good offense, and a slow team is not automatically inefficient.

If pace is represented as a deviation from the national baseline, impose:

$$
\sum_i Pace_{i,t}=0
$$

---

## Treating FCS opponents

FCS opponents should remain in the rating network. Do not automatically delete FBS-FCS games, initialize every FCS team identically, or treat every such game as an automatic FBS win.

### Preferred hierarchy

| Available FCS data | Representation | Uncertainty |
|---|---|---|
| Complete FCS schedules | Individual FCS ratings | Team-specific RD with conference pooling |
| Partial schedules and FBS-FCS games | Individual ratings anchored to conference priors | Higher RD for weakly connected teams |
| Only FBS schedule data | FCS conference buckets | High bucket-level uncertainty |
| Minimal opponent metadata | One FCS baseline | Very high RD and weak-identification flag |

### Hierarchical initialization

For team $i$ in group $g$:

$$
r_{i,0}\sim N(\mu_g,\tau_g^2)
$$

The group can represent an FBS conference, FCS conference, subdivision, or independent category. Estimate group means and dispersions inside each historical training fold.

For unit ratings:

$$
O_{i,0}\sim N(\mu^O_g,(\tau^O_g)^2)
$$

$$
D_{i,0}\sim N(\mu^D_g,(\tau^D_g)^2)
$$

An unknown FCS team should start near an estimated FCS or conference baseline with high uncertainty, not at the FBS average.

### Updating FBS-FCS games

Use the same expected-margin or expected-efficiency model used for every other matchup:

$$
\widehat{M}_t
=
r_{FBS,t}-r_{FCS,t}+H_t+X_t\beta
$$

$$
e_t=M_t-\widehat{M}_t
$$

A routine blowout close to expectation should produce little movement. A narrow FBS win, severe underperformance, or FBS loss should produce a larger update.

For possession models:

- Remove kneel-down and clock-kill possessions.
- Downweight or remove defined garbage-time possessions.
- Preserve competitive possessions.
- Do not delete the whole game simply because an FCS team participated.
- Keep FCS offensive and defensive RDs high when data coverage is incomplete.

### Preventing rating islands

Cross-subdivision games connect the FBS and FCS rating scales. Monitor:

- Number of FBS-FCS connections by season.
- Conference-level connectivity.
- Posterior or estimated uncertainty for isolated teams.
- Drift in average FBS and FCS ratings.
- Sensitivity to group-prior assumptions.

If the network is poorly connected, hierarchical priors are essential.

---

## Prior seasons and preseason ratings

Use the previous season's **continuous rating**, not its final ordinal rank. Ordinal rankings discard distance information and treat the gaps between adjacent ranks as equal when they may not be.

### Overall preseason mean

For season $s$:

$$
r^{pre}_{i,s}
=
\mu_{g,s}
+
\rho
\left(
 r^{post}_{i,s-1}-\mu_{g,s-1}
\right)
+
X_{i,s}\beta
$$

where:

- $r^{post}_{i,s-1}$ is last season's final continuous rating.
- $\mu_g$ is the relevant group baseline.
- $\rho$ is offseason persistence.
- $X_{i,s}$ contains frozen preseason information.

Potential preseason features include:

- Prior multiyear performance.
- Returning production.
- Quarterback continuity.
- Recruiting talent.
- Transfer gains and losses.
- Head-coach continuity.
- Offensive and defensive coordinator continuity.
- FBS/FCS transition status.

ESPN's published preseason FPI methodology has described combining prior performance, returning starters, recruiting, and coaching tenure, with the greatest emphasis on more recent performance.[cite:42][cite:43]

### Multiple historical seasons

A generic historical state is:

$$
r^{hist}_{i,s}
=
\frac{
\sum_{k=1}^{K}w_k r^{post}_{i,s-k}
}{
\sum_{k=1}^{K}w_k
},
\qquad
w_1>w_2>\dots>w_K
$$

Tune $K$ and the decay pattern in chronological training folds. Do not estimate the weights using future evaluation seasons.

### Offseason uncertainty inflation

Mean regression determines where a team should begin. RD inflation determines confidence in that starting point.

$$
RD^{pre}_{i,s}
=
\min\left(
RD_{max},
\sqrt{
(RD^{post}_{i,s-1})^2+
\sigma^2_{offseason,i,s}
}
\right)
$$

Increase offseason variance for:

- Quarterback turnover.
- Large transfer or graduation losses.
- Head-coach or coordinator changes.
- Teams entering or leaving FBS.
- Teams with limited recent observations.
- Programs with historically unstable performance.

### Unit-specific carryover

Carry offense and defense separately:

$$
O^{pre}_{i,s}
=
\rho_O O^{post}_{i,s-1}
+
X^O_{i,s}\beta_O
$$

$$
D^{pre}_{i,s}
=
\rho_D D^{post}_{i,s-1}
+
X^D_{i,s}\beta_D
$$

Inflate unit uncertainty separately:

$$
(RD^O_{i,s})^{pre}
=
\sqrt{
((RD^O_{i,s-1})^{post})^2+
(\sigma^O_{offseason,i,s})^2
}
$$

$$
(RD^D_{i,s})^{pre}
=
\sqrt{
((RD^D_{i,s-1})^{post})^2+
(\sigma^D_{offseason,i,s})^2
}
$$

Estimate $\rho_O$ and $\rho_D$ independently. There is no requirement that offensive and defensive performance persist equally from year to year.

### External rankings

| Input | Recommended use | Do not do |
|---|---|---|
| Internal continuous rating | Primary carry-forward prior | Carry forward without regression or RD inflation |
| Predictive power rating | External prior or ensemble feature | Treat as error-free truth |
| AP or Coaches Poll | Weak nonlinear feature | Insert raw rank as interval-scale data |
| CFP ranking | Résumé/context feature | Treat as pure predictive strength |
| Unranked | Censored or missing ranking | Assign every unranked team equal strength |

If ordinal polls are included, use rank percentiles, splines, or a latent-score transformation. Freeze every poll at its historical publication timestamp.

---

## Home-field advantage

Start with one global home-field coefficient:

$$
\widehat{M}_t
=
r_{h,t}-r_{a,t}+H+X_t\beta
$$

Only add conference-, stadium-, or team-specific home-field effects after the global model is stable. These effects should be partially pooled because individual venues have limited observations and strength can be confounded with home performance.

Neutral-site games should set $H_t=0$, subject to a verified site classification. Semi-neutral rivalry games require explicit venue rules rather than relying only on the home-team field supplied by a data provider.

---

## From ratings to probabilities

If margin residuals are approximately distributed with cumulative distribution function $F$, home win probability is:

$$
P(Home\ Win)
=
1-F(-\widehat{M}_t)
$$

Under a Gaussian approximation:

$$
P(Home\ Win)
=
\Phi\left(
\frac{\widehat{M}_t}
{\sqrt{\sigma_M^2+P_{h,t}+P_{a,t}}}
\right)
$$

For offense/defense models, posterior uncertainty in both PPP predictions and possessions should propagate into the margin and total distributions. Simulation is convenient once the component states are fit:

1. Draw offensive and defensive states from their pregame distributions.
2. Draw possessions from the pace model.
3. Draw team scoring efficiency conditional on the matchup.
4. Convert possessions and efficiency into scores.
5. Summarize win, cover, and total probabilities.

---

## Database implementation

### Recommended tables

| Table | Grain | Key fields |
|---|---|---|
| `core.fact_game` | One row per game | IDs, season, week, kickoff, teams, venue, scores, subdivision flags |
| `core.fact_team_game` | One row per team-game | points, possessions, PPP, opponent, garbage-time treatment |
| `core.dim_team_season` | One row per team-season | subdivision, conference, staff, roster context |
| `mart.preseason_team_features` | One row per frozen team-season snapshot | prior states, roster, recruiting, transfers, quarterback, staff |
| `model.team_rating_state` | One row per team/state/timestamp | means, variances, RD, pre/post timing, model version |
| `model.game_prediction` | One row per model/game/run | margin, total, win probability, intervals, pregame states |
| `model.game_rating_update` | One row per team-game/state | expectation, actual, residual, gain, pre/post states |
| `qa.rating_update_audit` | One row per validation check | leakage, duplicates, variance, chronology, missing opponent |

### Suggested rating-state schema

```sql
create table if not exists model.team_rating_state (
    model_version varchar not null,
    team_id bigint not null,
    game_id bigint,
    season integer not null,
    week integer,
    state_type varchar not null,
    state_timing varchar not null,
    rating_mean double not null,
    rating_variance double not null,
    rating_deviation double not null,
    process_variance double,
    observation_variance double,
    residual double,
    update_gain double,
    as_of_timestamp timestamp not null,
    created_at timestamp default current_timestamp,
    primary key (
        model_version,
        team_id,
        game_id,
        state_type,
        state_timing
    )
);
```

Valid `state_type` values could include:

- `overall`
- `offense_ppp`
- `defense_ppp`
- `pace`

Valid `state_timing` values should include `pregame` and `postgame`.

### Prediction table

```sql
create table if not exists model.game_prediction (
    model_version varchar not null,
    run_id varchar not null,
    game_id bigint not null,
    as_of_timestamp timestamp not null,
    expected_home_ppp double,
    expected_away_ppp double,
    expected_possessions double,
    expected_margin double,
    expected_total double,
    home_win_probability double,
    margin_sd double,
    total_sd double,
    market_spread double,
    market_total double,
    spread_edge double,
    total_edge double,
    primary key (model_version, run_id, game_id)
);
```

### Immutable snapshots

Always store both pregame and postgame states. Never reconstruct an old pregame estimate from the latest team record. Every prediction should point to:

- Model version.
- Parameter version.
- Feature snapshot timestamp.
- Market timestamp, if applicable.
- Exact pregame rating states.
- Data cutoff timestamp.

---

## Python implementation

### State object

```python
from dataclasses import dataclass

@dataclass(frozen=True)
class State:
    mean: float
    var: float

    @property
    def rd(self) -> float:
        return self.var ** 0.5
```

### Process variance

```python
def add_process_variance(state: State, process_var: float) -> State:
    return State(mean=state.mean, var=state.var + process_var)
```

Process variance can depend on elapsed days, offseason status, roster disruption, or state type.

### PPP prediction

```python
def predict_team_ppp(
    offense: State,
    opponent_defense: State,
    baseline_ppp: float,
    home_ppp: float,
    context_effect: float,
) -> float:
    return (
        baseline_ppp
        + offense.mean
        - opponent_defense.mean
        + home_ppp
        + context_effect
    )
```

### Paired offense-defense update

```python
def paired_update(
    attacking_state: State,
    defending_state: State,
    observed: float,
    expected: float,
    observation_var: float,
    min_var: float = 1e-8,
):
    residual = observed - expected
    denom = attacking_state.var + defending_state.var + observation_var

    k_off = attacking_state.var / denom
    k_def = defending_state.var / denom

    new_off = State(
        mean=attacking_state.mean + k_off * residual,
        var=max(attacking_state.var * (1.0 - k_off), min_var),
    )

    new_def = State(
        mean=defending_state.mean - k_def * residual,
        var=max(defending_state.var * (1.0 - k_def), min_var),
    )

    return {
        "offense": new_off,
        "defense": new_def,
        "residual": residual,
        "offense_gain": k_off,
        "defense_gain": k_def,
    }
```

### Full game update

```python
def update_game(home, away, game, params):
    home_off = add_process_variance(home.offense, params.q_off)
    home_def = add_process_variance(home.defense, params.q_def)
    away_off = add_process_variance(away.offense, params.q_off)
    away_def = add_process_variance(away.defense, params.q_def)

    expected_home_ppp = predict_team_ppp(
        offense=home_off,
        opponent_defense=away_def,
        baseline_ppp=params.baseline_ppp,
        home_ppp=params.home_ppp,
        context_effect=game.home_context_effect,
    )

    expected_away_ppp = predict_team_ppp(
        offense=away_off,
        opponent_defense=home_def,
        baseline_ppp=params.baseline_ppp,
        home_ppp=0.0,
        context_effect=game.away_context_effect,
    )

    home_attack = paired_update(
        attacking_state=home_off,
        defending_state=away_def,
        observed=game.home_ppp,
        expected=expected_home_ppp,
        observation_var=params.ppp_observation_var,
    )

    away_attack = paired_update(
        attacking_state=away_off,
        defending_state=home_def,
        observed=game.away_ppp,
        expected=expected_away_ppp,
        observation_var=params.ppp_observation_var,
    )

    return {
        "home_offense": home_attack["offense"],
        "home_defense": away_attack["defense"],
        "away_offense": away_attack["offense"],
        "away_defense": home_attack["defense"],
        "expected_home_ppp": expected_home_ppp,
        "expected_away_ppp": expected_away_ppp,
        "home_residual": home_attack["residual"],
        "away_residual": away_attack["residual"],
        "gains": {
            "home_offense": home_attack["offense_gain"],
            "away_defense": home_attack["defense_gain"],
            "away_offense": away_attack["offense_gain"],
            "home_defense": away_attack["defense_gain"],
        },
    }
```

### Offseason initialization

```python
def initialize_new_season(
    previous: State,
    current_group_mean: float,
    previous_group_mean: float,
    persistence: float,
    feature_effect: float,
    offseason_var: float,
    max_var: float,
) -> State:
    mean = (
        current_group_mean
        + persistence * (previous.mean - previous_group_mean)
        + feature_effect
    )

    variance = min(max_var, previous.var + offseason_var)
    return State(mean=mean, var=variance)
```

Run this independently for overall, offense, defense, and pace states.

### Centering states

```python
def center_states(states: dict[int, State]) -> dict[int, State]:
    center = sum(s.mean for s in states.values()) / len(states)
    return {
        team_id: State(mean=state.mean - center, var=state.var)
        for team_id, state in states.items()
    }
```

Center offense, defense, and pace separately after an update batch.

---

## Processing sequence

1. Ingest completed FBS and available FCS games.
2. Validate team identifiers, subdivision, conference, venue, kickoff order, and game status.
3. Create frozen preseason features for every team-season.
4. Initialize overall, offense, defense, and pace means and variances.
5. Sort games by actual kickoff timestamp rather than nominal week alone.
6. Add process variance before each team's next game.
7. Retrieve both teams' immutable pregame states.
8. Predict possessions, team PPP, margin, total, and win probability.
9. Save the prediction before reading the result.
10. Build cleaned observations with garbage-time and possession rules.
11. Calculate residuals and uncertainty-dependent gains.
12. Update both teams jointly.
13. Save immutable postgame states.
14. Recenter latent states where required.
15. Run QA checks.
16. Advance to the next kickoff.

---

## Parameter estimation

Estimate or tune:

- Initial FBS and FCS means.
- Conference and subdivision prior variance.
- Global home-field effect.
- Offensive home effect, if modeling PPP.
- Overall process variance.
- Offensive process variance.
- Defensive process variance.
- Pace process variance.
- Margin observation variance.
- PPP observation variance.
- Offseason persistence by state type.
- Offseason uncertainty inflation.
- Multiseason historical decay.
- Garbage-time thresholds or weights.
- Robust-likelihood degrees of freedom.
- Probability-calibration mapping.

Possible estimation strategies:

| Strategy | Advantage | Limitation |
|---|---|---|
| Grid/random search | Easy to implement | Can be inefficient and overfit |
| Maximum likelihood | Direct parameter estimates | Optimization can be difficult |
| Empirical Bayes | Good compromise for hierarchical priors | Understates some hyperparameter uncertainty |
| Full Bayesian inference | Complete posterior uncertainty | Computationally expensive |

Every tuned value must be selected within chronological training data. Do not choose parameters based on performance in the final evaluation seasons.

---

## Chronological backtesting

Use expanding-window season folds. For evaluation season $s$:

1. Train all hyperparameters using seasons before $s$.
2. Construct season-$s$ preseason states from information available before Week 1.
3. Walk through games in kickoff order.
4. Save each prediction before updating from the result.
5. Score the full season.
6. Repeat for season $s+1$.

### Metrics

| Output | Evaluation |
|---|---|
| Win probability | Log loss, Brier score, reliability, calibration slope/intercept |
| Margin | MAE, RMSE, mean bias, interval coverage |
| Total | MAE, RMSE, mean bias, interval coverage |
| Uncertainty | Error and coverage by RD bucket |
| FBS-FCS games | Prediction error, update magnitude, subsequent FBS-game performance |
| Early season | Weeks 1-3 error and calibration |
| Betting comparison | Error versus opener/close, CLV, post-vig return under preregistered rules |

### Required baselines

- Home-team base-rate model.
- Previous-season rating without roster adjustment.
- Standard Elo with home field.
- Ridge offense/defense ratings.
- Market-only prediction.
- Market plus Glicko-state residual model.

### Ablation tests

- Elo versus Glicko-style uncertainty.
- Glicko versus Glicko-2 volatility.
- Binary result versus scoring margin.
- Margin versus points per possession.
- Overall rating versus offense/defense ratings.
- Global versus hierarchical FCS treatment.
- Generic offseason decay versus roster-aware priors.
- One home-field parameter versus partially pooled venue effects.
- Model-only versus market-anchored prediction.

---

## Leakage controls

The following rules are mandatory:

- Never join final-season ratings to games played earlier in that season.
- Never use a poll published after the prediction timestamp.
- Never use final returning-production or roster files that were revised after kickoff unless reconstructing the historical snapshot.
- Never use closing lines when evaluating an earlier decision timestamp.
- Save pregame and postgame ratings separately.
- Sort same-day games by kickoff time if one game's result could affect another prediction.
- Fit FCS gaps, group priors, and rating decay only on historical training folds.
- Version all transformations and garbage-time rules.

---

## Quality-assurance tests

### State invariants

- Rating variance is positive.
- RD equals the square root of variance.
- Every update has one pregame and one postgame state.
- No team receives two updates for the same state and game.
- Centered offensive and defensive means remain approximately zero.
- Neutral-site games receive no ordinary home-field adjustment.

### Chronology invariants

- Prediction timestamp precedes kickoff.
- Pregame states use only earlier games.
- Offseason features are frozen before Week 1.
- Market data match the intended decision timestamp.

### FCS checks

- Every FCS opponent maps to a stable team identifier.
- Unknown FCS teams receive the configured group prior.
- FBS-FCS games do not create extreme rating movements from routine expected blowouts.
- FCS conference and subdivision means do not drift without cross-subdivision evidence.

### Reproducibility checks

- Replaying the same season with the same model version produces identical states.
- Every prediction can be traced to source games, parameters, and feature snapshots.
- Model changes create new versions rather than overwriting prior outputs.

---

## Recommended staged build

### Stage 1: Overall state

Build a single point-scale rating with variance, global home field, robust margin updates, hierarchical FBS/FCS priors, and offseason RD inflation.

### Stage 2: Unit states

Add offense and defense using points per possession. Keep the overall model as a benchmark and diagnostic.

### Stage 3: Pace and totals

Add a separate possessions model and produce total and margin distributions.

### Stage 4: Rich preseason priors

Add quarterback, roster, recruiting, transfers, returning production, and coaching continuity. Require improvements in locked early-season tests.

### Stage 5: Full state-space inference

Replace diagonal updates with a multivariate Kalman or Bayesian framework that retains covariance and hierarchical uncertainty.

---

## Final design recommendation

The recommended college-football system is not two independent copies of vanilla Glicko. It is a dynamic state-space model with Glicko-like uncertainty:

- One latent offense and one latent defense per team.
- Separate uncertainty for each unit.
- A separate pace state.
- Points per possession as the primary efficiency observation.
- Robust margin or scoring likelihoods.
- Hierarchical FBS/FCS priors.
- Continuous prior-season ratings with offseason mean regression.
- Unit-specific offseason uncertainty inflation.
- Immutable pregame and postgame snapshots.
- Strict chronological backtesting against simple and market baselines.

Start with the diagonal sequential implementation because it is transparent, fast, and auditable. Promote to a full Bayesian state-space model only after the simpler version demonstrates stable, out-of-sample improvement.

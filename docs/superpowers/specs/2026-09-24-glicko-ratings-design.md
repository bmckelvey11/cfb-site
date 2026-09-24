# Glicko-style margin ratings vs Elo and the vendor open — design

**Status:** declared 2026-09-24 (`f93ab320`, `76ec5171`) before any code existed, and
approved the same day. The model and tests are in `de4104f5` and the eval in `0c4da51b`. The
pre-score boundary step ran on 2014–2019 only, and its final grids are recorded below before
the scoring run. **Scored once (`be9d5692`): NO-GO.** G1 and G3 pass, G2 fails, and the
verdicts are stable under stress. Result:
[`../../glicko-ratings-2026-09-24.md`](../../glicko-ratings-2026-09-24.md).
**Cleared for descriptive use** (user decision, 2026-09-24):
- Glicko-margin may be shown as a team power rating with its RD, and as a pregame win
  probability. G1 and G3 support that: it ranks teams better than Elo, and its uncertainty is
  calibrated.
- It is not a price. It is never shown as an edge against a line or used to pick sides:
  that is what G2 failed.
**Question:** does a rating that carries a team's strength *and* its uncertainty from game
to game give a fair home margin that holds information the Bovada open lacks? It is a
candidate "new information source for the fair spread" for
[`objective-review-2026-09-23.md`](../../../research/spread/docs/objective-review-2026-09-23.md)
("What a build aimed at the user's yardstick would need", item 3).
**Design reference:** `Using Glicko for College Football.md` (user-supplied, 2026-09-24). Its
"Practical first version" is the scope, minus the roster prior.
**Builds on:**
- Release B's harness: `load_pool`/`snapshot` from `scripts/pregame_replay_audit.py`, and
  `_cluster_boot`/`classify_verdict` from `scripts/weekly_ratings_eval.py`.
- Its results: [`../../weekly-ratings-2026-09-23.md`](../../weekly-ratings-2026-09-23.md) and
  [`../../weekly-priors-2026-09-23.md`](../../weekly-priors-2026-09-23.md). Previous-season
  priors failed their declared stress rule for totals.
- [`../../dynamic-ratings-2026-09-23.md`](../../dynamic-ratings-2026-09-23.md): week-to-week
  drift *lost* to a static ridge for totals (+0.08 MAE). That result is why τ = 0 is on the
  grid below. A pick of τ = 0 means dynamics add nothing for margins either.

**Forecast skill only.** Nothing here grades a wager, computes a cover rate, or sets an edge
threshold. ATS needs a registered amendment first (objective review, item 1).

## Hypothesis card

| Field | Value |
| --- | --- |
| `hypothesis_id` | `HYP-G1-glicko-margin` |
| Claim | A Gaussian team state (mean + variance) updated from capped scoring margins forecasts the home margin better than Elo with a margin multiplier, and its disagreement with the Bovada open predicts where the margin lands. |
| Mechanism | The margin carries more information than win/loss. A per-team variance lets a team with little evidence (week 1, a new FBS member, a team after the offseason) move fast, and lets a well-measured team move slowly. |
| Primary target | Home scoring margin, FBS vs FBS, regular season. |
| Primary metrics | Paired MAE and paired CRPS difference against Elo-MOV. Encompassing slope against the open. Interval coverage. |
| Outer test | 2021–2025, one scoring run. This is **not** an untouched holdout: the archived spread margin work and Release B already used these seasons. The untouched test is 2026, which is out of scope here. |
| Follow-up if null | Record the null in the finding doc. Glicko ratings do not feed the fair spread. |

## Scope

| In | Out (where it goes) |
| --- | --- |
| Glicko-margin (below), four baselines, the open and the close as market references | Roster, talent, and returning-production prior: next rung, needs its own declared rule |
| Win probability and interval coverage from the same state | Glicko-2 volatility: later ablation |
| Weekly snapshots of the frozen model | Offense/defense split, totals: later |
| | ATS grading, CLV, thresholds: needs a registered amendment |
| | Serving in `weekly_slate.py`, warehouse tables, GUI: not in this release |

## Inputs

All read-only. The sha256 of each file goes in the manifest.

| File | Used for |
| --- | --- |
| `data/processed/games.csv` via `load_pool` | `game_id`, season, week, `season_type`, teams, final points, `spread` (a **median close** across books, `provider = "median"`; negative = home favoured), kickoff from raw JSON |
| `data/raw/games_<s>.json` | `neutralSite`, `homeClassification`/`awayClassification`, `homePregameElo`/`awayPregameElo` |
| `data/raw/lines_<s>.json` | Bovada `spreadOpen`, `homeMoneyline`, `awayMoneyline`; first Bovada row per game, as in core |

Coverage, profiled on 2026-09-24 (regular season):

- **The pool:** 13,515 games, 2013–2025. No kickoff is missing; 4 have a TBD start time.
- **Bovada `spreadOpen`:** present **only in 2021–2025**, on 754–887 regular-season games a
  season. It is absent from every season from 2013 to 2020, so the open cannot enter tuning.
- **CFBD pregame Elo:** present on every FBS-vs-FBS game in every season. It is missing on
  most games that involve an FCS team.
- **FCS vs FCS:** absent from 2013 to 2021, then 506–663 games a season from 2022 to 2025.
- **Neutral sites:** 872 games.
- **Postseason:** 35–66 games a season.

## Game set and event clock

- **State updates:** every FBS-vs-FBS and FBS-vs-FCS game, regular season and postseason, in
  kickoff order, 2013–2025. 2013 is burn-in only. 2020 updates the state but is neither
  tuned nor scored.
- **FCS-vs-FCS games are excluded from the state in every season.** They exist only from
  2022, so including them would feed the score seasons evidence the tuning seasons never
  had: the parameters would be tuned in one data regime and scored in another. That limit
  is named in the finding doc, and including them is a later ablation.
- **Forecast clock: the week cutoff.** Each regular-season week $w$ has a cutoff: the earliest
  kickoff among its games. Every week-$w$ game is forecast from the state holding exactly
  the games that kicked off strictly before that cutoff, the same rule as `snapshot()`.
  This is Release B's clock. It is stricter than a per-game clock: a Thursday result does
  not inform that week's Saturday games. It is also closer to the open's information set,
  since the open is posted before the week starts.
- **Implementation:** one sorted event stream. Forecast events sit at week cutoffs, and
  update events sit at game kickoffs. At equal times a forecast runs first. A game whose
  kickoff moved outside its CFBD week is forecast at its own week's cutoff but updates the
  state only at its real kickoff, so no result can leak into an earlier forecast.
- **Scored:** regular-season games only. Postseason games update the state.

## Model: Glicko-margin (`glicko_margin_v1`)

Each team $k$ carries a mean $r_k$ in neutral-field points and a variance $u_k^2$.

$$
\begin{gathered}
\hat M_g = r_h - r_a + H\,(1-n_g), \qquad S_g = u_h^2 + u_a^2 + \sigma^2 \\[0.5em]
e_g = \operatorname{clip}\!\left(M_g,\,-C,\,C\right) - \hat M_g, \qquad K_h = \frac{u_h^2}{S_g}, \qquad K_a = \frac{u_a^2}{S_g} \\[0.5em]
r_h \leftarrow r_h + K_h\,e_g, \qquad r_a \leftarrow r_a - K_a\,e_g, \qquad u_k^2 \leftarrow u_k^2\,(1-K_k) \\[0.5em]
P(\text{home wins})_g = \Phi\!\left(\hat M_g / \sqrt{S_g}\right) \\[1em]
\begin{array}{rl}
\text{where}\quad h,\ a: & \text{home and away team of game } g \\
r_k: & \text{team } k\text{'s strength, points above the state's zero on a neutral field; + = stronger} \\
u_k^2: & \text{variance of } r_k\text{, points}^2\text{; } u_k \text{ is the team's rating deviation (RD)} \\
H: & \text{home-field edge, points; tuned} \\
n_g: & 1 \text{ if game } g \text{ is at a neutral site, else } 0 \\
\hat M_g: & \text{forecast home margin, points; + = home favoured} \\
M_g: & \text{actual home margin (home points} - \text{away points)} \\
\sigma^2: & \text{game-level margin noise variance, points}^2\text{; tuned} \\
S_g: & \text{forecast variance of the margin, points}^2 \\
C: & \text{margin cap, points; tuned (} \infty \text{ = no cap)} \\
e_g: & \text{residual of the capped margin, points} \\
K_h,\ K_a: & \text{gains, unitless, in } (0,1) \\
\Phi: & \text{standard normal CDF}
\end{array}
\end{gathered}
$$

This is a Kalman filter on a margin. Glicko's RD becomes the team's variance: it shrinks
with every game, and a large variance means a result moves the team a lot. The two gains
can differ, so a week-1 transfer-portal team with a large variance absorbs most of a
surprise that its well-measured opponent barely feels. $\hat M_g$ is always computed from
the state at the week cutoff, and the update applies after the game.

Worked number:
- **Forecast:** take $r_h = 10$, $r_a = 3$, $H = 2.75$, not neutral: $\hat M = 9.75$.
- **Variance:** with $u_h = u_a = 6$ and $\sigma = 15$, $S = 36+36+225 = 297$, so
  $\sqrt S = 17.2$. The home team wins with probability $\Phi(0.567) = 0.715$.
- **Update:** the home team wins by 21, so $e = 11.25$ and $K = 36/297 = 0.121$. The ratings
  move to 11.36 and 1.64, and each variance falls to $36 \times 0.879 = 31.6$ ($u = 5.62$).

Between games and seasons:

$$
\begin{gathered}
u_k^2 \leftarrow u_k^2 + \tau^2\,\frac{\Delta t_k}{7\ \text{days}} \qquad \text{(within a season)} \\[0.5em]
r_k \leftarrow w\,r_k + (1-w)\,\bar r_{c(k)}, \qquad u_k^2 \leftarrow u_k^2 + \delta^2 \qquad \text{(once, at each season start)} \\[1em]
\begin{array}{rl}
\text{where}\quad \tau^2: & \text{weekly drift variance, points}^2\text{; tuned; } \tau = 0 \text{ means no within-season drift} \\
\Delta t_k: & \text{time since team } k\text{'s variance was last advanced, inside the season} \\
w: & \text{offseason carry weight, } [0,1]\text{; tuned} \\
c(k): & \text{team } k\text{'s subdivision (FBS or FCS) in its latest game} \\
\bar r_{c}: & \text{mean } r \text{ over teams of subdivision } c \text{ that played in the season just ended} \\
\delta^2: & \text{offseason variance inflation, points}^2\text{; tuned}
\end{array}
\end{gathered}
$$

- **Drift within a season:** a team that is idle for one week gains exactly $\tau^2$ of
  variance. Variance is advanced to the forecast time before a forecast, and to the kickoff
  before an update.
- **The offseason step:** it separates *where a team starts* ($w$ pulls it toward its
  subdivision's mean) from *how sure we are* ($\delta^2$ widens it). No within-season $\tau^2$
  accrues across the offseason; $\delta^2$ stands in for it.
- **Worked number:** with $w = 0.7$, a +20 FBS team in a league whose FBS mean is +1 starts
  next season at $0.7 \times 20 + 0.3 \times 1 = 14.3$.
- **Unseen team:** it enters at its subdivision's current mean with variance $u_0^2$ (tuned).
- **Start of 2013:** every FBS team is at 0 and every FCS team at $m_0$, all with variance
  $u_0^2$. The seed $m_0$ is minus the mean margin by which FBS teams beat FCS teams in
  **2013** games. It comes from the burn-in season, so no tuning or scoring outcome enters
  it.
- **Subdivision changes:** a team moving from FCS to FBS is pulled toward the FCS mean in its
  transition offseason, because $c(k)$ is taken from its latest game. About one to four
  teams a year; named as a ceiling.

## Baselines (the ablation ladder)

Every rung is scored on the same games. The trial counts are in the tuning section.

1. **`hfa_only`:** $\hat M = \bar H(1-n_g)$, where $\bar H$ is the mean home margin of
   non-neutral FBS-vs-FBS regular-season games in 2014–2019. Its predictive sd is those
   games' margin sd, and its win probability is $\Phi(\hat M/s)$.
2. **`cfbd_elo`:** CFBD's own pregame Elo, an external benchmark. It maps to points as
   $\hat M = b(\text{Elo}_h - \text{Elo}_a) + H_c(1-n_g)$, with $b$ and $H_c$ fit by OLS on
   2014–2019. Its sd is the residual sd on the same games, and its win probability is
   $\Phi(\hat M/s)$. It is defined on FBS-vs-FBS games only.
3. **`elo_mov`:** Elo with a log margin-of-victory multiplier, a home edge, and an offseason
   regression, built on the same event clock and game set as Glicko-margin.

$$
\begin{gathered}
E_h = \frac{1}{1+10^{-(R_h - R_a + A(1-n_g))/400}}, \qquad
R_h \leftarrow R_h + K\,m_g\,(o_g - E_h), \qquad R_a \leftarrow R_a - K\,m_g\,(o_g - E_h) \\[0.5em]
m_g = \ln\!\left(|M_g|+1\right)\,\frac{2.2}{0.001\,\Delta_{w} + 2.2}, \qquad
\hat M_g = b\left(R_h - R_a + A(1-n_g)\right) \\[1em]
\begin{array}{rl}
\text{where}\quad R_k: & \text{Elo rating; FBS seeded at 1500, FCS at } 1500 + 25\,m_0 \\
A: & \text{home edge, Elo points; tuned} \\
E_h: & \text{expected score for the home team, also its win probability} \\
o_g: & 1 \text{ home win, } 0 \text{ away win} \\
K: & \text{update size, Elo points; tuned} \\
m_g: & \text{margin multiplier; } \Delta_w = \text{winner's Elo} - \text{loser's Elo, home edge included} \\
b: & \text{points per Elo point, fit by OLS through the origin on 2014–2019 for each grid point}
\end{array}
\end{gathered}
$$

The multiplier grows with the log of the margin, so going from 35 to 42 teaches less than
going from 7 to 14. The $\Delta_w$ term damps favourites' blowouts, which are expected, so
ratings do not inflate. At each season start $R \leftarrow w_e R + (1-w_e)\bar R_c$, the same
rule as the model above. The predictive sd for CRPS is the RMSE of $\hat M$ on 2014–2019.
Worked number: a 7-point win gives $m = \ln 8 \times 2.2/(0.001\,\Delta_w + 2.2)$, about
1.99 at $\Delta_w = 100$.

4. **`glicko1`:** Glickman (1999) Glicko, from `glicko.net/glicko/glicko.pdf`.
   - It has one game per rating period, the home edge in rating points, and RD growth $c$ per
     idle week.
   - Offseason: the mean regresses with $w_g$, and RD inflates by $\delta_g$ (with a cap of
     350).
   - FCS is seeded as in `elo_mov`.
   - It sees only win or loss. It is scored on **log loss and Brier only**; no margin is
     invented for it.
5. **`glicko_margin_v1`:** the model above.

**Market references**, on the same games:

- **`open`:** $\hat M = -\text{Bovada spreadOpen}$. This is the decision-time market.
  - **Distribution:** for CRPS it is $\mathcal N(\hat M, s_{\text{mkt}}^2)$, and its
    spread-implied win probability is $\Phi(\hat M / s_{\text{mkt}})$.
  - **Where $s_{\text{mkt}}$ comes from:** the RMSE of the open on the scored primary games
    themselves. Bovada has no opens before 2021, so the value cannot be tuned out of sample.
  - **Why that is fair:** CRPS and log loss are lowest at the true sd, so fitting it in
    sample gives the market its best case. That can only make the benchmark harder to beat.
  - **Not the close's RMSE:** it is narrower than the open's errors, so it would make the
    open overconfident and penalise the market.
  - **No decision-time moneyline exists.** The market's proper score is therefore
    spread-implied, not a de-vigged price, and every doc says so.
- **`close`** and **`close_ml`**: the median close, and Bovada's moneyline de-vigged
  multiplicatively. They are secondary and labelled **"not decision-time"** everywhere they
  appear. Bovada's moneylines carry no capture time, so they are treated as closing.

## Tuning

- **Seasons:** state from 2013; loss summed over 2014–2019 regular-season FBS-vs-FBS games.
  2020 and every score season are never read while tuning.
- **Loss:** each model is tuned on the score that matches its output.
  - Glicko-margin: mean CRPS of $\mathcal N(\hat M, S)$ against the uncapped margin. CRPS
    rewards the mean and the spread together, and it is comparable across caps.
  - `elo_mov`: mean squared error of $\hat M$.
  - `glicko1`: mean log loss.
- **Declared grids** (full factorial). The pre-score boundary step extended these; the final
  grids are in "Boundary step result" below.
  - **`glicko_margin_v1`:** 1,458 points.
    - $\sigma \in \{13, 15, 17\}$
    - $\tau \in \{0, 0.75, 1.5\}$
    - $w \in \{0.5, 0.7, 0.9\}$
    - $\delta \in \{3, 6, 9\}$
    - $C \in \{24, 38, \infty\}$
    - $H \in \{2, 2.75, 3.5\}$
    - $u_0 \in \{8, 14\}$
  - **`elo_mov`:** 36 points. $K \in \{20, 30, 40, 50\}$, $A \in \{50, 70, 90\}$,
    $w_e \in \{0.5, 0.67, 0.85\}$.
  - **`glicko1`:** 81 points. $c \in \{10, 20, 35\}$, $\delta_g \in \{50, 100, 150\}$,
    $A \in \{40, 65, 90\}$, $w_g \in \{0.5, 0.7, 0.9\}$, with $\text{RD}_0 = 350$.
  - **Closed-form fits:** `hfa_only` and `cfbd_elo`, 1 each.
- **Trial count:** 1,577 tuning configurations, plus any extension trials, plus the stress
  variants below. It goes in the manifest.
- **Pre-score boundary step** (reads tuning seasons only):
  - Before the one scoring run, `tune()` runs by itself from a scratchpad script.
  - Any axis whose pick lands on a grid edge that can be pushed further gets one more value
    outward, and that model is re-tuned. $\tau = 0$, $C = \infty$, and $w \in [0,1]$ are
    natural limits and are never pushed past.
  - The extension trials join the count. The final grids go into this spec in their own
    commit **before** the scoring run.
  - A pick still on an edge after one extension is flagged in the manifest and the doc.
- **No grid changes after scoring.**

**Boundary step result** (2026-09-24, tuning seasons only):

| Model | Edge picks on the declared grid | Added value | Final grid | Edge after extension |
| --- | --- | --- | --- | --- |
| `glicko_margin_v1` | σ low (13), w high (0.9), $u_0$ high (14) | σ 11, w 1.0, $u_0$ 20 | 3,888 points | none; the pick is unchanged |
| `elo_mov` | K high (50), A low (50), $w_e$ high (0.85) | K 60, A 30, $w_e$ 1.0 | 80 points | **K = 60, flagged** |
| `glicko1` | c low (10), $\delta_g$ high (150), $w_g$ high (0.9) | c 0, $\delta_g$ 200, $w_g$ 1.0 | 192 points | none |

- **Final trial count:** 3,888 + 80 + 192 + 2 closed-form fits = **4,162 tuning
  configurations**. Every declared grid is a subset of its final grid, so no trial is
  counted twice.
- **Why the K flag matters:** Elo-MOV may be slightly under-tuned, and a weaker baseline
  makes G1 slightly easier to pass. The finding doc states this next to G1.

## Scoring (2021–2025, one run, all parameters frozen)

**Primary population:** FBS vs FBS, regular season, with a Bovada `spreadOpen` present. Every
forecast is defined on every primary game. Expected size: about 3,900 games in about 75
season-week clusters.

**Secondary populations**, each reported and none gated:
- FBS-vs-FBS games with no open requirement. The open is dropped from this comparison.
- FBS vs FCS.

**Breakdowns** of every metric:
- Per season. Each score season is a walk-forward fold with frozen parameters.
- Per week bucket: 1–3, 4–7, and 8+.

**Metrics:**

- **Margin:** MAE, RMSE, bias (forecast minus actual), and CRPS for every rung with a
  distribution.
- **Paired differences**, loss(a) − loss(b) on the same games, using a season-week cluster
  bootstrap (`_cluster_boot`, 10,000 draws, seed 20260922), a percentile 95% interval, and
  MDE = 2.8 × bootstrap SE:
  - Glicko-margin against `open`, `elo_mov`, `cfbd_elo`, and `hfa_only`, on MAE and on CRPS.
  - `elo_mov` and `cfbd_elo` against `open`, on MAE.
  - Glicko-margin against `glicko1` and against the open's spread-implied probability, on
    log loss.
- **Encompassing slope** against the open, for Glicko-margin, `elo_mov`, and `cfbd_elo`:

$$
\begin{gathered}
M_g - L_g = a + \beta\left(\hat M^{F}_g - L_g\right) + \varepsilon_g \\[1em]
\begin{array}{rl}
\text{where}\quad L_g: & \text{the open on the home-margin scale, } -\text{spreadOpen, points} \\
\hat M^{F}_g: & \text{forecast } F\text{'s home margin, points} \\
a,\ \beta: & \text{OLS intercept and slope; interval from the same cluster bootstrap} \\
\varepsilon_g: & \text{residual, points}
\end{array}
\end{gathered}
$$

Read $\beta$ as how much of the forecast's disagreement with the open shows up in the
result. $\beta \approx 0$ means the forecast adds nothing the open lacks. $\beta > 0$ with an
interval clear of 0 means it carries information the open does not. $\beta = 1$ means its
disagreements are right on average at full size. For example, $\beta = 0.2$ means a 5-point
disagreement predicts the margin landing about 1 point toward the model.

- **Win/loss:** log loss and Brier for every rung, and for the open's spread-implied
  probability. The calibration intercept and slope come from a logistic regression of the
  outcome on $\operatorname{logit}(p)$, fit with numpy. The ideal values are 0 and 1.
- **Interval coverage:** the share of margins inside $\hat M \pm z\sqrt S$ for the 68% interval
  ($z = 1$) and the 95% interval ($z = 1.96$). It is reported pooled, and by quintile of the
  game's rating uncertainty $\sqrt{u_h^2 + u_a^2}$.

CRPS, for a normal forecast:

$$
\begin{gathered}
\text{CRPS}\left(\mathcal N(\mu, s^2),\, y\right) = s\left[z\left(2\Phi(z)-1\right) + 2\varphi(z) - \frac{1}{\sqrt\pi}\right], \qquad z = \frac{y-\mu}{s} \\[1em]
\begin{array}{rl}
\text{where}\quad \mu,\ s: & \text{forecast mean and sd of the margin, points} \\
y: & \text{actual margin, points} \\
\Phi,\ \varphi: & \text{standard normal CDF and density}
\end{array}
\end{gathered}
$$

CRPS is in points and lower is better. As $s \to 0$ it becomes $|y-\mu|$, the absolute
error, so it sits on MAE's scale and charges a forecast for being both off-centre and
over- or under-confident. A forecast that lands exactly on the result with $s = 15$ still
scores $15 \times 0.234 = 3.5$ points, which is the price of that spread.

## Declared go/no-go (primary population)

| Gate | Rule | Tests |
| --- | --- | --- |
| **G1 vs Elo** | `classify_verdict` on paired **CRPS**, Glicko-margin − `elo_mov`, is **improves**: interval upper bound < 0, and negative in at least 4 of 5 seasons. Paired MAE on the same games must also not be **worse** | The margin state and variance earn their complexity over plain Elo. The standard keeps MAE secondary when a model gives a full distribution, and MAE cannot see the variance |
| **G2 vs open** | The encompassing slope $\beta$ for Glicko-margin has a 95% lower bound > 0 | It holds information the open lacks. MAE against the open is reported with its verdict but not gated; beating the open outright is not expected |
| **G3 coverage** | Pooled 68% coverage in [0.65, 0.71], pooled 95% coverage in [0.93, 0.97], and every uncertainty quintile's 95% coverage in [0.90, 0.98] | The RD means what it says |
| **Stress** | Each of the 7 Glicko-margin parameters is moved to its neighbouring grid value(s), with the others held at the pick: at most 14 variants. G1 and G2 must keep their verdicts in every variant | The result is a plateau, not a spike |

- **GO** = G1, G2, and G3 all pass, and G1 and G2 are stable under stress.
  - A GO earns **only** the next step: register the ATS amendment, then take one prospective
    look at 2026.
  - A GO is not a bet.
- **Any failure is a NO-GO.** The doc names each gate that failed.
- **Nothing is re-tuned after scoring.** If a bug surfaces after scoring, the fix bumps
  `VERSION` and reruns once. Both runs and the updated trial count go in the doc.

## Sign check (runs before any fit; a failure stops the build)

| Game | `game_id` | Close `spread` | Home margin | Required |
| --- | --- | --- | --- | --- |
| 2023 wk 1, UT Martin at Georgia | 401520154 | −50.5 | +41 | $-$spread, margin, $\hat M$ all > 0 |
| 2022 wk 2, Alabama at Texas | 401403868 | +21.5 | −1 | all < 0 |
| 2024 wk 1, Georgia v Clemson, neutral (CFBD home: Georgia) | 401628323 | −10.5 | +31 | all > 0, $n_g = 1$ |

The spread and margin columns were read on 2026-09-24. $\hat M$ is checked once the model
runs, and the eval refuses to write results if any sign disagrees.

## Files and outputs

- **`scripts/glicko_ratings.py`:**
  - Contents: the event clock, the Glicko-margin state, forecast, update, and offseason
    step, `elo_mov`, `glicko1`, and a season runner that returns per-game forecasts and
    weekly snapshots.
  - `VERSION = "1.0"`.
- **`scripts/glicko_ratings_eval.py`:**
  - Contents: the loaders (pool plus raw JSON fields, a Bovada `spreadOpen` and moneyline
    loader mirroring `load_opens`), tuning, scoring, and the CLI.
  - It imports `load_pool` and `_sha256` from `pregame_replay_audit`, and `_cluster_boot`
    and `classify_verdict` from `weekly_ratings_eval`. It edits neither.
  - `snapshot()` is not imported. The event clock in `glicko_ratings.events` applies the same
    strictly-before rule, and test 5 pins it.
- **`scripts/glicko_ratings_table.py`** (added after scoring, for descriptive use):
  - Originally replayed `FROZEN_V1` through `load()`'s games.csv-based pool. **Superseded
    2026-09-24 (`c6433a68`):** per rung P1's declared adopt rule
    ([`2026-09-24-glicko-pool-design.md`](2026-09-24-glicko-pool-design.md)), it now replays
    `FROZEN_P1` through `glicko_pool_eval.load_pool_games` instead — every completed D-I game
    from the raw files, with conference-mean offseason targets. `FROZEN_V1` and this file's
    `load()` are unaffected and stay reproducible for v1's own record.
  - It writes `data/processed/ratings/glicko_ratings_<season>.csv`: rank within subdivision,
    rating in points above an average FBS team on a neutral field, RD, and games played.
  - Command: `python -m scripts.glicko_ratings_table --season 2026`.
  - To support it, `load()` now drops, and counts, games with no final score (lined games not
    yet played) instead of asserting. 2013–2025 has no such games, so the scored result is
    unchanged.
- **Command:**
  `python -m scripts.glicko_ratings_eval --tune-seasons 2014-2019 --score-seasons 2021-2025`.
  2020 is always skipped, and there are no other flags.
- **Outputs** (gitignored), in `data/processed/ratings/`:
  - `glicko_snapshots.csv`: Glicko-margin `r` and `u` per team at every week cutoff, with
    `season`, `week`, `as_of_ts`, `team`, `subdivision`, `n_games`, and `version`.
  - `glicko_eval.json`: the command, code and source sha256s, grid losses and picks,
    boundary flags, seeds ($m_0$, $\bar H$, $s_{\text{mkt}}$), every metric above, the
    verdicts, the stress runs, the trial count, population counts, and the sign check.

## Tests (`tests/test_glicko_ratings.py`, plain asserts, in-memory, no `CFB_DATA_ROOT`)

1. A zero residual leaves both means unchanged.
2. With equal variances, the two mean changes are equal and opposite.
3. An update never raises a variance, and a 7-day idle stretch raises it by exactly $\tau^2$.
4. The offseason step moves a mean toward its subdivision mean and adds exactly $\delta^2$.
5. No lookahead: a week-$w$ game's forecast is unchanged when every game at or after its
   week's cutoff is deleted, or given an extreme score.
6. Sign: a stronger home team gives $\hat M > 0$ and $P > 0.5$, and an open of −7 maps to
   +7.

## Commits

1. `docs(ratings)`: this spec. **Stop for approval.**
2. `feat(ratings)`: `glicko_ratings.py` and the tests.
3. `feat(ratings)`: `glicko_ratings_eval.py`.
4. `docs(ratings)`: the final grids from the pre-score boundary step, recorded in this spec.
   Then comes the one scoring run.
5. `docs(ratings)`: `docs/glicko-ratings-2026-09-24.md` and its `docs/README.md` row.

## Departures from the build prompt, for approval

- **FCS vs FCS is present from 2022.** The prompt said it was absent. It is excluded from
  the state in every season (see "Game set").
- **`mae_interval` is not used.** It is a game-level bootstrap, and the standard asks for
  clustering. Intervals use Release B's season-week `_cluster_boot`.
- **CRPS is added.** `docs/model-evaluation-standard.md` names CRPS for continuous predictive
  distributions. MAE stays for comparison with Release B and the open.
- **Week-cutoff clock, not per-game kickoff.** This keeps the information set comparable to
  the open's.
- **G1 gates on CRPS, with MAE as a guard.** The prompt named MAE against Elo. The standard
  makes distributional scores primary for a model that gives a distribution.

## What this design does not claim

- **No betting value.** The open has no capture time and no price. A GO licenses the ATS
  amendment, not a bet.
- **The screen is not holdout evidence.** 2021–2025 has served earlier questions. 2026 is
  the untouched test.
- **The pool is FBS-anchored.** FCS teams are rated only from their FBS games, so FCS
  ratings are coarse by construction.
- **Neither the market's proper score nor the moneyline is decision-time.** The market's
  proper score is spread-implied because no timestamped moneyline exists, and the close and
  the moneyline are not decision-time.

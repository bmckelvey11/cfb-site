# The Glicko-margin rating: exact method

This is the living reference for the Glicko rating that the weekly rankings table uses. It
covers every step from raw game file to published rating: which games go in, how time is
kept, how a team enters, how each forecast and each update is computed, the offseason rule,
how the table is built, and how the rating is scored. It describes the code as it stands.
When the code changes, this doc changes in the same commit.

- **Current version:** P1.1 is P1's frozen parameters plus a separate forecast SD of 13.5.
  Every version is listed in [`glicko-versions.md`](glicko-versions.md), and the registry is
  [`scripts/glicko_versions.py`](../../scripts/glicko_versions.py).
- **Code:**
  - [`scripts/glicko_ratings.py`](../../scripts/glicko_ratings.py) holds the model and the clock.
  - [`scripts/glicko_pool_eval.py`](../../scripts/glicko_pool_eval.py) holds the game set and the
    FCS seed.
  - [`scripts/glicko_ratings_table.py`](../../scripts/glicko_ratings_table.py) builds the table.
- **Records behind each choice:**
  - [`glicko-ratings-2026-09-24.md`](glicko-ratings-2026-09-24.md): v1 and the clock.
  - [`glicko-pool-2026-09-24.md`](glicko-pool-2026-09-24.md): P1, the game pool and the
    conference target.
  - [`glicko-p2-2026-10-15.md`](glicko-p2-2026-10-15.md): the forecast SD of 13.5, and the
    preseason prior that was rejected.
  - [`glicko-adjustments-review-2026-10-16.md`](glicko-adjustments-review-2026-10-16.md): what
    the rating does not adjust for.
- **Rebuild the table:**
  `CFB_DATA_ROOT=... python -m scripts.glicko_ratings_table --season 2026`. Add
  `--version <name>` to build any other version.

## 1. What the rating is

Each team $k$ carries two numbers at every moment:

- $r_k$, its **rating**. This is how many points better than an average FBS team it is
  expected to be, on a neutral field.
- $u_k^2$, the **variance** of that rating, in points squared. Its square root $u_k$ is the
  **RD** (rating deviation), the uncertainty in points.

The model is a one-dimensional Kalman filter per team. Each team's strength is treated as a
normal random variable with mean $r_k$ and variance $u_k^2$. It drifts slowly within a season
and jumps at each offseason. Every game is a noisy measurement of the difference between two
teams' strengths. "Glicko" refers to the idea Glickman introduced: carry an uncertainty
alongside each rating, and let it grow when a team is idle and shrink when it plays. Unlike
Glicko-1, the measurement here is the **final point margin**, not win/loss. The update is
therefore exact Gaussian algebra, with no logistic approximation.

The only inputs are game results: home team, away team, final score, neutral-site flag,
kickoff time, each team's subdivision (FBS or FCS) and conference. The rating reads no box
score stats, betting lines, recruiting, returning production, injuries or weather.

## 2. Parameters

These are frozen in `FROZEN_P1` and `SIGMA_PRED_P1` in `scripts/glicko_ratings.py`.

| Symbol | Code | Value | Meaning | How it was chosen |
| --- | --- | --- | --- | --- |
| $\sigma$ | `sigma` | 15 | Game noise SD used in the gain, points | Tuned on 2014–19, grid {11, 13, 15, 17} |
| $\sigma_{pred}$ | `SIGMA_PRED_P1` | 13.5 | Game noise SD used in published intervals and win probabilities, points | Tuned on 2014–19, 11.0–16.0 step 0.5 |
| $\tau$ | `tau` | 1.5 | Within-season drift SD per week, points | Tuned, grid {0, 0.75, 1.5, 2.25} |
| $w$ | `w` | 0.7 | Share of last season's rating a team keeps at the offseason | Tuned, grid {0.5, 0.7, 0.9, 1.0} |
| $\delta$ | `delta` | 6 | Offseason shock SD, points | Tuned, grid {3, 6, 9} |
| $C$ | `cap` | ∞ | Margin cap, points (none) | Tuned, grid {24, 38, ∞} |
| $H$ | `hfa` | 2 | Home edge, points | Tuned, grid {1.25, 2, 2.75, 3.5} |
| $u_0$ | `u0` | 14 | Starting RD of a team never seen before, points | Tuned, grid {8, 14, 20} |
| $m_0$ | `m0` | −27.279 | Starting mean of the FCS subdivision, points | Computed from 2013 games (§5) |

Tuning used every grid combination: 6,912 points after one boundary extension on $H$ and
$\tau$. Each one was replayed and scored by mean CRPS (§10) on FBS-vs-FBS regular-season games
from 2014–2019, with 2013 as burn-in. The lowest score won. $\sigma_{pred}$ was tuned
separately afterwards, with every other parameter held fixed. No parameter was chosen on
2020 or later.

## 3. Which games go in

`glicko_pool_eval.load_pool_games` reads `raw/games_<season>.json` (CFBD) for every season
from 2013 through the season being rated. A game is kept when:

- `completed` is true and both `homePoints` and `awayPoints` are present, and
- both `homeClassification` and `awayClassification` are `fbs` or `fcs`.

So the pool is every completed Division I game: FBS vs FBS, FBS vs FCS, and FCS vs FCS. That
covers regular season and postseason, with or without a betting line. Games with a D-II,
D-III or unlabelled side are dropped and counted, as are unplayed or postponed games. Each
kept game becomes one row:

$$
\begin{gathered}
y_g = P^{home}_g - P^{away}_g \\[1em]
\begin{array}{rl}
\text{where}\quad y_g: & \text{the game's margin, home minus away, points; positive means the home team won} \\
P^{home}_g, P^{away}_g: & \text{final points scored by the home and away teams, overtime included}
\end{array}
\end{gathered}
$$

The margin is the raw final score difference. Overtime points count, and there is no cap or
garbage-time adjustment. A 31–28 overtime win enters as $+3$, the same as a 3-point
regulation win. Rows are sorted by kickoff, then by CFBD game id.

Other fields on the row:

- **Kickoff:** `startDate`, parsed as UTC.
- **Neutral-site flag:** `neutralSite`.
- **Season type:** `regular` or `postseason`.
- **Week.**
- **Subdivisions.**
- **Conferences:** `homeConference` and `awayConference`. CFBD labels each conference as of
  the season played, so realignment shows up in the season it happened.

## 4. The clock

`events()` turns the games into a time-ordered list of two kinds of event. Time $t$ is
measured in days since 1970-01-01 UTC.

- **Forecast event:** one per (season, season type, week), at that week's **cutoff**, which
  is the earliest kickoff of any game in that week. Every game in the week is forecast at this
  one moment.
- **Update event:** one per game, at its own kickoff. This is when the game's result enters
  the state.

At equal times a forecast sorts before an update. So a game that kicks off exactly at its
week's cutoff is forecast before it updates anything.

The rule is strict. A Saturday game's published forecast is taken at the week's first kickoff
(often Thursday night). It sees no result from that week, even a Thursday game between other
teams. This keeps the forecast close to what an opening line knows.

The update step is different: it recomputes the expected margin at the game's own kickoff.
Between the cutoff and kickoff, the teams' variances have drifted a little further (§6). A
team that plays twice in one week would also have its first result already counted. That
almost never happens in college football.

**Season boundary.** The first event of a new season triggers the offseason step (§8) for
every rated team, at that event's time. No within-season drift is charged across the gap
between seasons; the offseason shock replaces it.

## 5. How a team enters

The first time a team appears in a forecast event, `enter()` creates it with:

- **Rating:** its target mean. If the team has a conference label and that conference has a
  mean from a finished season, that conference mean is used. Otherwise the subdivision mean
  is used: 0 for FBS before any season ends, $m_0$ for FCS.
- **Variance:** $u_0^2 = 196$ (RD 14).

The FCS seed comes from the 2013 burn-in season:

$$
\begin{gathered}
m_0 = -\frac{1}{N}\sum_{g \in G_{2013}} d_g \\[1em]
\begin{array}{rl}
\text{where}\quad m_0: & \text{starting mean rating of FCS teams, points vs the FBS starting mean of 0} \\
G_{2013}: & \text{the } N \text{ completed FBS-vs-FCS games of 2013 (111 games)} \\
d_g: & \text{the FBS team's margin in game } g\text{, FBS points minus FCS points}
\end{array}
\end{gathered}
$$

FBS teams beat FCS teams by an average of 27.279 points in 2013, so FCS teams start at
−27.279. This seed is only used before the first offseason. After that, the FCS mean is
whatever the FCS teams' ratings actually are (§8). Reading 2013's results to set a 2013
starting value is a look ahead within the burn-in season. That is why 2013 is never tuned or
scored.

## 6. Drift between games

Before any forecast or update, each team's variance is advanced to the current time:

$$
\begin{gathered}
u_k^2 \leftarrow u_k^2 + \tau^2 \, \frac{t - t_k}{7} \\[1em]
\begin{array}{rl}
\text{where}\quad u_k^2: & \text{team } k\text{'s rating variance, points}^2 \\
\tau: & \text{drift SD per week, 1.5 points} \\
t: & \text{now, in days} \\
t_k: & \text{the last time team } k\text{'s variance was advanced, in days; then } t_k \leftarrow t
\end{array}
\end{gathered}
$$

Each idle week adds $\tau^2 = 2.25$ points² of variance, so a bye week makes a team's rating
slightly less certain. The mean does not move. Drift is charged continuously, so a game on
the Thursday after a Saturday game adds $2.25 \times 5/7 = 1.6$ points².

## 7. Forecast and update for one game

### Forecast

$$
\begin{gathered}
\hat{M} = r_h - r_a + H\,(1 - n) \qquad S = u_h^2 + u_a^2 + \sigma^2 \qquad s_{pred} = \sqrt{u_h^2 + u_a^2 + \sigma_{pred}^2} \\[1em]
\begin{array}{rl}
\text{where}\quad \hat{M}: & \text{expected home margin, points; positive favours the home team} \\
r_h, r_a: & \text{home and away ratings, points} \\
H: & \text{home edge, 2 points} \\
n: & \text{1 for a neutral-site game, else 0} \\
u_h^2, u_a^2: & \text{home and away variances after drift, points}^2 \\
S: & \text{variance of the margin used in the update gain, points}^2 \\
\sigma: & \text{game noise SD for the gain, 15 points} \\
s_{pred}: & \text{published forecast SD of the margin, points} \\
\sigma_{pred}: & \text{game noise SD for published intervals, 13.5 points}
\end{array}
\end{gathered}
$$

$\hat{M}$ is the fair home margin. The published spread is $-\hat{M}$, so a negative spread
means the home team is favoured. The forecast distribution of the margin is normal with
mean $\hat{M}$ and SD $s_{pred}$. The home win probability is

$$
\begin{gathered}
p_{home} = \Phi\!\left(\hat{M} / s_{pred}\right) \\[1em]
\begin{array}{rl}
\text{where}\quad p_{home}: & \text{probability the home team wins, 0 to 1} \\
\Phi: & \text{the standard normal CDF}
\end{array}
\end{gathered}
$$

$\sigma$ and $\sigma_{pred}$ differ on purpose. In P1 the single $\sigma = 15$ did two jobs:
it set how fast ratings learn, and it set how wide forecasts are. 15 was the best learning
speed, but it made the forecasts too wide. On 2021–25, 72.3% of margins landed inside the
"68%" interval, and win probabilities were squeezed toward 50%. P1.1 keeps 15 for learning and
uses 13.5 for the published spread. That gives 68.9% coverage at 68%, and a calibration slope
of 1.005. Ratings and ranks are identical between P1 and P1.1.

**Worked example.**

- **Inputs:** home team $r_h = 10$, $u_h^2 = 50$; away team $r_a = 4$, $u_a^2 = 50$; not
  neutral.
- **Expected margin:** $\hat{M} = 10 - 4 + 2 = 8$, so the fair spread is home −8.
- **Forecast SD:** $s_{pred} = \sqrt{100 + 182.25} = 16.8$.
- **Win probability:** $p_{home} = \Phi(0.476) = 0.683$.
- **68% interval:** the margin should land between −8.8 and +24.8 about 68% of the time.

### Update

At the game's kickoff, $\hat{M}$ and $S$ are recomputed from the state at that instant. The
result then moves both teams:

$$
\begin{gathered}
e = \operatorname{clip}(y, -C, C) - \hat{M} \qquad K_h = \frac{u_h^2}{S} \qquad K_a = \frac{u_a^2}{S} \\
r_h \leftarrow r_h + K_h\, e \qquad r_a \leftarrow r_a - K_a\, e \qquad u_h^2 \leftarrow (1 - K_h)\, u_h^2 \qquad u_a^2 \leftarrow (1 - K_a)\, u_a^2 \\[1em]
\begin{array}{rl}
\text{where}\quad e: & \text{the surprise, actual home margin minus expected, points} \\
y: & \text{actual home margin, points} \\
C: & \text{margin cap, points (}\infty\text{ in P1, so no cap)} \\
K_h, K_a: & \text{Kalman gains, unitless, between 0 and 1}
\end{array}
\end{gathered}
$$

A team moves by its own gain times the surprise. The home team moves up when it beats
expectations, and the away team moves down by its own gain. A team's gain is its share of
the total uncertainty. An unsure team (large $u^2$) learns a lot from one game, and a settled
team learns little. Every game shrinks both variances.

**Worked example, continued.** Say the home team wins by 20.

- **Surprise:** $e = 20 - 8 = 12$.
- **Gain:** $S = 325$, so $K_h = K_a = 50/325 = 0.154$.
- **Ratings:** the home rating rises to 11.85 and the away rating falls to 2.15.
- **Variances:** both fall from 50 to 42.3, so RD goes from 7.07 to 6.51.

**The update is not zero-sum.** When the two variances differ, the two teams move by
different amounts. Take a settled team ($u^2 = 50$) that beats a new team ($u^2 = 150$) by 10
more than expected. $S = 425$, so the settled team gains 1.18 points and the new team loses
3.53. The new team's rating carries most of the information.

**What the update does not do.** Only the two teams in the game move. Beating a team that
later turns out to be good does not raise your rating after the fact. That team's later
wins move only that team, never its past opponents. This is the "schedule strength credit"
gap. Candidate A (§12) is built to test it.

## 8. The offseason

When a new season's first event arrives, `season_start(ended, t)` runs once:

1. **Subdivision means.** For FBS and for FCS, the mean rating of the teams of that
   subdivision that played in the ended season.
2. **Conference means.** For each conference, the mean rating of the teams whose most
   recent conference label is that conference and that played in the ended season. Both
   kinds of mean are taken before anyone regresses.
3. **Regression and shock.** Every rated team then gets the following, including teams that
   did not play in the ended season:

$$
\begin{gathered}
r_k \leftarrow w\, r_k + (1 - w)\, m_k \qquad u_k^2 \leftarrow u_k^2 + \delta^2 \\[1em]
\begin{array}{rl}
\text{where}\quad w: & \text{carryover, 0.7} \\
m_k: & \text{team } k\text{'s target: its conference mean if one exists, else its subdivision mean, points} \\
\delta: & \text{offseason shock SD, 6 points (so } \delta^2 = 36\text{)}
\end{array}
\end{gathered}
$$

A team keeps 70% of its distance from its conference's average. A team rated 11.85 in a
conference whose mean is 3.0 starts the next season at $0.7 \times 11.85 + 0.3 \times 3.0 =
9.20$. Its variance grows by 36, from 42.3 to 78.3 (RD 6.5 → 8.85), so early-season results
move it faster. The drift clock is reset to $t$, and each team's games-played counter goes
back to 0.

**Why the conference target.** P1 pulls each team toward its conference mean. v1 pulled
toward the subdivision mean. The conference version won on 2014–19 tuning CRPS (9.207 vs
9.270). It also rates FCS teams far better, because an FCS team in a strong conference is
not dragged toward the whole FCS average.

**A known quirk.** The target uses the conference a team played in **last** season. Its new
label only arrives with its first game of the new season. So Texas and Oklahoma regressed
toward the 2023 Big 12 mean before 2024, not the SEC's. This uses last season's peers and is
not a leak. Candidate B (§12) tests using the new conference instead.

Subdivision changes work the same way. A team moving from FCS to FBS keeps its rating, and
its subdivision label changes with its first FBS game.

## 9. The published table

`glicko_ratings_table.py --season S` does the following:

1. It replays every game from 2013 through the latest completed game of season S, in one
   continuous state. Nothing is re-tuned.
2. It takes `as_of` = the latest kickoff among season S's completed games.
3. It keeps the teams that played in season S and advances each one's variance to `as_of`
   (§6). The RD is therefore as of the table date, not as of each team's last game.
4. It **re-centres** the ratings so the mean of this season's FBS teams is exactly 0. The
   filter's own zero point wanders a little over the years, because means are not conserved
   (§7, "not zero-sum"). Re-centring keeps "points above an average FBS team" true. Rating
   differences, and therefore forecasts, do not change.
5. It ranks teams within their subdivision by rating, with ties sharing the lower rank.
6. It writes `data/processed/ratings/glicko_ratings_<S>.csv`. Columns: subdivision, rank, team,
   rating (1 decimal), rd (1 decimal), games, as_of, version.

**How to read a row.**

- **Rating:** Ohio State 24.0 vs Penn State 19.0 means Ohio State is 5 points better on a
  neutral field. At Ohio State it would be favoured by 7, because the home edge adds 2.
- **RD:** about two thirds of the time, the team's "true" rating sits within ±RD of the
  shown rating. The two-team forecast SD is about 16–17 points mid-season. Most of that is
  game noise ($\sigma_{pred} = 13.5$), not rating uncertainty.

## 10. How it is scored

**CRPS** is the main score. It is a proper score for the whole forecast distribution, in
points:

$$
\begin{gathered}
\mathrm{CRPS}(\mu, s; y) = s\left[z\,\bigl(2\Phi(z) - 1\bigr) + 2\varphi(z) - \frac{1}{\sqrt{\pi}}\right], \qquad z = \frac{y - \mu}{s} \\[1em]
\begin{array}{rl}
\text{where}\quad \mu: & \text{forecast mean margin } \hat{M}\text{, points} \\
s: & \text{forecast SD, points} \\
y: & \text{actual margin, points} \\
\varphi, \Phi: & \text{standard normal density and CDF}
\end{array}
\end{gathered}
$$

CRPS rewards being close and being honest about uncertainty. A sure-sounding forecast that
misses is punished more than a wide one. For a perfect point forecast it reduces to 0. When
$s$ is tiny it reduces to the absolute error. Lower is better. P1.1's mean CRPS on 2021–25
FBS-vs-FBS regular-season games is 8.891, and its MAE is 12.577.

**Other scores reported:**

- MAE of $\hat{M}$.
- Win log loss.
- 68% and 95% interval coverage.
- Calibration slope of the win probability. 1 is ideal; above 1 means the probabilities are
  too timid.
- The encompassing slope against the Bovada open. It answers whether the rating's
  disagreement with the open predicts the result.

**Comparisons are paired:** each model is scored on the same games. The interval comes from a
season-week block bootstrap, which resamples whole weeks so that games on the same
Saturday are not treated as independent.

**Windows:**

- 2013 is burn-in.
- 2014–2019 is tuning.
- 2020 updates the state but is never scored.
- 2021–2025 has now been scored three times on this family (v1, P1, P2). It is reported but
  cannot decide anything.
- Anything after 2026-10-16 belongs to sealed holdouts (§11).

**Trials:** 21,691 fits have been run on this family through the P3-D freeze. Any new result
has to be read against that count.

## 11. What is sealed

- **P1's 2026 confirmation** (`scripts/glicko_p1_confirm.py`) reads P1's encompassing slope
  against the Bovada open once, after the 2026 regular season. It is protected by a
  **forecast fingerprint**: the sha256 of (game id, mean, SD) for P1's 3,718 scored
  2021–25 games. Any code change that alters one P1 forecast trips it. This is why every
  later idea is built as a new class whose default settings reproduce P1 exactly.
- **P3 bundle holdout:** games kicking off after 2026-10-16T23:59Z, through 2027. The picks
  and fingerprints are in `scripts/glicko_p3_frozen.json`. The interim look is not before
  2027-01-20, and the final look is not before 2028-01-20.
- **P3-D holdout:** games kicking off after 2026-10-17T12:00Z, through 2027, on the same look
  dates. Its pick and fingerprint are in `scripts/glicko_p3d_frozen.json`.

## 12. Candidates under test (not part of the live rating)

These are built and frozen but are **not** used by the table, except as clearly labelled
experimental columns. They are declared in
[`superpowers/specs/2026-10-16-glicko-p3-bundles-design.md`](specs/2026-10-16-glicko-p3-bundles-design.md),
and the code is in `scripts/glicko_p3.py`.

**A. Schedule strength (`GlickoFull`).** One joint filter over all teams, carrying the
covariance between every pair:

$$
\begin{gathered}
v = P_{\cdot h} - P_{\cdot a} \qquad \mathbf{r} \leftarrow \mathbf{r} + v\, \frac{e}{S} \qquad P \leftarrow P - \frac{v\, v^{\top}}{S}, \qquad S = P_{hh} + P_{aa} - 2P_{ha} + \sigma^2 \\[1em]
\begin{array}{rl}
\text{where}\quad \mathbf{r}: & \text{vector of every team's rating, points} \\
P: & \text{covariance matrix of all ratings, points}^2\text{; its diagonal is each } u_k^2 \\
P_{\cdot h}, P_{\cdot a}: & \text{the home and away teams' columns of } P \\
v: & \text{each team's covariance with (home} - \text{away), points}^2 \\
e: & \text{the surprise, as in §7}
\end{array}
\end{gathered}
$$

Say A beat B earlier. Their ratings are then correlated. When B later beats C by a lot, A's
rating also rises, in proportion to how strongly A's estimate is tied to B's. The diagonal-only
version of this update is exactly P1's. At each offseason every cross-covariance is reset to
0, and each variance gets $+\delta^2$, as in P1. Frozen pick: $\sigma = 15$.

**B. Preseason start (`GlickoStart`).** Three changes to the offseason target:

- A conference switcher regresses toward its **new** conference's mean. The new conference is
  known from the published schedule.
- The target blends in a 3:2:1-weighted average of the team's own last three final ratings,
  with weight $h$.
- Carryover $w$ can scale with transfer-aware returning production. Tuning gave this weight
  0, so it is effectively off.

Frozen pick: $h = 0.3$, $w = 0.6$.

**C. Game context (`GlickoContext`).**

- The home edge follows a season trend, with 2020 as its own value: $H(s) = 2.75 - 0.05(s -
  2013)$.
- An overtime game updates as a regulation tie.
- Postseason and FBS-vs-FCS games get observation variance × 1.5.
- A neutral-site game within 150 miles of one campus gives that team half the home edge.
- A time-zone term adds 0.5 points per zone the away team crossed.

**D. FBS vs FCS (`GlickoShrinkX`).** The diagnostics found that P1's FBS-vs-FCS forecasts are
about 15% too extreme: residual slope −0.149 [−0.204, −0.096]. FBS teams still win big, but by
less than P1 predicts. Bundle D multiplies the expected margin of every FBS-vs-FCS game by
$(1 - \lambda)$, in the forecast and in the update's surprise. Gains, variances and all other
games are unchanged.

- **Frozen pick:** $\lambda = 0.05$, so a 30-point forecast becomes 28.5, with σ_pred 12.5.
- **Its plan:**
  [`superpowers/specs/2026-10-17-glicko-p3d-fcs-design.md`](specs/2026-10-17-glicko-p3d-fcs-design.md).
- **2021–25, descriptive only:** it improves FBS-vs-FCS CRPS by 0.050, but the slope only
  moves from −0.149 to −0.110. A flat shrink fixes about a quarter of the problem.
- **Caveat:** its single σ_pred of 12.5, tuned on FCS games, makes its FBS-vs-FBS intervals a
  little narrow.

None of these goes live unless it passes its declared holdout test. **2021–25 numbers for
them are descriptive only.**

## 13. What the rating does not do

- **No schedule-strength back-credit** (only candidate A tests it).
- **No preseason information** beyond last season's rating. There is no recruiting, returning
  production, coaching change or portal data in the live rating. The one tested prior (P2)
  made 2021–25 forecasts worse.
- **No margin cap, no garbage-time or overtime handling.** A 70–0 win counts as 70.
- **One home edge (2 points) for every team and era.**
- **No game-type weighting.** Bowls, rivalry games and FCS games all use the same noise.
- **No injuries, quarterback changes, weather or rest.**
- **No betting market input.** The rating is independent of the lines, which is what lets the
  encompassing test mean something.
- **D-II and D-III games are invisible.** A team's game against one simply does not exist.
- **No betting claim.** On 2021–25 the rating sits 0.46 points of MAE behind the Bovada
  open (v1 record). P1's encompassing slope is a second-look pass, not a confirmed edge, until
  the sealed 2026 confirmation is read.

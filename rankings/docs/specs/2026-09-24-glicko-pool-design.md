# Glicko-margin on a connected Division I pool (rung P1) — design

**Status:** declared 2026-09-24 (`e6443ec2`), approved same day, model change in `0e2e0373`,
eval script in `c28745e8`. **Scored once: ADOPTED.** `pool_conf` beats v1 on both required
CRPS tests and is stable under stress. G2 (encompassing β vs the open) newly passes as a
second-look result, not a confirmed GO — see the result for what that does and does not mean.
Result: [`../../glicko-pool-2026-09-24.md`](../../glicko-pool-2026-09-24.md). Table switched
in `c6433a68`.
**Descriptive-use clearance carries over** from v1's (`4c505ce8`): show the rating and RD as
a power rating and win probability, never as an edge against a line. P1's own G3 failed on
the wide side (68% intervals cover 72.8%), so its RD reads a little more cautious than its
actual error — still descriptive, not a reason to withhold it, but named here rather than
silently inherited.
**Question:** does rating every Division I team from every Division I game, with FCS and FBS
teams pulled toward their conference's mean, forecast better than `glicko_margin_v1`, which
sees only games that had a betting line?
**Builds on:** [`2026-09-24-glicko-ratings-design.md`](2026-09-24-glicko-ratings-design.md)
(v1) and its result [`../../glicko-ratings-2026-09-24.md`](../../glicko-ratings-2026-09-24.md):
NO-GO on G2, and G1 and G3 pass.
**Chosen by the user:** step 1 of 2. This rung builds the pool; the preseason-prior rung
follows as its own spec, on top of whichever base this rung adopts.
**Design reference:** user-supplied notes on FCS opponents and prior seasons (2026-09-24):
one connected FBS/FCS system, individual FCS ratings pooled toward conference priors, and
the FBS–FCS gap estimated from data rather than hard-coded.

**Forecast skill only**, as in v1. No wager is graded.

## Why now: the data v1 did not use

v1 read `games.csv`, which holds only games with a betting line. The raw CFBD files hold
every completed game. Counts of completed games (checked 2026-09-24):

| Seasons | FCS vs FCS in raw files | FCS vs FCS in `games.csv` | FBS vs FCS in raw files | FBS vs FCS in `games.csv` |
| --- | --- | --- | --- | --- |
| 2013–2019 | 596–666 a season | 0 | 98–114 | 67–111 |
| 2020 | 259 | 0 | 36 | 33 |
| 2021–2025 | 635–692 | 0 in 2021, 506–663 from 2022 | 117–126 | 106–126 |

- **FCS results are complete in every season**, so the reason v1 excluded FCS-vs-FCS games
  (tuning seasons had none) does not hold for the raw files.
- **Conference labels:** every FBS and FCS team carries one, across 11 FBS and 14 FCS
  conferences, independents included.

## Hypothesis card

| Field | Value |
| --- | --- |
| `hypothesis_id` | `HYP-P1-glicko-pool` |
| Claim | A state fed by every Division I game, with conference-level targets, forecasts FBS-vs-FBS margins no worse than v1, and forecasts FBS-vs-FCS margins better. |
| Mechanism | FCS ratings learn from about 11 games a season instead of about 1. That anchors the FBS–FCS gap and each FCS team's own level, and conference means give new or rarely seen teams a better starting point than one FCS-wide mean. |
| Primary metric | Paired CRPS, adopted P1 − v1, on v1's primary population (the same 3,718 games). |
| Secondary metric | Paired CRPS, adopted P1 − v1, on the 580 lined FBS-vs-FCS score-season games both models forecast. |
| Outer test | 2021–2025, one scoring run. **This is a second look at these seasons**, after v1. |
| Follow-up if null | v1 stays the base for the prior rung, and the null is recorded. |

## Model: two variants, one clock

Both variants use v1's `GlickoMargin` update, drift, offseason step, and win probability
unchanged. Only the game set and the pull targets change.

- **`pool_sub` (P1a):** every completed game in the raw files where both teams are FBS or
  FCS, 2013 onward. The pull targets are the subdivision means, as in v1.
- **`pool_conf` (P1b):** the same games. Each team's offseason pull target, and the level a
  new team enters at, is its conference's mean:

$$
\begin{gathered}
\bar r_{c} = \frac{1}{|T_{c}|}\sum_{j \in T_{c}} r_j, \qquad
r_k \leftarrow w\,r_k + (1-w)\,\bar r_{c(k)} \ \text{(offseason)}, \qquad
r_k^{\text{new}} = \bar r_{c(k)} \\[1em]
\begin{array}{rl}
\text{where}\quad c(k): & \text{team } k\text{'s conference in its latest game (independents form their own bucket per subdivision)} \\
T_{c}: & \text{teams of conference } c \text{ that played in the season just ended} \\
\bar r_{c}: & \text{their mean rating, points; recomputed at each season start before anyone regresses} \\
w: & \text{offseason carry weight, as in v1} \\
r_k^{\text{new}}: & \text{entry rating of a team seen for the first time}
\end{array}
\end{gathered}
$$

- **Fallback:** if $T_c$ is empty (the conference's first season in the data, or 2013 before
  any offseason), the subdivision mean stands in. That is v1's rule.
- **Worked number:** a Big Sky team at −30 in a conference averaging −24 moves to
  $0.9 \times (-30) + 0.1 \times (-24) = -29.4$. Under `pool_sub` it would move toward the
  FCS-wide mean instead.
- **What the tuning decides:** at v1's $w = 0.9$, the target moves a team by only 10% of the
  gap. If conference targets matter, the tuning will pick a smaller $w$.

**Game set rules:**
- **Games dropped and counted:** any game with a Division II, Division III, or unlabelled
  team (for example FCS vs D-II, 30–45 a season), and any game without a final score.
- **Game set:** 2013 is burn-in, 2020 updates the state, and postseason updates the state,
  all as in v1.
- **Seed:** the FCS seed $m_0$ comes from 2013 FBS-vs-FCS games, now all of them, not only
  the lined ones.

**Clock:**
- The rule is unchanged: each week's cutoff is the earliest kickoff among *all* that week's
  games in the set, and forecasts are taken at the cutoff.
- An FCS game that kicks off before the week's first FBS game makes the cutoff earlier, so
  P1's clock is **at least as strict as v1's**. Any bias this adds works against P1.

## Tuning and selection

- **Grid:** v1's final grid (3,888 points) for each variant. That is 7,776 configurations,
  plus the pre-score boundary step with the same rule as v1.
- **Loss:** mean CRPS on the same mask as v1: 2014–2019 regular-season FBS-vs-FBS games.
- **Selection:** the adopted P1 is the variant and grid point with the lowest **tuning**
  CRPS. The choice between `pool_sub` and `pool_conf` is made on tuning seasons only, never
  on scored ones.
- **Baselines** (`elo_mov`, `glicko1`, `cfbd_elo`, `hfa_only`) are not re-tuned. They and v1
  are reproduced exactly from v1's frozen picks.

## Scoring (2021–2025, one run)

- **Primary population:** v1's, the same 3,718 games. P1 forecasts are joined by `game_id`.
- **Paired differences**, with v1's season-week cluster bootstrap, seed, and MDE:
  - Adopted P1 − v1, on CRPS and MAE. This is the primary comparison.
  - `pool_conf` − `pool_sub`, at each variant's own tuned pick. This is attribution only.
  - The same comparisons on the 580 lined FBS-vs-FCS games.
- **Reported, not gated:** P1's MAE and bias on unlined FBS-vs-FCS games, and on FCS-vs-FCS
  games against v1's absence.
- **v1's gates re-read for the adopted P1:** G1 against Elo-MOV, G2 as the encompassing slope
  against the open, and G3 coverage.

## Declared rules

| Rule | Condition | Consequence |
| --- | --- | --- |
| **Adopt** | Adopted P1 − v1 on primary CRPS is **not worse**, **and** P1 − v1 on FBS-vs-FCS CRPS is **improves** (`classify_verdict`) | P1 replaces v1 as the base for the prior rung, and it takes over the weekly table |
| **Keep v1** | Either condition fails | v1 stays the base, and the null is recorded |
| **Stress** | The adopted P1's parameters are each moved one grid step, as in v1. The adopt verdict must hold in every variant | If it does not, the verdict is reported as unstable and v1 stays the base |
| **G2 on a second look** | If the adopted P1's encompassing lower bound is > 0 | Recorded as a **second-look pass, not a GO**. It becomes a GO only on a declared 2026 confirmation |

Nothing is re-tuned after scoring. A bug found after scoring gets one fix, `VERSION` 1.1, and
one rerun, with both runs recorded.

## Files

- **`scripts/glicko_ratings.py`:**
  - `_Teams` gains optional conference tracking: `enter` and `played` take a conference, and
    `season_start` computes conference means.
  - With no conference passed, behaviour is v1's exactly, and a test pins that.
- **`scripts/glicko_pool_eval.py`** (new):
  - A raw-JSON pool loader.
  - Tuning of both variants, with v1 reproduced from `FROZEN_V1` and the baselines from v1's
    tune rules.
  - Scoring through `glicko_ratings_eval`'s `scored_frame`, `paired`, `gates`, and `coverage`.
  - It writes `data/processed/ratings/glicko_pool_eval.json`.
  - `glicko_ratings_eval.py` is not changed, so v1 stays reproducible.
- **`tests/test_glicko_ratings.py`:**
  - v1 output is unchanged when no conference is passed.
  - The conference mean is the offseason target and the entry level, with a fallback to the
    subdivision mean.
  - The raw loader drops non-D-I games and counts them.
- **Docs:** a dated finding doc, `docs/glicko-pool-2026-09-24.md` or the date it lands, a
  `docs/README.md` row, and a status link here.

## Trial count

v1 used 4,162 tuning configurations and 13 stress variants. P1 adds 7,776 tuning
configurations, any boundary extensions, its stress variants, and 1 scoring run. The ledger
is cumulative in the finding doc.

## What this cannot claim

- **Not holdout evidence.** It is a second look at 2021–2025, and 2026 is the untouched test.
- **No betting value**, as in v1. A second-look G2 pass is not a GO.
- **Conference realignment lags by one offseason.** A team that changes conferences is pulled
  toward its old conference's mean for one offseason, because $c(k)$ comes from its latest
  game.
- **D-II and D-III opponents are not rated.** FCS games against them are dropped.

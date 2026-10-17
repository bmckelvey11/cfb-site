# Glicko-margin on a connected D-I pool (rung P1) — 2026-09-24

**Answer: ADOPTED, and a second-look pass on G2 — not a confirmed GO.**

- **Adopted:** `pool_conf`, the variant pulling each team toward its **conference** mean at
  the offseason, not the subdivision mean. It beat `pool_sub` on tuning CRPS (9.207 vs 9.270).
- **P1 vs v1, on v1's own primary population (3,718 games):** CRPS improves by 0.082
  [0.031, 0.137], MAE by 0.127 [0.050, 0.210]. Both rules of the adopt test pass.
- **P1 vs v1, on FBS-vs-FCS games (580 games):** CRPS improves by 0.829 [0.401, 1.244], MAE
  by 1.269 [0.588, 1.939]. This is the gap the pool was built to close.
- **Stable under stress:** the adopt verdict holds in all 13 one-step parameter variants.
- **G1 (vs Elo-MOV) strengthens:** CRPS gain widens from v1's −0.331 to −0.413.
- **G2 (encompassing slope vs the open) now passes:** β = 0.193 [0.052, 0.329], clear of 0.
  v1 failed this gate. **This is a second look at 2021–2025**, already scored once for v1, so
  per the declared rule this is recorded as a second-look pass, not a GO. It becomes a GO
  only on a declared 2026 confirmation.
- **G3 (coverage) fails, on the wide side.** Pooled 68% coverage is 72.8%, above the declared
  [65%, 71%] band. P1's intervals are a little wider than its own error, not narrower.
- **Per the spec's declared rule, P1 replaces v1 as the base for descriptive use and the
  weekly ratings table.**

**Question.** Does rating every Division I team from every Division I game — with FCS teams
pulled toward their conference's mean instead of one FCS-wide mean — forecast better than
v1 (`glicko_margin_v1`), which saw only games that had a betting line?

**Design:**
[`superpowers/specs/2026-09-24-glicko-pool-design.md`](superpowers/specs/2026-09-24-glicko-pool-design.md).
**Builds on:** [`glicko-ratings-2026-09-24.md`](glicko-ratings-2026-09-24.md) (v1, NO-GO on
G2). **Reproduce:** `python -m scripts.glicko_pool_eval`
([`scripts/glicko_pool_eval.py`](../scripts/glicko_pool_eval.py)). It writes
`data/processed/ratings/glicko_pool_eval.json`, which holds every number below. This was the
one scoring run: code at `c28745e8`, no bug found after scoring.

## Why the pool exists

v1 read `games.csv`, which keeps only games that carried a betting line. The raw CFBD files
hold every completed Division I game — FCS-vs-FCS included, in every season from 2013. v1
excluded FCS-vs-FCS entirely because `games.csv` had none of it before 2022. Read from the
raw files instead, that reason disappears: 2013–2019 alone holds 596–666 completed
FCS-vs-FCS games a season. FCS teams in v1 were rated from roughly one FBS-vs-FCS game a
year; in the pool they are rated from a full FCS schedule.

## Method

- **Two variants**, both using v1's `GlickoMargin` update unchanged — only the game set and
  the offseason pull target change:
  - `pool_sub`: pull toward the subdivision mean (v1's rule).
  - `pool_conf`: pull toward the conference mean, falling back to the subdivision mean when
    no team from that conference has played yet.
- **Selection:** whichever variant has the lower CRPS on 2014–2019 tuning seasons is adopted.
  The choice never reads a scored season.
- **Game set:** every completed game from the raw files where both teams are FBS or FCS,
  2013 through 2025. Games with a D-II, D-III, or unlabelled side are dropped and counted, as
  are games with no final score.
- **Clock:** unchanged from v1 — each week's cutoff is its earliest kickoff, now across the
  fuller game set, so P1's clock can only be at least as strict as v1's.
- **v1 side of the comparison:** reproduced from v1's frozen manifest
  (`data/processed/ratings/glicko_eval.json`), not re-tuned. Its FCS seed (−27.279) and
  primary-population MAE (12.682) were checked to reproduce exactly before scoring.

## Frozen picks

| Variant | Pick | Tuning CRPS | Grid points |
| --- | --- | --- | --- |
| `pool_sub` | σ 13, τ 0.75, w 0.9, δ 6, C = ∞, H 2, $u_0$ 14 | 9.270 | 6,912 |
| **`pool_conf` (adopted)** | **σ 15, τ 1.5, w 0.7, δ 6, C = ∞, H 2, $u_0$ 14** | **9.207** | **6,912** |

Both grids were extended once from v1's final grid: H (home edge) could be pushed below 2
(v1's `LIMITS` has no floor on it), and τ (weekly drift) could be pushed above 1.5. Both
adopted-pick values (H = 2, τ = 1.5) land inside the extended grid, not on an edge.
Grid: σ ∈ {11,13,15,17}, τ ∈ {0, 0.75, 1.5, 2.25}, w ∈ {0.5,0.7,0.9,1.0}, δ ∈ {3,6,9},
C ∈ {24, 38, ∞}, H ∈ {1.25, 2, 2.75, 3.5}, $u_0$ ∈ {8, 14, 20}.

**τ = 1.5 is larger than v1's picked τ = 0.75.** v1's own tuning surface showed τ = 0 within
0.001 CRPS of its pick — effectively flat. No equivalent per-axis surface was run for P1, so
whether within-season drift genuinely matters more on the fuller pool, or this is noise on a
different game set, is unconfirmed. It is not load-bearing for the adopt verdict: dropping τ
to its neighbouring grid values in the stress check below left the adopt verdict unchanged.

The FCS seed $m_0$ computed from every 2013 FBS-vs-FCS game in the raw files is −27.279,
matching v1's seed (computed from the lined-only 2013 games) to three decimals: 2013 had
full betting-line coverage of FBS-vs-FCS games, so the two computations draw from the same
111 games.

**Conference labels, checked before trusting `pool_conf`'s win.** Since the adopted variant
depends entirely on the conference key, two things were checked directly against the raw
files:

- **Era-correctness.** CFBD's `homeConference`/`awayConference` fields track realignment at
  the season it happened, not retroactively: Missouri and Texas A&M read SEC from 2013 (they
  joined in 2012), and the 2024 wave — Oklahoma and Texas to SEC, USC and UCLA to Big Ten,
  Colorado to Big 12 — first appears in `games_2024.json`, not earlier seasons. No leakage
  from a future label appearing in a past season.
- **No cross-subdivision collision.** `_Teams.conf_mean` keys purely by conference string, so
  a string shared by an FBS and an FCS conference in the same season would blend their means.
  Checked directly: zero (season, conference) pairs hold both subdivisions, in every season
  2013–2025, tuning and scored eras alike.

Both checks pass, so the conference-mean result stands without a rerun.

## Results

### Primary population (v1's 3,718 FBS-vs-FBS games, Bovada open present)

| Metric | Diff (P1 − v1) | 95% CI | MDE | Verdict | Per season 2021→2025 |
| --- | --- | --- | --- | --- | --- |
| CRPS | −0.082 | [−0.137, −0.031] | 0.077 | improves | −0.105, −0.109, −0.039, −0.098, −0.061 |
| MAE | −0.127 | [−0.210, −0.050] | 0.116 | improves | −0.092, −0.166, −0.064, −0.223, −0.092 |

Negative in every season, both metrics: the pool improves consistently, not on one good year.

### FBS-vs-FCS population (580 lined games)

| Metric | Diff (P1 − v1) | 95% CI | MDE | Verdict | Per season 2021→2025 |
| --- | --- | --- | --- | --- | --- |
| CRPS | −0.829 | [−1.244, −0.401] | 0.601 | improves | −0.760, −1.804, −0.648, −1.186, +0.142 |
| MAE | −1.269 | [−1.939, −0.588] | 0.956 | improves | −1.378, −2.722, −0.703, −2.039, +0.299 |

2025 is the one season where the pool is (very slightly) worse on these games. Season counts:
117, 116, 115, 106, 126 (2021→2025). The pooled interval is clear of 0.

### Gates re-read for the adopted P1 (same rules v1 used, for comparison — not adoption gates)

| Gate | v1 | P1 | Detail |
| --- | --- | --- | --- |
| G1 (vs Elo-MOV) | pass, CRPS −0.331 | **pass, CRPS −0.413** [−0.503, −0.326] | Also MAE guard: −0.549 [−0.699, −0.404], improves |
| G2 (encompassing β vs open) | **fail**, β 0.059 [−0.081, 0.198] | **pass, β 0.193** [0.052, 0.329] | Second look — see below |
| G3 (interval coverage) | pass, 65.5% / 93.5% | **fail**, 72.8% / 96.8% | Too wide, not too narrow |

**On G2:** a β whose interval clears 0 means the pool's disagreement with the Bovada open
predicts where the margin lands. v1 could not show this; P1 can, on the same 3,718 games,
now with a fuller FCS state feeding the ratings. But **this is the second time these seasons
have been scored** — first for v1, now for P1 — so this is not independent evidence in the
way an untouched season would be. The declared rule treats it as a second-look pass, not a
GO, and reserves a GO for a 2026 confirmation registered before that season is read.

**On G3:** pooled 68% coverage is 72.8%, above the declared [65%, 71%] band; 95% coverage is
96.75%, inside [93%, 97%]. Every RD quintile's 95% coverage sits inside [90%, 98%] (95.8% to
97.6%). The RD is wider than its own error calls for. Wide is not automatically safe: a
probability squeezed toward 0.5 by an inflated $S$ still misprices a game, and P1's
calibration slope was not re-read here — only interval coverage was.

### Stress (13 one-step variants on the adopted `pool_conf` pick)

The ADOPT verdict — not G1/G2/G3 — is what the spec declares stable-checked. It held in
every variant: σ ∈ {13, 17}, τ ∈ {0.75, 2.25}, w ∈ {0.5, 0.9}, δ ∈ {3, 9}, C = 38, H ∈ {1.25,
2.75}, $u_0$ ∈ {8, 20}.

## Trial count

- **Tuning:** 6,912 configurations for `pool_sub`, 6,912 for `pool_conf` — the declared grid
  (3,888) extended once on H and τ (both variants' boundary picks combined).
- **Stress:** 13 variants of the adopted pick.
- **Scoring:** 1 run.
- **Cumulative with v1:** v1's own tally was 4,162 tuning + 13 stress + 1 scoring = 4,176.
  Adding P1's 13,838 (which already includes its stress and scoring): **18,014
  tuning/stress/scoring trials** on the Glicko family to date.

## Dropped and counted (not silently skipped)

| Season | Non-D-I side (D-II/D-III/unlabelled) | No final score |
| --- | --- | --- |
| 2013–2019 | 48–90 a season | 0 |
| 2020 | 296 | 0 |
| 2021 | 932 | 0 |
| 2022–2025 | 2,164–2,204 a season | 0–10 a season |

The jump from 2021 to 2022 (932 → 2,164) reflects CFBD's Division II/III coverage expanding
in the raw feed from 2022 on — those games were never candidates for FBS/FCS ratings, but
seeing this many confirms the D-I filter is doing real work, not passing through everything.
The small "no final score" counts in 2023–2025 (10, 2, 2 games) are not examined further;
they predate 2026 and are not lined games waiting to be played.

## What this does not support

- **Any ATS or betting claim.** A second-look G2 pass is not a confirmation. No wager was
  graded.
- **That τ = 1.5 means within-season drift matters here.** No per-axis tuning surface was run
  for P1 (unlike v1's, which showed τ was flat). Unconfirmed; not load-bearing for the adopt
  verdict.
- **A holdout.** 2021–2025 has now been scored twice on this family (v1, then P1). 2026 is
  the first genuinely untouched test.
- **Any claim about D-II or D-III teams.** They were dropped from every game they appear in.
- **That P1's uncertainty is well calibrated.** G3 failed; the RD is a little wide.

## Next steps

1. **Register a 2026 confirmation spec before more of the season plays out**, following the
   pattern `prior_v3`'s sealed confirmation used in
   [`dynamic-ratings-2026-09-23.md`](dynamic-ratings-2026-09-23.md): freeze P1's pick now,
   read the encompassing slope exactly once, only after no 2026 regular-season game remains
   scheduled. If it confirms, **that** is when an ATS amendment becomes worth registering —
   not before.
2. **The preseason-prior rung** (the user's original second choice) now builds on P1, not v1,
   per the adopted spec's rule. The weeks 1–3 gap that motivated it was a v1 number; it should
   be re-measured on P1 before the prior rung is scoped.
3. **P1 takes over the weekly ratings table** (`scripts/glicko_ratings_table.py`), per the
   spec's declared rule.

# Building the five better-constructed EPA metrics

**Date:** 2026-09-18
**Status:** design spec. No numbers are reported here, so no script ships with it.
All four buildable constructions land in one script,
`scripts/build_ppa_opponent_adjusted_ratings.py`, behind a `--play-filter`
argument — see "The shared pipeline".
**Builds on:** [`ppa-opponent-adjusted-ratings-2026-09-16.md`](ppa-opponent-adjusted-ratings-2026-09-16.md)
(`scripts/build_ppa_opponent_adjusted_ratings.py`, `VERSION = "1.0"`)
**Bound by:** [`model-evaluation-standard.md`](model-evaluation-standard.md) integrity
gates, and the root `CLAUDE.md` no-lookahead rule.

## Question

For each of five common EPA-family metrics, the naive version has a known failure
mode and a "better construction". What does it actually take to build each better
construction against this warehouse, and which ones are not buildable at all?

## Headline

Four of the five are buildable today from `stg.plays`. One is not.

| # | Metric | Better construction | Buildable now? |
|---|---|---|---|
| 1 | EPA/play | Source-locked opponent-adjusted EPA residual | **Yes** — v1.0 already produces the residual; the delta is play-grain filtering and source-locking |
| 2 | Success rate | Joint model with EPA and explosive rate | **Yes** — recompute all three from `stg.plays` on one filter |
| 3 | Early-down EPA | Neutral-state, opponent-adjusted early-down EPA | **Yes** — but define neutral state from score/clock, not from `stg.win_probability` (see gates) |
| 4 | Dropback EPA | Separate pass, scramble, pressure-conditioned components | **Partial.** Pass/sack: yes. **Scramble: no.** **Pressure-conditioned: no at play grain.** |
| 5 | EPA allowed | Opponent- and field-position-adjusted defensive EPA | **Yes** — the work is the sign convention and a field-position covariate |

Row 4 is the one to plan around. The rest are the same pipeline with a different
`WHERE` clause.

## The shared pipeline

Constructions 1, 2, 3 and 5 are not four models. They are **one model with four
upstream play filters**:

```
stg.plays  --[play filter]-->  team-game aggregate  -->  crossed team/opponent
           (down, score state,     (mean ppa, n_plays,     random effects + HFA
            play type, sign)        success rate, expl)    -->  BLUP residual
                                                           -->  precision-weighted
                                                                shrinkage to prior
```

Stages 2 and 3 already exist in `scripts/build_ppa_opponent_adjusted_ratings.py`.
It currently reads `stg.ppa_games` (CFBD's own team-game aggregate). The build is:
add a `--play-filter` argument, swap the loader to aggregate `stg.plays` itself,
and leave the mixed-effects and shrinkage stages untouched.

**Do not fit a mixed model on 2.9M play rows.** Aggregating the filtered subset to
team-game first gives the same opponent adjustment at a fraction of the cost, and
the per-cell play count is what carries precision weighting into stage 2.

The "residual" in "opponent-adjusted EPA residual" is the team random effect (BLUP)
from stage 1 — EPA after opponent strength and home field are partialled out. That
is exactly what v1.0 outputs as `off_rating` / `def_rating`.

## Data and date range

All from local `cfb.duckdb` (`CFB_DATA_ROOT`, source of truth).

| Table | Grain | Rows | Coverage |
|---|---|---|---|
| `stg.plays` | play | ~2.9M | 2012–2026 (2026 partial: 58,904 plays, 335 games through the 2026-09-18 snapshot) |
| `stg.win_probability` | play | 1,554,334 | joins on `gameId`, `playId` |
| `stg.passing_plays` | pass play | 8,445 | **2026 only** — not historical |
| `stg.pff_passing_allowed_pressure` | player-week | 2,636 | no `playId` |
| `stg.pff_defense_pass_rush` | player-week | 266,523 | no `playId` |

`stg.plays` season volume steps up in 2022 (≈158k/season → ≈252k) as CFBD widened
coverage — a pre-2022 and a post-2022 rate are not the same denominator.

**`ppa` is NULL on ~25% of `stg.plays` rows.** This is not missing data: kickoffs
(138,159), punts (136,684), penalties (131,555), timeouts (99,271) and period
markers have no offensive expected-points delta. Every construction below filters
`ppa IS NOT NULL`. Do not treat the null rate as a coverage problem.

Play-type counts that matter downstream: `Rush` 985,248 · `Pass Reception` 439,118 ·
`Pass Incompletion` 343,459 · `Sack` 53,093.

### Three `stg.plays` traps, all verified against the 2026-09-18 snapshot

**Play order is `(driveNumber, playNumber)`, not `playNumber`.** `playNumber`
restarts at 1 on every drive. Ordering or windowing on `playNumber` alone silently
interleaves drives.

**`offenseScore` / `defenseScore` are POST-play, and include the PAT.** On a
`Field Goal Good` row the score already shows the 3; on a `Rushing Touchdown` row it
already shows 7. Filtering game state on these columns conditions a play on its own
outcome — which biases exactly the explosive plays row 2 is built to measure. They
are also possession-relative, so they swap meaning at every change of possession.

Reconstruct pre-play state possession-independently, then use it everywhere:

```sql
-- pre-play home/away score, safe across possession changes
WITH s AS (
  SELECT *,
         CASE WHEN offense = home THEN offenseScore ELSE defenseScore END::INTEGER AS home_post,
         CASE WHEN offense = home THEN defenseScore ELSE offenseScore END::INTEGER AS away_post
  FROM stg.plays
), state AS (
  SELECT *,
         COALESCE(LAG(home_post) OVER w, 0) AS home_pre,
         COALESCE(LAG(away_post) OVER w, 0) AS away_pre
  FROM s
  WINDOW w AS (PARTITION BY gameId ORDER BY driveNumber, playNumber)
)
SELECT *,
       CASE WHEN offense = home THEN home_pre - away_pre
            ELSE away_pre - home_pre END AS margin   -- offense-relative, pre-play
FROM state
```

The `::INTEGER` casts are load-bearing: the score columns are `UINT64`, so a
trailing team's `home_pre - away_pre` raises
`Out of Range Error: Overflow in subtraction of UINT64`.

**Postseason is included unless excluded.** `stg.plays.season_type` is
`regular` (2,553,040) or `postseason` (106,543). v1.0 fits on regular season only
(`seasonType = 'regular'` on `stg.ppa_games`); the blocks below do not filter it, so
add `AND season_type = 'regular'` to match v1.0, or keep postseason deliberately.
`gameId` is in every grouping key, so the two never collide — this is a modelling
choice, not a correctness bug.

Every SQL block below was executed against season 2024 on the 2026-09-18 snapshot
and returns 3,204 team-game rows.

---

## 1. EPA/play → source-locked opponent-adjusted EPA residual

### What breaks in the naive version
Raw mean `ppa` is a schedule artifact as much as a team-quality measure, and the
number is only comparable to another number computed from the same EPA model. CFBD
`ppa`, PFF EPA, and a self-fit EPA are three different models of the same concept;
differences between vendors are larger than most differences between teams.

### The construction
Team BLUP from a crossed team/opponent random-effects fit on team-game mean `ppa`,
with a home-field fixed effect, shrunk toward a prior-seasons pooled estimate by
inverse-variance weighting. Pinned to one EPA source and one pull.

**Source-locking is a mechanism, not a disclaimer.** `stg` tables carry
`_source_file`; PFF tables carry `pulled_at`. The rule: one figure never mixes EPA
models, and the output row records which file produced it. Anything reported as an
"EPA rating" without that pin is not comparable to the next one.

### SQL / model form
```sql
-- stage 0: team-game aggregate, all offensive plays
SELECT season, week, gameId, offense AS team, defense AS opponent,
       AVG(ppa) AS epa_play, COUNT(*) AS n_plays,
       ANY_VALUE(_source_file) AS src
FROM stg.plays
WHERE ppa IS NOT NULL
GROUP BY 1,2,3,4,5
```
Then `fit_crossed_effects()` + the shrinkage stage from the v1.0 script, unchanged.

### Tables used
`stg.plays` × `stg.games` (for `homeTeam`, `neutralSite`).

### What it does not support
It does not make the rating comparable to a PFF or ESPN EPA rating. It does not
separate line play, scheme, or personnel. And a BLUP from a 2-game sample is mostly
prior — report the SE alongside it, not the point estimate alone.

---

## 2. Success rate → joint model with EPA and explosive rate

### What breaks in the naive version
Success rate is a ceiling-censored statistic: a 4-yard gain on 1st-and-10 and a
60-yard touchdown are both one success. A team can post a top-10 success rate and a
bottom-40 EPA by never hitting anything. Reading it as a summary of offensive
quality double-counts consistency and ignores the tail entirely.

### The construction
Compute all three on the **same filtered play set** and carry them as a vector, not
a ranking: mean EPA, success rate, explosive rate. They decompose one distribution —
EPA is roughly the mean, success rate the mass above a low threshold, explosive rate
the mass in the tail.

**Recompute, don't consume.** `stg.advanced_box_score__teams_success_rates` and
`__teams_explosiveness` exist, vendor-computed with vendor thresholds. Recomputing
from `stg.plays` with the threshold written out in the query is the source-locked
choice; using the vendor column is fine, but then it is a vendor metric and rows 1
and 2 no longer share a definition. Pick one and say which.

Standard down-distance threshold: **50% of distance on 1st down, 70% on 2nd, 100%
on 3rd and 4th.**

### SQL / model form
```sql
SELECT season, week, gameId, offense AS team, defense AS opponent,
       AVG(ppa) AS epa_play,
       AVG(CASE WHEN (down = 1 AND yardsGained >= 0.5 * distance)
                  OR (down = 2 AND yardsGained >= 0.7 * distance)
                  OR (down >= 3 AND yardsGained >= distance)
                THEN 1.0 ELSE 0.0 END) AS success_rate,
       AVG(CASE WHEN ppa >= 1.0 THEN 1.0 ELSE 0.0 END) AS explosive_rate,
       COUNT(*) AS n_plays
FROM stg.plays
WHERE ppa IS NOT NULL AND down BETWEEN 1 AND 4
GROUP BY 1,2,3,4,5
```
`ppa >= 1.0` is an EPA-space explosive definition, which keeps all three measures on
one scale. A yardage-space definition (12+ rush / 16+ pass) is defensible but is a
different statistic — do not switch between them mid-analysis.

### Tables used
`stg.plays` only.

### What it does not support
Three correlated columns are not three independent signals. Before using all three
as model features, check the correlation — in most seasons success rate and EPA
share most of their variance, and the incremental information sits in the explosive
column. Success rate also says nothing about *why* drives stall; it is not a
substitute for a drive-level model.

---

## 3. Early-down EPA → neutral-state, opponent-adjusted early-down EPA

### What breaks in the naive version
Restricting to 1st and 2nd down removes third-down conversion noise, which is the
point. It does not remove score state. A team leading by 28 in the 4th quarter runs
early-down plays that are deliberately low-EPA; a team trailing by 28 runs
early-down plays against a defense that has stopped defending the sticks. Both
contaminate the mean, in opposite directions.

### The construction
Filter to 1st and 2nd down **and** a neutral game state, then run the shared
pipeline. Define neutral state from **pre-play** score margin and quarter, both
derivable from `stg.plays` — see the post-play trap above; using the raw score
columns here conditions each play on its own result:

- through the 3rd quarter: `|margin| <= 21`
- in the 4th quarter: `|margin| <= 16`

These are the conventional garbage-time bounds. They are a declared modelling
choice, not a tuned parameter — **do not select them on evaluation data**, which the
evaluation standard treats as an invalidating gate.

### SQL / model form
```sql
WITH s AS (
  SELECT *,
         CASE WHEN offense = home THEN offenseScore ELSE defenseScore END::INTEGER AS home_post,
         CASE WHEN offense = home THEN defenseScore ELSE offenseScore END::INTEGER AS away_post
  FROM stg.plays
), state AS (
  SELECT *,
         COALESCE(LAG(home_post) OVER w, 0) AS home_pre,
         COALESCE(LAG(away_post) OVER w, 0) AS away_pre
  FROM s
  WINDOW w AS (PARTITION BY gameId ORDER BY driveNumber, playNumber)
)
SELECT season, week, gameId, offense AS team, defense AS opponent,
       AVG(ppa) AS early_down_epa, COUNT(*) AS n_plays
FROM state
WHERE ppa IS NOT NULL
  AND down IN (1, 2)
  AND (   (period <= 3 AND ABS(home_pre - away_pre) <= 21)
       OR (period >= 4 AND ABS(home_pre - away_pre) <= 16))
GROUP BY 1,2,3,4,5
```
The margin is symmetric, so the home/away orientation does not matter for the
filter itself — but keep the offense-relative form from the traps section if the
filter is ever made asymmetric (leading vs. trailing). Then the shared stage 1/2.

### Tables used
`stg.plays` only. **Deliberately not `stg.win_probability`** — see gates below.

### What it does not support
A neutral-state filter cuts sample, hardest for exactly the blowout teams you most
want to rate. Report `n_plays` per team-game; a team whose games are never close has
a thin and differently-selected sample. The filter also does not turn early-down EPA
into a measure of "intent" — pace, personnel and opponent script still load onto it.

---

## 4. Dropback EPA → separate pass, scramble, pressure-conditioned components

**This is the row that does not fully build. Read the constraints before planning
work against it.**

### What breaks in the naive version
"Dropback EPA" is a definitional convention, not a measurement. Whether sacks count,
whether scrambles are passes or runs, and whether spikes and throwaways are excluded
all move the number — and every vendor draws those lines differently. Two "dropback
EPA" figures from two sources are not the same statistic.

### The construction, and what is actually available

**Pass vs. sack: buildable.** `playType` separates them cleanly. `Sack` = 53,093
rows; pass outcomes are `Pass Reception`, `Pass Incompletion`, `Pass Completion`,
`Passing Touchdown`, `Interception` / `Pass Interception` / `Pass Interception
Return`.

**Scramble: not buildable.** CFBD does not label scrambles. They sit inside `Rush`
(985,248 rows), and `playText` carries no marker — of 409,399 `Rush` plays since
2022, 237 contain "scrambles" and **zero** contain "QB". Play text reads
`Riley Leonard run for 2 yds to the ND 24`, identical in form to a running back's
carry. There is no rusher ID on `stg.plays`.

The only proxy is name-matching the rusher in `playText` against the team's primary
passer, which needs a passer roster per team-season and still cannot separate a
designed QB run from a scramble. `stg.passing_plays` — which does carry `passer`,
`airYards`, `passDepth`, `isSpike`, `isThrowaway` — **covers 2026 only (8,445
rows)**, so it is not a historical solution. Treat scramble separation as
unavailable and say so in any figure that claims "dropback".

**Pressure-conditioned: not buildable at play grain.**
`stg.pff_passing_allowed_pressure` (2,636 rows) and `stg.pff_defense_pass_rush`
(266,523 rows) are **player-week aggregates with no `playId`**. There is no join
from a PFF pressure event to a CFBD play. The most that can be built is a
**team-week pressure rate as a covariate** on a team-game EPA aggregate — which
answers "do high-pressure-rate defenses suppress passing EPA" and does not answer
"what is this offense's EPA under pressure". Those are different questions; do not
let one be reported as the other.

### SQL / model form (the part that does build)
Define the dropback set **once**, in a CTE, and derive both components from it. A
`LIKE 'Pass%'` predicate in the `WHERE` next to an explicit list in the `CASE` is
two different definitions of "dropback" in one query, and it drops
`Interception Return Touchdown` while admitting rows the `CASE` ignores.

```sql
WITH dropback AS (
  SELECT * FROM stg.plays
  WHERE ppa IS NOT NULL
    AND playType IN ('Pass Reception','Pass Incompletion','Pass Completion',
                     'Passing Touchdown','Interception','Pass Interception',
                     'Pass Interception Return','Interception Return Touchdown',
                     'Sack')
)
SELECT season, week, gameId, offense AS team, defense AS opponent,
       AVG(CASE WHEN playType <> 'Sack' THEN ppa END) AS pass_epa,
       AVG(CASE WHEN playType =  'Sack' THEN ppa END) AS sack_epa,
       COUNT(*) FILTER (WHERE playType = 'Sack')      AS sacks,
       COUNT(*)                                       AS n_dropbacks
FROM dropback
GROUP BY 1,2,3,4,5
```
That set is 968,576 rows across 2012–2026 (7,373 of them with NULL `ppa`, excluded
by the CTE). `n_dropbacks` now counts the same rows the components are computed
from, which is what its name claims.

Report `pass_epa` and `sack_epa` as two columns. A combined dropback EPA that folds
sacks in is fine as a derived figure, but the components should survive to the
output so the convention stays visible.

### Tables used
`stg.plays`. `stg.passing_plays` for 2026-only pass-depth work. PFF tables only as
team-week covariates.

### What it does not support
It is not a dropback *rate* — `stg.plays` gives no snap count, so a pass/run split
by snaps is unavailable. It does not isolate the quarterback from pass protection or
receiving. And without scramble separation, a QB who scrambles often has EPA sitting
in the rushing bucket; any QB comparison across mobility profiles is biased by
construction.

---

## 5. EPA allowed → opponent- and field-position-adjusted defensive EPA

### What breaks in the naive version
Negated offensive EPA is a *result*, jointly produced by the defense, the offense it
faced, and the field position it inherited. A defense that starts every series at its
own 40 because its offense punts well looks better than one starting at its own 12.
Calling that result a defensive metric attributes all three causes to one unit.

### The construction
The same crossed random-effects fit as row 1, run on the defensive side, with **two
additions**: correct sign handling and a field-position covariate.

**Sign convention — the most common error in this row.** `stg.plays.ppa` is
**offense-signed**. For a defense, a positive `ppa` on a play it defended is a bad
outcome. Negate when aggregating by `defense`, so higher is better on both sides of
the fit. v1.0 documents this same trap at game grain (`defense_overall` carries
CFBD's raw sign and the script fits on its negation); it recurs identically at play
grain and is easy to reintroduce.

**Field position.** `yardsToGoal` is on every play. Carry mean starting field
position per team-game as a fixed-effect covariate in stage 1, so inherited position
is partialled out alongside opponent strength.

### SQL / model form
```sql
SELECT p.season, p.week, p.gameId,
       p.defense AS team, p.offense AS opponent,
       AVG(-p.ppa)        AS def_epa_allowed,   -- higher = better defense
       AVG(p.yardsToGoal) AS mean_start_ytg,
       COUNT(*)           AS n_plays
FROM stg.plays p
WHERE p.ppa IS NOT NULL
GROUP BY 1,2,3,4,5
```
Stage 1 gains `mean_start_ytg` as a fixed effect alongside the home-field term; team
and opponent stay crossed random effects.

For true drive-start field position rather than a per-play mean, aggregate
`stg.drives` instead — the per-play mean above is a proxy and mixes in the offense's
own success.

### Tables used
`stg.plays` × `stg.games`; optionally `stg.drives` for drive-start position.

### What it does not support
It is still a unit result, not a player metric. After adjustment it does not separate
front seven from secondary, does not credit turnovers as skill (turnover EPA is
high-variance and poorly persistent), and does not account for how often the defense
was on the field. Opponent adjustment shrinks the schedule effect; it does not
eliminate it in a 2-game sample.

---

## Integrity gates

These bind every construction above, under
[`model-evaluation-standard.md`](model-evaluation-standard.md) and the root
`CLAUDE.md` no-lookahead rule.

1. **Fit through week W−1.** An opponent adjustment fit on the full season includes
   the game being predicted. Any of these ratings used as a pre-game feature must be
   refit with data strictly before kickoff. The v1.0 script takes `--week`; a
   play-level loader must honour it the same way. Restate this per construction —
   do not assume it carries over because the stage-1 code is shared.
2. **`stg.win_probability` is spread-informed.** It carries a `spread` column, so
   filtering "neutral state" on WP conditions a feature on market-derived
   information and then grades it against the market. Circular. Use score margin and
   clock (row 3) for any feature that will be evaluated against a line; reserve WP
   filtering for descriptive work.
3. **Never mix EPA sources in one figure.** CFBD `ppa`, PFF EPA, and a self-fit EPA
   are different models. Record `_source_file` (CFBD `stg` tables) or `pulled_at`
   (PFF tables) on any output row.
4. **Never filter on post-play state.** `stg.plays` score columns are post-play
   (see the traps section). Any game-state filter must run on the `LAG`-reconstructed
   pre-play score, or the play is selected by its own outcome — leakage inside a
   single row, which the standard treats the same as leakage across rows.
5. **Thresholds are declared, not tuned.** The 50/70/100 success threshold, the
   `ppa >= 1.0` explosive cut, and the 21/16-point garbage-time bounds are
   conventions written down in advance. Selecting any of them on evaluation data is
   an invalidating gate, not a tuning step.

## What this document does not support

It reports no numbers and validates no metric. Nothing here shows that any of these
constructions predicts anything — that needs the walk-forward, interval, and
market-relative evidence the evaluation standard specifies, in a separate dated doc.
Row 4's constraints are statements about this warehouse as of the 2026-09-18
snapshot, not about the CFBD API in general; a future feed carrying a scramble flag
or play-grain pressure data would reopen it.

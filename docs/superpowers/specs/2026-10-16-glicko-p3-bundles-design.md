# Glicko P3: three adjustment bundles, declared before any holdout read — design

**Status:** declared 2026-10-16, before any bundle is built or scored. Nothing in 2026 after
2026-10-16 or in 2027 has been read by any Glicko work.
**Builds on:** [`../../glicko-p2-2026-10-15.md`](../../glicko-p2-2026-10-15.md) (P2 not adopted,
σ_pred 13.5 adopted) and [`../../glicko-adjustments-review-2026-10-16.md`](../../glicko-adjustments-review-2026-10-16.md)
(which adjustments strong systems make that P1 lacks).
**Leaves alone:** P1's sealed 2026 confirmation
([`2026-09-24-glicko-p1-2026-confirmation-design.md`](2026-09-24-glicko-p1-2026-confirmation-design.md)).
`FROZEN_P1` and its forecast fingerprint must still match after every change here; each bundle
is a new class or option whose defaults reproduce P1 exactly.

## Question

Does each of three bundles improve P1's forecasts on games no Glicko work has seen?

## Why a fresh holdout

2021–2025 has been scored three times on this family (v1, P1, P2) and 18,622 trials have been
run. It can still be reported, but it cannot decide anything. Every adopt decision below reads
only the holdout.

## Bundles

Each bundle is built and scored on its own against the base, never stacked during selection.

| Bundle | What changes | Tunable, grid (2014–2019 only) |
| --- | --- | --- |
| **A. Schedule strength** | Replace the per-team update with a within-season filter that carries the covariance between teams, so a result moves every team linked to the two that played, by how strongly they're linked. The offseason step resets cross-season covariance to zero. | σ ∈ {13, 15, 17}; everything else P1's |
| **B. Preseason start** | (1) Offseason target for a conference switcher is its **new** conference's mean, which is known from the schedule before kickoff. (2) Carryover depends on transfer-aware returning production: returning plus incoming transfers' prior-season production, with transfers from below FBS at half credit, z-scored within each season. (3) The target blends in a 3-season weighted history of final ratings. | c ∈ {0, 0.05, 0.1}; history weight h ∈ {0, 0.15, 0.3}; w ∈ {0.6, 0.7, 0.8} |
| **C. Game context** | (1) Home edge varies by season as a linear trend in season, with 2020 its own value. (2) An overtime game's margin is read as 0, the score at the end of regulation. (3) Observation variance is multiplied by k for postseason games and for FBS-vs-FCS games. (4) A neutral-site game within 150 miles of one campus gives that team half the home edge. (5) A signed time-zone difference term, in points per zone. | H₂₀₁₃ ∈ {2, 2.75, 3.5}, slope ∈ {0, −0.05, −0.1}/season, H₂₀₂₀ ∈ {0, 1, 2}; k ∈ {1, 1.5, 2}; tz ∈ {0, 0.25, 0.5} |

B(2) needs player-level prior-season production joined to `raw/transfer_portal_*.json`. If
that join cannot be built from data on disk, B ships without (2), and the write-up says so.
Bundle C's travel and neutral-site distances use CFBD venue coordinates. Pick each bundle's
setting by lowest mean CRPS on FBS-vs-FBS regular-season games, 2014–2019, with forecast SD
from σ_pred, re-tuned per bundle on 11.0–16.0 in steps of 0.5.

## Holdout and looks

- **Holdout:** every completed FBS-vs-FBS game kicking off after 2026-10-16T23:59Z through the
  end of the 2026 postseason, plus the whole 2027 season.
- **Comparison:** each bundle minus P1 with σ_pred 13.5, paired CRPS and MAE on the same games.
  Season-week block bootstrap, 10,000 draws, seed 20261016.
- **Interim look**, after the 2026 postseason: printed and recorded, labelled interim. No
  verdict is quoted and nothing is adopted from it.
- **Final look**, after the 2027 postseason, read exactly once per bundle.
- **Adopt** a bundle if its paired CRPS interval is below 0 and its MAE interval is not above
  0. Also report, without gating: weeks 1–3 vs later, coverage, log loss, and the encompassing
  slope against the Bovada open.
- **Combining:** adopted bundles are stacked and the stack is reported descriptively. A stack
  that is worse than its best single bundle is not adopted.

## Diagnostics that may run first

[`scripts/glicko_diagnostics.py`](../../../scripts/glicko_diagnostics.py) reads only seasons
through 2025. Its results may **drop** a component from a bundle before the bundle is built,
and the drop is recorded here. They may not add a component or widen a grid.

**Run 2026-10-16 on 2014–2025 (2020 skipped): nothing dropped.** Overtime games are
over-covered (85.5% at 68%) and postseason under-covered (65.8%), which supports C(2) and C(3).
Home teams beat the forecast by about +0.5 points a season on average (9 of 11 seasons
positive), which supports C(1). Conference switchers show no clear miss (+0.19
[−0.47, 0.87], 142 team-seasons). Not in any bundle, so not testable here: FBS-vs-FCS
forecasts are too extreme (residual slope −0.149 [−0.204, −0.096]). That needs its own plan.

## Trial accounting

Grids above: A 3, B 27, C 3 × 3 × 3 × 3 × 3 = 243, plus 11 σ_pred values per bundle. Each
bundle gets one interim and one final look. All of it adds to the family's running count
(18,622 before this spec).

## What this does not support

- No betting claim. The encompassing slope is reported but not gated.
- Nothing about P1's sealed confirmation, which is read separately and unchanged.

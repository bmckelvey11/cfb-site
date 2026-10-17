# Rankings docs index

Team-rating models and their records: the Glicko margin rating (the published team rating),
its theory, plans, method, versions, and every dated result. The code stays in `scripts/`
for now (see [`../CLAUDE.md`](../CLAUDE.md)). Root rules, including the docs lifecycle, are in
[`../../CLAUDE.md`](../../CLAUDE.md).

## Theory

What the rating models are and why: the state-space view, observation models, priors and the
market-residual framing. Theory says what is true or believed, not what to build next.

| Doc | Question it answers |
| --- | --- |
| [rating-model-theory.md](rating-model-theory.md) | What a football-native rating system should model (team strength vs market overlay vs decisions; offense, defense and pace states; observation noise; priors; regimes) and why literal chess Glicko is not the endpoint (from the 2026-10-17 external review) |

The original design document the review responds to, `glicko-college-football.md`, is not in
the repo yet. It is untracked in the working copy on Blake's Mac.

## Plans

What to build and test next, and the preregistered designs that bind each test.

| Doc | Question it answers |
| --- | --- |
| [rating-model-roadmap.md](rating-model-roadmap.md) | In what order to build the strength model, market overlay, calibration and decision layers, with the promotion gates each stage must clear (from the 2026-10-17 external review) |
| [specs/2026-09-24-glicko-ratings-design.md](specs/2026-09-24-glicko-ratings-design.md) | Design of v1: Glicko-style margin ratings vs Elo and the vendor open, declared before any code |
| [specs/2026-09-24-glicko-pool-design.md](specs/2026-09-24-glicko-pool-design.md) | Design of P1: rating every D-I team from every D-I game, with conference-mean offseason targets |
| [specs/2026-09-24-glicko-p1-2026-confirmation-design.md](specs/2026-09-24-glicko-p1-2026-confirmation-design.md) | P1's sealed 2026 confirmation: its encompassing slope against the open, read once after the season |
| [specs/2026-10-16-glicko-p3-bundles-design.md](specs/2026-10-16-glicko-p3-bundles-design.md) | Bundles P3-A (schedule strength), P3-B (preseason start), P3-C (game context): grids, holdout and adopt rule, with the build record |
| [specs/2026-10-17-glicko-p3d-fcs-design.md](specs/2026-10-17-glicko-p3d-fcs-design.md) | Bundle P3-D: shrink FBS-vs-FCS forecasts, declared before build, with the build record |
| [specs/2026-10-17-market-implied-score-design.md](specs/2026-10-17-market-implied-score-design.md) | Market-implied score baseline $(T \pm M)/2$: comparators, scoring and limits, declared before build |

## Method and versions

Living references: they must match the code.

| Doc | Question it answers |
| --- | --- |
| [glicko-method.md](glicko-method.md) | Exactly how the live Glicko rating works (living reference): game set, clock, entry, drift, forecast and Kalman update, offseason, table, scoring, sealed holdouts, candidates under test, and what it does not adjust for |
| [glicko-versions.md](glicko-versions.md) | Which Glicko versions exist, which one is published (P1.1), and what each changed: v1 retired, P1 adopted, P2 rejected, P3-A to P3-D candidates awaiting their holdout (living changelog of `scripts/glicko_versions.py`) |

## Records

Dated results. Never rewritten after the fact; a new answer is a new dated doc.

| Doc | Question it answers |
| --- | --- |
| [glicko-ratings-2026-09-24.md](glicko-ratings-2026-09-24.md) | Does a Glicko-style margin rating (mean + RD, Kalman update) hold information the Bovada open lacks? No-go: beats Elo (−0.33 CRPS) with calibrated intervals, but encompassing β 0.06 [−0.08, 0.20] and +0.46 MAE behind the open |
| [glicko-pool-2026-09-24.md](glicko-pool-2026-09-24.md) | Does rating every D-I team from every D-I game (conference-mean targets) beat the lined-only v1 Glicko rating? Adopted: −0.08 CRPS on FBS-vs-FBS, −0.83 on FBS-vs-FCS; encompassing β 0.19 [0.05, 0.33] now clears 0, but it's a second look at 2021–25, not a confirmed GO |
| [glicko-p2-2026-10-15.md](glicko-p2-2026-10-15.md) | Can P1 Glicko be improved without touching its sealed 2026 confirmation? A preseason prior (returning production + recruiting) is not adopted: −0.06 CRPS in 2014–19 tuning, +0.05 on 2021–25 and +0.05 on 2026 wk 1–7. A separate forecast σ of 13.5 (gain keeps 15) fixes P1's too-wide intervals: −0.022 CRPS, 68% cover 72.3% → 68.9%, ranks unchanged |
| [glicko-adjustments-review-2026-10-16.md](glicko-adjustments-review-2026-10-16.md) | Does P1 Glicko make the adjustments strong CFB rating systems make? Mostly: opponent adjustment, raw margin and ~0.70 carryover match. Gaps ranked: schedule strength not credited back, roster-blind preseason pull, conference switchers regress to the old conference, flat 2.0 home edge too low before ~2020 (literature review, untested) |

## Moved here

These docs moved on 2026-10-17 from `docs/` and `docs/superpowers/specs/`. Frozen and declared
files (`scripts/*_frozen.json`, `scripts/*_declared.json`) still record the old paths; those
strings are history and are not rewritten.

# Plan: Tuning lab Release D — probabilistic decisions
_By Claude + mckel, 2026-09-23. Executed inline, serially._

Design (gate, candidates, engine, deferral of priced evaluation):
[`../specs/2026-09-23-tuning-lab-release-d-design.md`](../specs/2026-09-23-tuning-lab-release-d-design.md).
This file is the build order; where the two differ, fix both.

## Status

| Task | Status |
| --- | --- |
| 0. Pin Release C's run id; declare the gate (spec) | Done 2026-09-23: `test_committed_spec_keeps_its_published_run_id` |
| 1. D0 contract (`dist_spec.py`) | Done 2026-09-23: 19 tests |
| 2. D1 distributions (+ frame targets in `features.py`) | Done 2026-09-23: 9 tests; real frame: target = home_reg + away_reg + ot_points on all 7,601 games, 340 with overtime, max total 146 |
| 3. D2 betting engine (`market.py`) | Done 2026-09-23: 20 hand-computed tests. Read-only pass over the real AN tick CSV (counts only): 94,130 full-game total quotes over 333 events at 5 books, 2026-04-02 to 2026-09-23; dropped 50,715 consensus/Open rows and 8,778 live rows. The first pass exposed `astype(bool)` reading blank flags as True; flags are now parsed explicitly |
| 4. D3 selective prediction (`selective.py`) | Done 2026-09-23: 3 tests; meta-model is a fixed-alpha Ridge (not a second search) |
| 5. D4 join, real run twice, AN read-only audit, docs | pending |

## Global constraints

- Everything from the Release C plan: `.venv`, stage `models/tuning/...` by path, no
  betting terms in cards, one commit per task, pushed.
- Never open `data/cfb.duckdb` (another session is rebuilding it). Real inputs are the raw
  JSON, the Release B snapshot CSV, C's published run directory, and, read-only, the AN
  tick CSV.
- The gate, window, candidates, and selection rule in the spec are frozen as of the spec
  commit. Outer 2021–2025 is scored once.
- `RunSpec` and `total_ratings_v1.json` do not change; the pin test guards them.

## Task outlines

1. **D0.** Frozen pydantic types with their own canonical hash:
   - `DistributionSpec`, `CalibrationGate`, `DistRunSpec`;
   - `DecisionPolicySpec`, `ExecutionSpec`;
   - `dist_run_id()`.

   Tests: hash stability, unknown fields rejected, gate defaults equal the spec.
2. **D1.**
   - `features.py` adds the `home_reg`, `away_reg`, and `ot_points` columns.
   - `distributions.py` has:
     - `season_forecasts`
     - `residual_pools`
     - `normal_pmf`, `empirical_pmf`, `joint_pmf`
     - `score_pmf`, for CRPS, mid-PIT, coverage, and pinball

   Tests: hand-checked CRPS and PIT on tiny tables, rows sum to 1, the joint total equals
   home + away + overtime, and the window uses only earlier seasons.
3. **D2.**
   - `Quote`, conversions, `settle`, `outcome_probs`, `expected_value`, `devig`;
   - `select_quote`, `decide`, `backtest`, `sensitivity`;
   - `quotes_from_an_ticks`.

   Tests: hand-computed pushes, half points, no-action, EV with pushes, de-vig, quote age
   and staleness, and refusal of an unpriced number.
4. **D3.** `meta_scores` (prior seasons only), `risk_coverage`, `aurc`. Tests: trained
   only on earlier seasons; an oracle score beats random ordering.
5. **D4.**
   - `dist_run.py`, the `dist` CLI subcommand, `specs/dist_total_v1.json`, and a
     distribution card.
   - Synthetic two-root byte-identity test.
   - Run on real data twice.
   - Audit the AN ticks read-only: counts and ages only.
   - Docs: plan-of-record status, and the guide's stale mid-2020 odds claim.

---
name: project-auto-discover-systems
description: Auto-discover-systems feature (MVP-001..006) design decisions made during MVP-002 that MVP-003+ must build on
metadata:
  type: project
---

Building an auto-discovery feature for cfb_system_maker that beam-searches a space of
`SystemFilter`/`FeatureFilter` predicates for profitable betting systems. Tickets live in
`.solopreneur/backlog/2026-07-22-auto-discover-systems/` (MVP-001 through MVP-006, plus
P1/P2). MVP-002 (candidate generation, `cfb_system_maker/search.py`) is built and merged
to `ticket/MVP-002`; MVP-003 (beam search evaluation/pruning/ranking) is next and
`depends_on: [MVP-002]`.

**Why this matters**: MVP-003's beam loop calls `search.expand_candidates` per surviving
candidate at each step and uses `search.candidate_identity` as its final tie-break sort
key — these two function signatures are now a contract MVP-003 must match, not
redesign.

**How to apply**: Before starting MVP-003, re-read `cfb_system_maker/search.py`'s module
docstring and these decisions rather than re-deriving them:
- Candidate "dimensions" (favorite_underdog, home_away, spread_range, total_range,
  `feature:<key>`) are a deliberately different counting scheme from
  `backtest.count_overfit_filters` (which counts values, not dimensions) — do not
  conflate the two or reuse one for the other.
- `total_side` (over/under) and `side` (home/away) are NOT independently expandable
  dimensions — `side` only changes as part of the `home_away` dimension (bool flag +
  side must be set together, verified empirically against `matches_system` — setting
  `home=True` with `side="away"` matches zero games). `total_side` is fixed by the seed
  candidate, same pattern.
- `seasons`/`weeks`/`teams`/`conferences`/`providers` are treated as external search
  *scope*, not generated candidate dimensions — they pass through from the seed
  unchanged. High-cardinality; MVP-003 already treats season range as scope config.
- Team-scoped registry features are generated from `bet_side` perspective only (MVP
  scope cut, backlog.md cross-cutting risk #5) — but *value derivation* pools both
  home_/away_ columns (via perspective="either") since the eventual candidate's side
  isn't known at generation time and some features (e.g. pregame win prob) aren't
  home/away symmetric.
- Spread/total range thresholds are derived from the raw home spread
  (`GameRecord.spread`), while `matches_system` applies min/max bounds to the
  side-adjusted spread (negated for away bets) — a known, documented MVP-quality gap,
  not a bug; MVP-003's empirical evaluation will simply score a poorly-placed threshold
  lower.
- `candidate_identity`'s optional numeric fields (`min_spread`/`max_spread`/
  `min_total`/`max_total`) are wrapped as `(is_not_none, value_or_0.0)` — plain
  `None`/`float` tuple comparison raises `TypeError` when used as a sort key, which
  broke the very first `expand_candidates` smoke test.

# Glicko P1's encompassing slope, sealed for a 2026 confirmation — design

**Status:** declared and frozen 2026-09-24, before any 2026 confirmation is read. The freeze
is committed in this same session; the confirmation itself waits for the season.
**Builds on:** [`2026-09-24-glicko-pool-design.md`](2026-09-24-glicko-pool-design.md) (rung P1,
adopted) and its result [`../../glicko-pool-2026-09-24.md`](../../glicko-pool-2026-09-24.md):
G2 (encompassing β vs the Bovada open) passed at β = 0.193 [0.052, 0.329] on 2021–2025 — the
**second** time those seasons were scored on this family, so the declared rule there treats it
as a second-look pass, not a GO. This spec is the "declared 2026 confirmation" that rule
requires before a GO is possible.
**Follows the pattern of:**
[`2026-09-23-prior-scale-2026-confirmation-design.md`](2026-09-23-prior-scale-2026-confirmation-design.md)
(`prior_v3`) — a frozen candidate, one confirmatory look after the season is final, interim
runs descriptive only. `season_look` and `write_freeze` are imported from
`scripts/weekly_prior_scale.py` unchanged.

## Question

Does P1's disagreement with the Bovada open — frozen, untouched since 2026-09-24 — predict
where the 2026 margin lands? This is the one test 2021–2025 cannot answer cleanly, because it
has now been read twice on this family.

## What is frozen

Nothing here is tunable. The candidate is exactly P1's adopted, already-scored configuration:

- **Model:** `GlickoMargin(**FROZEN_P1, m0=fcs_seed_pool(...))`, variant `pool_conf`
  (`scripts/glicko_ratings.py`, `scripts/glicko_pool_eval.py`).
- **Game set:** `glicko_pool_eval.load_pool_games` — every completed D-I game from the raw
  CFBD files, state run continuously from 2013.
- **Market:** Bovada `spreadOpen`, the same fixed-book rule as every other rung.

`scripts/glicko_p1_frozen.json` records these exact values and their source commit
(`c28745e8`, `0e2e0373`) so the confirmation script cannot silently drift from the scored
result. Written once, committed before any confirmation run, and never rewritten — mirroring
`weekly_prior_v3.json`.

## Confirmation

- **Data:** 2026 regular season, FBS vs FBS, completed games, Bovada open present. Same
  primary-population rule as P1's own scoring (`docs/glicko-pool-2026-09-24.md`).
- **Declared comparison:** the encompassing slope β of P1's forecast against the open
  (`glicko_ratings_eval.encompassing`, reused unchanged), with the same season-week cluster
  bootstrap. 2026 is one season, so this is roughly one cluster per week — about 14–15
  clusters at a full season, matching `prior_v3`'s own caveat that the interval will be wide.
- **One confirmatory look.** The verdict counts once, using `season_look` from
  `weekly_prior_scale.py`: **final** only when no FBS-vs-FBS regular-season 2026 game is
  still scheduled. Any run before that is labeled `"look": "interim"`, prints and writes its
  numbers for visibility, but **no verdict is quoted from it and nothing is decided because of
  it** — the same rule `prior_v3` uses.
- **Confirm** if, at the final look, β's 95% CI lower bound is **> 0** — the same bar G2 used
  on 2021–2025. Anything else (the interval crosses 0, or β is negative) is **not confirmed**;
  the point estimate and CI are always reported so a near miss is visible, but it is not
  called a partial pass.
- **Also reported, not gated:** MAE and CRPS of P1 against the open and against v1 on the same
  2026 games — descriptive, the same way `prior_v3`'s confirmation reports `prior_v3` vs `open`
  and `ridge_v1` vs `open` without gating on them.

## What a confirmed GO would unlock — and what it would not

- **Would unlock:** registering the ATS amendment named in
  [`objective-review-2026-09-23.md`](../../../research/spread/docs/objective-review-2026-09-23.md)
  item 1, now with a rating that has shown the open-relative information the review asked for.
- **Would not:** license a bet by itself. Registering the amendment is a separate, later step
  with its own declared rule — this spec only decides whether P1's G2 result is real.
- **A "not confirmed" result is not a failure of P1's power-rating quality.** G1 (vs Elo) and
  the descriptive use of the rating and RD stand regardless of this confirmation's outcome.

## Files

- `scripts/glicko_p1_confirm.py`:
  - `freeze()`: writes `scripts/glicko_p1_frozen.json`; refuses to overwrite
    (`weekly_prior_scale.write_freeze`, reused unchanged).
  - `confirm(season, frozen_path)`: reads the freeze, refuses to run without it, computes
    2026 (or whichever season is passed) forecasts, and labels the look via `season_look`.
  - CLI: `python -m scripts.glicko_p1_confirm freeze` (run once, now) and
    `python -m scripts.glicko_p1_confirm confirm --season 2026` (run anytime; interim until
    the season is final).
  - Writes `data/processed/ratings/glicko_p1_confirm_<season>_<look>.json` — gitignored, one
    file per look so an interim run never overwrites what came before it.
- `scripts/glicko_p1_frozen.json`: the frozen candidate, committed today on its own.
- `tests/test_glicko_p1_confirm.py`:
  - `freeze()` refuses to overwrite an existing frozen file.
  - `confirm()` refuses to run without a frozen file.
  - An interim look (a synthetic schedule with a future game) is labeled `"interim"` and its
    result carries no `"verdict"` key; only a schedule with nothing left to play produces one.
- **The final look gets its own dated finding doc** when the 2026 regular season completes —
  not before. An interim run is not written up; this spec's freeze is the record until then.

## What this cannot claim

- **Before the final look, nothing.** An interim number is visibility only.
- **No betting value even if confirmed.** The open has no capture time, same as every rung in
  this family — see P1's result for that limit's origin.
- **Not independent of P1's own tuning choices.** The grid, the adopt rule, and the stress
  check were all set before 2021–2025 was scored a second time; 2026 is the first data this
  specific configuration has never touched, which is the entire point of sealing it now.

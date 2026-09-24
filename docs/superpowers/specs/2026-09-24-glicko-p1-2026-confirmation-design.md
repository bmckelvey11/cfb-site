# Glicko P1's encompassing slope, sealed for a 2026 confirmation — design

**Status:** declared and frozen 2026-09-24, before any 2026 confirmation is read. The freeze
was regenerated once, same day, to switch from a code-hash seal to a forecast-fingerprint seal
(see "What is frozen" below) — no confirmation had been read at that point, so nothing changed
hands. The confirmation itself waits for the season; the first interim check ran clean
(`fingerprint_ok=True`, β = 0.011 [−0.25, 0.31] on 3 of ~15 weeks, no verdict).
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

`scripts/glicko_p1_frozen.json` records these exact values, their source commits
(`c28745e8`, `0e2e0373`), and a **forecast fingerprint**: the sha256 of (`game_id`, forecast
mean, forecast sd) for every one of P1's own 2021–2025 primary games, recomputed fresh from
the pool/model code each time — not read from a stored number. Freezing a fingerprint of the
forecasts, rather than a hash of the confirmation script's own text, means a later edit to
`glicko_ratings.py` or `glicko_pool_eval.py` (the preseason-prior rung, for one) is caught even
if this script is untouched, and an edit to this script alone does not falsely trip it. The
fingerprint carries no 2021–2025 outcome, so recomputing it at confirm time is not a further
read of those seasons' results. `confirm` recomputes it and refuses to emit a final verdict —
prints and writes the mismatch instead — if it no longer matches.

**Regenerated once, 2026-09-24** (freeze committed in `06987caa`, then rebuilt this same
session before the branch was reviewed further): the first freeze hashed the confirmation
script before its `open_sd` fix landed, which would have shown as script drift at the final
look for a reason that has nothing to do with the candidate. `FROZEN_P1`'s params were never
touched; only the recorded hashes and the switch to a forecast fingerprint changed. This is
the one and only time the freeze is regenerated — `write_freeze` refuses from here on, same as
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
- **The fingerprint gates the verdict too.** A final look whose forecast fingerprint no longer
  matches the freeze prints and writes the mismatch, but emits no `"verdict"` key at all — not
  even a "not confirmed" one, since that would misreport a broken seal as a real result. Later
  rungs (the preseason-prior rung, most likely) may edit `glicko_ratings.py` or
  `glicko_pool_eval.py` only in ways that leave this fingerprint matching, or they must
  re-freeze and re-declare this confirmation before it is read.
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
  - `p1_primary_fingerprint(data_root)`: recomputes the sha256 fingerprint fresh — never
    reads a stored value except at freeze time.
  - `_verdict(look, encompassing, fingerprint_ok)`: pure function, no I/O. Returns `None`
    unless `look == "final"`, an encompassing result exists, and the fingerprint matches;
    otherwise `"confirmed"` or `"not confirmed"` from the CI lower bound.
  - `freeze()`: writes `scripts/glicko_p1_frozen.json`; refuses to overwrite
    (`weekly_prior_scale.write_freeze`, reused unchanged).
  - `confirm(season, frozen_path)`: reads the freeze, refuses to run without it, recomputes
    the fingerprint, computes 2026 (or whichever season is passed) forecasts, labels the look
    via `season_look`, and calls `_verdict`.
  - CLI: `python -m scripts.glicko_p1_confirm freeze` (run once, now) and
    `python -m scripts.glicko_p1_confirm confirm --season 2026` (run anytime; interim until
    the season is final).
  - Writes `data/processed/ratings/glicko_p1_confirm_<season>_interim_<date>.json` for an
    interim look (gitignored, dated so successive interim runs never overwrite each other) or
    `glicko_p1_confirm_<season>_final.json` for the final one — `confirm` refuses to
    overwrite an existing final file.
- `scripts/glicko_p1_frozen.json`: the frozen candidate, committed today, carrying the
  params, source commits, and the forecast fingerprint.
- `tests/test_glicko_p1_confirm.py`:
  - `freeze()` refuses to overwrite an existing frozen file.
  - `confirm()` refuses to run without a frozen file.
  - `_verdict` is `None` for an interim look regardless of the encompassing result.
  - `_verdict` is `None` at a final look whose fingerprint no longer matches, even with a
    clearly positive slope.
  - `_verdict` is `"confirmed"` only when the CI lower bound is positive; otherwise
    `"not confirmed"`, at a final look with a matching fingerprint.
- **The final look gets its own dated finding doc** when the 2026 regular season completes —
  not before. An interim run is not written up; this spec's freeze is the record until then.

## What this cannot claim

- **Before the final look, nothing.** An interim number is visibility only.
- **No betting value even if confirmed.** The open has no capture time, same as every rung in
  this family — see P1's result for that limit's origin.
- **Not independent of P1's own tuning choices.** The grid, the adopt rule, and the stress
  check were all set before 2021–2025 was scored a second time; 2026 is the first data this
  specific configuration has never touched, which is the entire point of sealing it now.

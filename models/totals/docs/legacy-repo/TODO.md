# Fix backtest inference issues

Plan from the econometrics review. Do not cite 57.00% / +8.82% ROI / +1.52 pp until the leakage item is done and re-graded. Do not start citing the open–close gap until the paired test exists.

---

- [x] Drop leaked features (havoc, attendance, contaminated winProb)

  - **Intent** — The model must only see information available before the bet. Current-game havoc, reported attendance, and post-game win probability make the 57% hit rate unusable as evidence.
  - **Already shipped** — Entering-game pace/PPA/success via `shift(1).expanding()` in `data._entering_game_stats` is clean and tested. Elo, talent, recruiting, returning PPA, and `home_running_*` registry cols are entering-game.
  - **Gaps** — `_REGISTRY_COLS` still includes `home/away_havoc_*_rate` (4), `attendance`, and `home_pregame_win_prob` (this is team-scoped `pregame_win_prob`, not the clean `pregame_home_win_prob`). Comment on that tuple claims they are already entering-game. No test fails if they come back.
  - **Shape** — Remove those six names from `_REGISTRY_COLS` in `cfb_totals_model/data.py`. Fix the comment. Optional: if a real pregame home win prob is wanted later, add `pregame_home_win_prob` as a new col — out of scope for v1. Do not retune GBM. Do not add new feature groups.
  - **Done when** — `feature_cols` contains none of those six keys; a unit test asserts they are absent; `python -m pytest` passes.

- [x] Re-grade walk-forward on the clean feature set

  - **Intent** — Replace the leaked 57% with a number that could actually be cited, with uncertainty.
  - **Already shipped** — `walk_forward` + `Backtest.summary` / `by_season` / `permutation_test`. Chronological splits and push-dropping stay.
  - **Gaps** — `summary()` prints bare hit% / ROI, no CI. Graded frame `keep` list has no `week`, so week-clustered SEs cannot be computed from the saved rows. README / `docs/MODEL.md` still lead with 57.00% (2023–25) and EARLY-WEEKS with 55.98% (2021–25).
  - **Shape** — Keep `week` (and `game_id`) on graded rows. Re-run `python -m cfb_totals_model backtest --line ou_open --permute` after the drop. Put the new table in `docs/MODEL.md` with n, hit, Wald-or-clustered 95% CI, and MDE vs 52.38%. Strike or footnote the old 57% as invalid. Leave EARLY-WEEKS as a dated note that it used leaked features — do not re-litigate early-week strategy here.
  - **Done when** — MODEL.md headline table is from the clean walk-forward and every cited hit/ROI has a CI; README matches that table.

- [x] Proper score vs the line, paired, with clustered CI + MDE

  - **Intent** — Know whether the model’s *forecast* beats the market, not only whether signed residuals win a coin flip.
  - **Already shipped** — Point prediction `pred`; MODEL.md already notes MAE 12.86 vs market 12.80 (closing, leaked-feature era). Grading is hit/ROI only.
  - **Gaps** — No paired MSPE/MAE Δ vs the line used for betting. No cluster. No MDE. Hit rate is not a proper score. Permutation test only checks shuffled edges sit near 50%.
  - **Shape** — v1: per-game `d = (pts − pred)² − (pts − line)²` (and the MAE analogue), mean Δ with week-clustered SE, 95% CI, and MDE printed next to it. Add a `week` column so clustering is possible. Hit/ROI stay as extras at **one** frozen threshold (see below), also with week-clustered CI. Do not build a new probability model or CRPS-from-ensemble in v1 — later.
  - **Done when** — `backtest` CLI prints paired Δ vs line with CI and MDE; a test on toy data checks the Δ is computed on the same games (paired).

- [x] Paired open-vs-close test and CLV on this model’s bets

  - **Intent** — Measure whether betting the open is worth more than the close *for these predictions*, and whether the line later moved toward the model — not a 1.52 pp difference of two unpaired rates, and not the 344-bet personal CLV sample.
  - **Already shipped** — `compare_lines.py` holds `pred` fixed (fit on `ou_open`) and grades open vs close; drops pushes; restricts to games with both numbers.
  - **Gaps** — Prints two hit% and a subtract. No per-game pairing, no CI, no MDE. No signed CLV (`bet_side` × open-to-close move). Docs treat +1.52 pp and +0.29 pts (other sample) as the same finding.
  - **Shape** — Same script: per-game hit_open − hit_close, week-clustered CI + MDE; plus mean CLV for the model’s side with CI. Do not import the personal 344-bet CLV as corroboration.
  - **Done when** — `python compare_lines.py` prints Δ hit with CI/MDE and mean CLV with CI; MODEL.md’s open-vs-close section uses those, not the unpaired 1.52 pp.

- [x] Report 2021 week-expanding separately from 2022+ prior-season folds

  - **Intent** — Do not average two different validation designs into one headline.
  - **Already shipped** — `iter_walk_forward_splits` + `FoldResult.week_expanding`. CLI already labels expanding folds.
  - **Gaps** — Default `--seasons` is 2021–25; `summary()` concatenates all folds. README still cites 2023–25 while the default window moved.
  - **Shape** — Headline backtest stays **2022–25 prior-season only** (or 2023–25 if 2022 train is too thin — pick one and freeze it). Print 2021 expanding as a separate block, not mixed into `summary()`. No new split logic.
  - **Done when** — One frozen test window is documented and is the only window in the headline table; 2021 expanding, if run, is a labeled appendix.

- [x] Freeze one edge threshold for the ship/no-ship number

  - **Intent** — Stop treating the luckiest `|edge|` cutoff as the result.
  - **Already shipped** — `summary(thresholds=(0, 1, 2, 3, 5))` as a diagnostic ladder. MODEL.md already flags ~35 parent-project hypotheses.
  - **Gaps** — Headline and “monotonic = real signal” language use the whole ladder. EARLY-WEEKS added more bins on leaked features.
  - **Shape** — Pre-declare **one** threshold for the citable row (recommend `|edge| ≥ 0` as the unselected full book, or `|edge| ≥ 3` if that was locked before seeing 2025 — state which and why in MODEL.md). Keep the ladder in the CLI as diagnostics, labeled as such. Do not re-run EARLY-WEEKS as part of this fix.
  - **Done when** — MODEL.md has exactly one citable hit/ROI row with CI; other thresholds are explicitly diagnostic.

---

Later / out of scope: Bovada takeability, prices other than −110, GBM tuning, a real P(under) model, spread model, early-week strategy, swapping in `pregame_home_win_prob`.


# Plan: harden the 2026-09-08 spread line-movement next-steps plan
_Locked via claudex-loop — by Claude + mckel, 2026-09-08. Revised after Codex review rounds 1–2._

**This plan does not replace `docs/superpowers/plans/2026-09-08-spread-next-steps.md`.** That
file (962 lines, 14 tasks, Task 2 done) stays the executable artifact with the code and the
per-step expected output. This document is the contract around it: what it is for, the
contestable decisions inside it, and the defects found by reading it against its two spec
documents together. Reviewers should read both. §"Required amendments" lists the edits this
loop obliges the plan file and the prereg to take before their tasks run; the three-round Codex
argument that produced them is in `plan-review-log-2026-09-08.md`, and the parallel build
decomposition is in `build-brief-2026-09-08.md`.

## Goal

Decide, on a pre-registered schedule, whether the decontaminated archive result — the screened
model consensus (E4) anticipates ~15% of the open→close move, γ ≈ 0.29, positive in 20 of 20
seasons — survives at a price the user can actually get: the first Monday snapshot of the week.

**That archive result is conditional on a full-sample decontamination screen** (Risk 4) and must
be described that way everywhere until the walk-forward rerun lands. Everything else in the plan
exists to make the version B answer trustworthy rather than to add models.

## Approach

Executable detail is in the plan file. In brief:

1. **Phase 1 — data integrity and the cheap questions.** Backfill AN histories lost to the
   09-04 → 09-08 collector outage (T1); a `collector_health.py` that exits non-zero on a stale
   stream (T3); read each model's publication time off snapshots already on disk (T4);
   amendment A4, a finer ridge grid to decide whether E6 keeps its place in `weekly_slate.py`
   (T5); amendment A5, whether E4's disagreement with PT's `line` predicts the residual
   PT-line → AN-close move (T6); amendment B2, slope decay across Monday/Tuesday/Wednesday
   captures (T7).
2. **Phase 2 — weekly.** Chain the version B grader onto the existing Monday `CFB-AN-History`
   task, health check first (T8); line-shopping amendment S1, outlier guard and price-adjusted
   value (T9); verify "AN scoreboard = close" once 2026 closes exist (T10, blocked on a
   `cfb_system_maker` scrape).
3. **Phase 3 — the decision.** At season end, read version B's E4 slope and apply the decision
   table fixed in T11 Step 2, under the single stopping rule in decision 6.
4. **Hygiene.** T12–T14, each its own commit.

## Key decisions & tradeoffs

1. **The existing plan is lifted, not rewritten.** A fresh plan from the same two spec docs
   would duplicate 962 lines already in git and already being executed against, and would send
   Codex at the wrong artifact.
2. **One primary confirmatory family: the version B E4 slope at the Monday anchor.** Everything
   archive-side (A1–A5) and the line-shopping amendments are **exploratory**, and their
   sections must say so. Holm within a family stays; no across-family correction is attempted,
   because with one confirmatory hypothesis none is needed. This is the adopted resolution to
   review round 1 finding 1 — a ledger alone documents forks without controlling them.
3. **E4 is the graded predictor; E6 and the model median are reported beside it with no
   selection among them** (prereg B1, "fixed now, before data"). E6 is the higher-R² method on
   the full panel and the bigger loser to decontamination (0.248 → 0.163, 66% retained vs E4's
   90%) — grading the more robust method rather than the higher-scoring one is deliberate.
4. **E6 keeps running in production at λ = 10⁴, a known grid edge, until A4 decides — and A4's
   output is an engineering decision, not an inferential claim.** A4 chooses which λ
   `weekly_slate.py` serves. It does not license "the ridge works"; its R² is reported without
   a p-value and labelled exploratory.
5. **The version B predictor set is frozen for the season.** `MODEL_COLS` and `PARAMS` in
   `weekly_slate.py` define `pred_close`; changing them mid-forward-test silently redefines the
   quantity being graded. If A4 drops E6, the change is versioned (`model_set_version`) and the
   existing forward-log rows are recomputed before any read quotes `pred_close`.
6. **The stopping rule, stated once and in these words: no verdict before season end; at season
   end, confirmatory inference requires ≥ 8 week clusters, and with fewer the read is reported
   as inconclusive.** Round 1 finding 3: "act when `mde_80 ≤ 0.2`" is a data-dependent stopping
   time, and the MDE is itself estimated from the same data. The observed MDE is reported at
   every read and triggers nothing. Nothing else in this document or the plan file may state the
   rule differently.
7. **Weekly reads are reported but decide nothing.** With decision 6 this is now enforced by the
   gate's definition rather than asserted.
8. **Version B's target is Action Network book 15 (consensus), last full-game tick before
   kickoff**, not PT's `line`. Measured: PT's `line` is a late line, not the close — mean |Δ|
   0.69, exact on 31%, within 0.5 on 67%.

## Toolchain

Skill inventory scan, both benches:

- **Claude side loads `econometrics`** for the inference work (leakage, clustering, multiplicity,
  power, forking paths). Installed at `~/.claude/skills/econometrics`.
- **Asymmetry:** `econometrics` is **not** installed on the Codex bench (`~/.agents/skills/`);
  `statistical-analysis` is. So the inference questions went into the review prompt explicitly.
  This worked — round 1's sharpest findings (2, 3, 4) were all inference findings.
- `~/.codex/config.toml` pins `model = "gpt-6-astra"`, which **CLI 0.151.0 cannot run** (400:
  "requires a newer version of Codex"). Review rounds run with `-c model="gpt-5.5"` at the
  user's instruction; `model_reasoning_effort` raised low → high (backup at `config.toml.bak`).
  The broken pin affects all Codex use here, not just this review.

## Assumptions

_Confirmed by the user, 2026-09-08. Sources are repo paths unless noted._

1. Brownfield; `research/spread/` is current and matches both spec docs.
2. The next-steps plan exists at `docs/superpowers/plans/2026-09-08-spread-next-steps.md`;
   Task 2 done, Tasks 1 and 3–14 open. — `git show --stat ca39a4f`
3. **Review §5 "all done" ≠ plan tasks done.** §5 is the audit's own remediation list; the plan
   is forward work. 13 of 14 plan tasks are open.
4. A3 decontamination ran and is recorded: E4 0.170 → 0.153 (90% retained), E6 0.248 → 0.163,
   15 models dropped at ρ ≥ 0.365, three of them margin-era "best forecasters". Its screen is
   **full-sample** — see Risk 4. — `line-movement-results.md` §A3
5. `eval_version_b.py` and `check_pt_line_is_close.py` exist and ran; PT `line` vs AN close
   measured at mean |Δ| 0.69. — `research/spread/scripts/`
6. `tests/test_spread_estimators.py` exists with three cases — weaker than the review specified
   (a single null draw, not p ~ uniform), and covering none of `holm`, `pick_1se`, the E6–E14
   fitters or the decontamination screen. — the file
7. Headline numbers are single-sourced: no `0.248`/`0.170` left in `research/spread/CLAUDE.md`
   or `research/spread/docs/README.md`. — grep
8. `weekly_slate.py:65` serves E6 at λ = 10⁴ with a comment justifying it; A4 (T5) is the
   queued fix. Not a silent defect.
9. **The §2 collector fix is claimed, not verifiable from git** — the Task Scheduler conditions
   live in the UI. Plan T1 Step 3 is still unchecked. Treated as claimed-unverified.
10. `archive/spread-margin-era/scripts/diag_weight_concentration.py:46` still carries the
    hardcoded `C:/Users/mckel/data/cfb/processed` fallback (guarded by `hasattr`, archived).
11. Research gate: **none**. Internal econometrics on a private panel.
12. **No leakage in the live path.** Confirmed independently by round 1: the close and the score
    reach version B only as grading targets, never the predictor.

## Risks / open questions

_Renumbered after round 1. Each carries the adopted resolution._

1. **Amendment stack vs the prereg's stopping rule.** The prereg says "one run of A; no interim
   looks; no re-thresholding"; since then A2, A3, B1, with A4, A5, B2, S1 queued. **Resolved by
   decision 2** — one confirmatory family (version B E4 slope), everything else labelled
   exploratory — plus an amendment ledger in the prereg recording each amendment's motivation
   and whether that motivation was data-driven.
2. **A4 is post-hoc grid selection.** The data chose the grid. **Resolved by decision 4:** A4 is
   an engineering choice about what to serve, reported without inferential claims.
3. **Weekly reads as a sequential test.** **Resolved by decision 6:** a calendar/cluster-count
   gate replaces the observed-MDE crossing.
4. **The decontamination screen is fit on the full sample, evaluation seasons included.**
   `eval_line_movement.py:64` computes `ρ_i = corr(f_i − open, close − open)` over all of
   2001–2025 and drops the top decile before fitting. The in-code comment argues this "can only
   cost accuracy — there is no optimistic bias". That is right about the *direction* for R²
   (the screen removes the most target-correlated columns, so retained R² is if anything biased
   down) but wrong that the screen is therefore innocuous: the **identity of the retained panel
   was chosen with knowledge of the evaluation seasons**, so the A3 p-values are conditional on
   a screen that saw its own test set. **Adopted fix:** recompute the drop list walk-forward
   from training seasons only (the screen is already a per-season-fittable quantity), rerun A3,
   and until then label the A3 archive inference "conditional on a full-sample screen".
   Priority: high — A3 is the result the whole tree's self-description rests on.
5. **B1's power arithmetic is iid, the estimator is clustered.** `prereg-line-movement.md:127`
   uses `σ_resid/(σ_x√n)`, while `eval_version_b.py:119` falls back to HC1 whenever weeks <
   `MIN_WEEKS`. The published `n_for_mde_0.2 ≈ 80` therefore comes from one week's HC1 SE and
   understates the n a clustered design needs. **Adopted fix:** compute the MDE from the
   cluster SE (or a season-week bootstrap) and report it only once the cluster count clears the
   fallback; the reported n stays informational until then.
6. **T9 reuses the constant the review retired.** Review §1.5 retired "3.2 win-rate points per
   point of spread" as an in-sample line-shopping P2 constant; T9 Step 3's value column is
   `3.2 * gain − 100*(breakeven(best) − breakeven(median))`. **Unresolved — the user's call.**
   Either the constant is fit for converting *shopping* gains (it was estimated on exactly that
   sample, which is an argument for it) and §1.5's retirement was about the *movement* CLV
   claim only, or T9 needs a different conversion. The plan must say which.
7. **Two decision tables have undefined regions.** T4 Step 5 has actions for "≥ 15 of 20" and
   "< 10" but none for 10–14. T11 Step 2 row 1 requires "slope < 0.10 **and** CI excludes 0.20";
   under-0.10-with-a-wide-CI matches no row — the likely case, not a corner one. **Adopted fix:**
   fill both, before the runs that reach them.
8. **T8's health check does not gate anything.** The plan's code runs `history()` first, then
   `collector_health.py` and `eval_version_b.py` under `check=False`. A stale stream produces a
   read anyway. **Adopted fix:** run health first and skip the *grade* (not the pull) on a
   non-zero exit, recording the skip.
9. **B2 overweights games with more snapshots.** `capture_offsets` returns every (game,
   snapshot) row, so one game contributes several rows to a bucket, and buckets hold different
   game sets. **Adopted fix:** one pre-specified capture per game per bucket, a fixed game set
   across buckets, missingness reported, resampling clustered by game and week.
10. **`pred_close` can be redefined mid-forward-test.** T5 may drop E6 from `MODEL_COLS` while
    forward-log rows written under the old definition stay in the sample. **Resolved by
    decision 5** (versioned model set, historical rows recomputed).
11. **A5 treats a walk-forward prediction as a fixed regressor.** `cluster_ols` carries no
    first-stage uncertainty. **Adopted fix:** label the CI conditional on the fitted predictor;
    a season-week bootstrap of the whole pipeline only if A5 lands near a decision boundary.
12. **Estimator tests are thin.** No `holm`, no `pick_1se`, no decontamination screen, no null
    p-value calibration. **Adopted fix (scoped):** add `holm` (known-input), `pick_1se`
    (known-input), a repeated-null uniformity check on `wild_cluster_boot`, and — once Risk 4's
    walk-forward screen exists — **a test that the drop list is built from training seasons only
    and that no evaluation-season row reaches it.** Round 2 was right that omitting this one was
    over-narrowing: Risk 4 makes the screen central, and an untested walk-forward screen is the
    same defect one layer down. **Rejected:** per-fitter tests for E6–E14 — they are exercised
    end-to-end by the registered runs and per-fitter unit tests would be gold-plating.
13. **The across-target multiplicity question is silently resolved.** Review §1's NOTE deferred
    it as "low priority if §1.1 survives"; §1.1 survived. **Adopted fix:** say so in one line
    rather than leaving a reader with an open item.
14. **T10 is an external dependency, not a task** — it needs a `cfb_system_maker` AN scoreboard
    re-scrape that nothing in this plan triggers. Mark it blocked-on-external.
15. **T1 Step 3 is answerable now** — enough 6-hour slots have passed since the scheduler fix
    that `LastTaskResult` can be read, closing assumption 9.

## Required amendments to the plan file and the prereg

Before the tasks they touch run:

- **Prereg:** an amendment ledger; the confirmatory/exploratory split (decision 2); the B1 gate
  restated as cluster-count + season end (decision 6); the MDE computed from the cluster SE
  (Risk 5).
- **Plan T5:** A4 labelled exploratory; if E6 is dropped, the versioned-model-set procedure
  (decision 5).
- **Plan T7:** one capture per game per bucket, fixed game set (Risk 9).
- **Plan T8:** health check gates the grade (Risk 8).
- **Plan T4 and T11:** the undefined branches filled (Risk 7).
- **Plan T9:** marked **blocked pending user decision** in the plan file itself, not only here —
  an executor must not run it with the `3.2` question open (Risk 6).
- **Plan, new task:** walk-forward decontamination screen and an A3 rerun (Risk 4).
- **Plan T12–T14 area:** the four scoped estimator tests, including the walk-forward
  drop-list test (Risk 12).

## Out of scope

- New models, new data sources, or new targets. Three targets have already been tried on this
  one panel (margin vs close, margin vs open, close vs open).
- Re-opening the margin era. `archive/spread-margin-era/` is retained for audit history and is
  not cited as current.
- Alpha-spending machinery for the weekly reads. Decision 6 removes the sequential-test problem
  by fixing the checkpoint; a spending function would be complexity bought for a design that no
  longer stops early.
- Per-fitter unit tests for E6–E14 (Risk 12).
- Scraping PT's constituent models directly. A downstream tree, opened only if T4 shows the
  leading forecasters publish before PT compiles and T11 lands in the "bettable" branch.

# Plan Review Log: harden the 2026-09-08 spread line-movement next-steps plan

> **Absorbed 2026-09-08 into `plan-2026-09-08-master.md`.** What these three rounds settled
> is carried into that document's §4 and §7. Retained in full as the record of the argument.

Phases 0-1 (recon + interrogation) complete — plan locked with the user. MAX_ROUNDS=5.

Framing decision (Q1): lift the existing 962-line next-steps plan into the loop rather than
writing a new one. `plan-2026-09-08-hardened.md` (`PLAN.md` during the loop) is the contract around
`docs/superpowers/plans/2026-09-08-spread-next-steps.md`, not a replacement for it.

Reviewer: codex-cli 0.151.0, model `gpt-6-astra`, `model_reasoning_effort` raised low → high
for this review at the user's instruction.

---

## Round 1 — Codex

Note: round 1 was attempted first on the config-pinned `gpt-6-astra` and failed with
`400 invalid_request_error: The 'gpt-6-astra' model requires a newer version of Codex`
(CLI 0.151.0). Rerun on `gpt-5.5` at the user's instruction; config left unchanged.

Read-only review. No files changed. I did not run tests because pytest can write cache/output.

**Material Findings**
1. Multiplicity fix is not enough. [PLAN.md](C:/Users/mckel/dev/cfb/PLAN.md:104) proposes ledger only, but A2/A3/B1 already happened and A4/A5/B2/S1 add more chances to find a usable story after seeing earlier results. Ledger documents forks; it does not control them.
Fix: define one primary family, likely Version B E4 slope, and mark amendment outputs exploratory unless corrected within archive/live/shopping families.

2. B1 power gate is not valid for clustered inference. [prereg-line-movement.md](C:/Users/mckel/dev/cfb/research/spread/docs/prereg-line-movement.md:127) uses iid-style `sigma/(sd_x*sqrt(n))`; [eval_version_b.py](C:/Users/mckel/dev/cfb/research/spread/scripts/eval_version_b.py:119) falls back to HC1 when weeks < 5. Current `n_for_mde_0.2 = 80` comes from one cluster, not cluster evidence.
Fix: gate only after minimum week clusters and compute MDE from cluster SE or a cluster bootstrap, not HC1-scaled n.

3. Weekly reads create a sequential test. [PLAN.md](C:/Users/mckel/dev/cfb/PLAN.md:51) says reads decide nothing, but [Task 11](C:/Users/mckel/dev/cfb/docs/superpowers/plans/2026-09-08-spread-next-steps.md:918) allows action as soon as observed MDE crosses 0.2. That is a data-dependent stopping time.
Fix: use fixed calendar/sample checkpoints or alpha-spending; otherwise season-end only.

4. Decontamination leaks archive evaluation outcomes. [eval_line_movement.py](C:/Users/mckel/dev/cfb/research/spread/scripts/eval_line_movement.py:64) computes `rho` on full 2001-2025 data, including evaluation seasons, then reports archive p-values as if regressor screen were fixed.
Fix: recompute drop list walk-forward using training seasons only, or use an external pre-fixed market-proxy list and label current A3 archive inference conditional.

5. A4 is post-hoc model selection, not just documentation. It exists because E6 hit edge and wide grid disappointed after seeing results. Saying “data-motivated” is honest but not enough if used to keep/drop production E6.
Fix: either mark A4 exploratory and wait for Version B, or include it in amendment-family correction before making inferential claims.

6. Task 8 contradicts itself. It says health check first, but planned code runs `history()` first and runs health with `check=False` [plan](C:/Users/mckel/dev/cfb/docs/superpowers/plans/2026-09-08-spread-next-steps.md:781). Stale PT stream would not fail Monday routine.
Fix: run `collector_health.py` before history/evaluation and abort on nonzero unless explicitly in report-only mode.

7. B2 decay estimate overweights games. `capture_offsets` returns every snapshot row [plan](C:/Users/mckel/dev/cfb/docs/superpowers/plans/2026-09-08-spread-next-steps.md:719), so one game can contribute multiple rows per bucket; buckets also have different game sets.
Fix: use one pre-specified capture per game per bucket, report missingness, and cluster/resample at least by game plus week.

8. `pred_close` can silently change mid-forward test. Task 5 can remove E6 from `MODEL_COLS`, changing future `pred_close` while old forward-log rows keep old definition.
Fix: freeze Version B predictor definitions or add `model_set_version` and recompute historical forward rows before reporting `pred_close`.

9. A5 ignores estimated-regressor uncertainty. It regresses AN close residuals on walk-forward predictions [plan](C:/Users/mckel/dev/cfb/docs/superpowers/plans/2026-09-08-spread-next-steps.md:627) but `cluster_ols` treats predictor as fixed.
Fix: bootstrap whole prediction-plus-second-stage pipeline by season-week, or label CI conditional.

10. Tests do not cover estimator core. [tests/test_spread_estimators.py](C:/Users/mckel/dev/cfb/tests/test_spread_estimators.py:30) covers Anchor zero correction, gamma recovery, one bootstrap smoke test. No `holm`, no E6-E14 fitters, no `pick_1se`, no decontam screen, no null p-value uniformity.
Fix: add targeted tests for each shared estimator and a repeated-null calibration check.

**PLAN Risks**
Risk 1: correctly diagnosed, resolution inadequate. Needs correction/hierarchy, not ledger alone.

Risk 2: correctly diagnosed, understated. A4 can only be confirmatory if analysis family and correction are fixed.

Risk 3: understated. “Reads are not looks” fails once MDE crossing triggers action.

Risk 4: correctly diagnosed, unresolved. T9 still reuses retired `3.2` despite results warning not to convert CLV with it [line-movement-results.md](C:/Users/mckel/dev/cfb/research/spread/docs/line-movement-results.md:69).

Risk 5: correctly diagnosed. Undefined 10-14 publish-count branch and slope <0.10 but CI not excluding 0.20 branch must be filled.

Risk 6: minor, but real. Document why across-target correction is closed or mark it open.

Risk 7: correctly diagnosed. T10 cannot finish without `cfb_system_maker`; make it explicit external dependency, not normal task.

Risk 8: non-issue for plan soundness, but operationally should be checked before relying on scheduler state.

Live leakage answer: close and score do not appear to enter Version B predictor path; they enter grading only. Archive decontamination screen is bigger leakage problem.

Power answer: one-season gate may be reachable if 5+ weeks give stable cluster SE, but current one-week HC1 `n=80` claim should not be used.

VERDICT: REVISE
### Claude's response

Verified in code before accepting: finding 4 (`eval_line_movement.py:64-80`, rho over the full
2001-2025 frame), finding 2 (`eval_version_b.py:111-128`, HC1 fallback below `MIN_WEEKS`),
finding 6 (plan lines 779-786, `history()` runs first and both children run under
`check=False`), finding 3 (plan line 918, the gate reads `slope.E4.mde_80 <= 0.2`). All four
hold as described.

**Accepted in full — 1, 2, 3, 4, 6, 7, 8, 9.**

- 1 -> new decision 2: one confirmatory family (the version B E4 slope at Monday); A1-A5 and the
  shopping amendments are exploratory and must be labelled so. A ledger alone documents forks
  without controlling them, which was the right objection.
- 2 + 3 -> new decision 6: the B1 gate becomes a fixed checkpoint (at least 8 week clusters, and
  season end), not an observed-MDE crossing; the MDE is computed from the cluster SE and is
  reported, never a trigger.
- 4 -> Risk 4 rewritten and a new plan task required: recompute the decontamination screen
  walk-forward from training seasons only and rerun A3; until then label A3's inference
  conditional on a full-sample screen. The in-code comment defending the screen is half right --
  the bias direction on R-squared is conservative -- but the retained panel's identity was still
  chosen with knowledge of the evaluation seasons, so the p-values are conditional. This was the
  round's sharpest finding; the audit that motivated A3 did not catch it.
- 6 -> Risk 8: health gates the grade, not the pull.
- 7 -> Risk 9: one capture per game per bucket, fixed game set across buckets.
- 8 -> new decision 5: the version B predictor set is frozen for the season; a change is
  versioned and historical forward rows are recomputed before any read quotes `pred_close`.
- 9 -> Risk 11: label the A5 CI conditional on the fitted predictor; bootstrap the full pipeline
  only if A5 lands near a decision boundary.

**Accepted with narrower scope — 5, 10.**

- 5: A4 is marked exploratory, and the stronger claim is made explicit -- A4's output is an
  engineering choice about which lambda `weekly_slate.py` serves, not an inferential claim, so it
  needs no correction and gets no p-value. "Wait for version B" is rejected: the served slate
  should not sit at a known-wrong grid edge for a season while waiting.
- 10: accepted for `holm`, `pick_1se` and a repeated-null uniformity check on
  `wild_cluster_boot`. **Rejected: per-fitter tests for E6-E14.** They are exercised end to end by
  the registered runs; unit-testing each fitter is gold-plating on a research tree with one
  maintainer.

**Not changed — Risk 6 (the `3.2` constant).** Left explicitly unresolved and flagged as the
user's call, because the two readings are both defensible: 3.2 was estimated on the
line-shopping sample itself, which is an argument for using it there, and review section 1.5's
retirement was aimed at the movement CLV conversion. Guessing here would settle a question the
specs genuinely leave open.

Also carried: PLAN.md now has a "Required amendments" section naming every edit the plan file
and the prereg must take before the affected tasks run, so the contract and the executable plan
cannot drift apart.

---

## Round 2 — Codex

Read-only. Checked current `PLAN.md`.

Prior findings mostly addressed. Multiplicity now fixed by one confirmatory family: Version B E4 Monday slope; archive/shopping work exploratory ([PLAN.md](C:/Users/mckel/dev/cfb/PLAN.md:42)). Power/sequential risk now mostly fixed: observed MDE no longer triggers stop, weekly reads decide nothing ([PLAN.md](C:/Users/mckel/dev/cfb/PLAN.md:59), [PLAN.md](C:/Users/mckel/dev/cfb/PLAN.md:64)). Leakage/decontam issue now correctly promoted to high-priority walk-forward rerun ([PLAN.md](C:/Users/mckel/dev/cfb/PLAN.md:126)).

Remaining problems:

1. Gate wording contradicts itself. Approach says “B1 gate or season end, whichever comes first” ([PLAN.md](C:/Users/mckel/dev/cfb/PLAN.md:33)); decision 6 says “≥ 8 week clusters AND season end” ([PLAN.md](C:/Users/mckel/dev/cfb/PLAN.md:61)). Those are different stopping rules.
Fix: write exact rule once: “no verdict before season end; require ≥8 week clusters for confirmatory inference, else report inconclusive.”

2. Goal still overstates A3. It leads with decontaminated E4 as fact ([PLAN.md](C:/Users/mckel/dev/cfb/PLAN.md:13)) while Risk 4 says A3 inference is conditional on full-sample screen until rerun ([PLAN.md](C:/Users/mckel/dev/cfb/PLAN.md:133)).
Fix: call headline “conditional full-sample-screen result” until walk-forward decontam rerun lands.

3. Finding 5 narrowed to engineering-only A4: defensible. A4 can choose served E6 λ/drop without p-value, if clearly exploratory and no “ridge works” claim ([PLAN.md](C:/Users/mckel/dev/cfb/PLAN.md:51)).

4. Finding 10 narrowed too far. Rejecting per-fitter unit tests for E6-E14 is defensible ([PLAN.md](C:/Users/mckel/dev/cfb/PLAN.md:169)); omitting decontamination-screen test is not, because Risk 4 now says that screen is central and must be walk-forward.
Fix: add one test for train-only drop-list construction/no eval-season input.

5. Risk 6 left as user call: defensible only because Required Amendments blocks T9 until settled ([PLAN.md](C:/Users/mckel/dev/cfb/PLAN.md:192)). Not defensible if executor may run T9 with unresolved `3.2`.
Fix: mark T9 “blocked pending user decision” in executable plan.

Net: revised plan improved, but stopping-rule contradiction and missing decontam-screen test still material.

VERDICT: REVISE
### Claude's response

All four remaining findings accepted; none rejected.

- 1 (gate contradiction): real -- the Approach section still carried "B1 gate or season end,
  whichever comes first" while decision 6 said "≥ 8 clusters AND season end". Two stopping rules
  in one document is exactly the drift this loop exists to catch. Decision 6 now states the rule
  once, in fixed words, with an explicit "nothing else may state it differently", and the
  Approach section points at it instead of paraphrasing.
- 2 (Goal overstated A3): accepted. The Goal now says the archive result is conditional on a
  full-sample screen until the walk-forward rerun lands.
- 4 (decontamination-screen test): accepted -- this was over-narrowing on my part. Risk 4 makes
  the screen central, so an untested walk-forward screen reproduces the same defect one layer
  down. Risk 12 now requires a test that the drop list is built from training seasons only and
  that no evaluation-season row reaches it.
- 5 (T9): accepted. "Blocked pending user decision" now has to be written into the executable
  plan file, not just recorded here, so an executor cannot run T9 with the 3.2 question open.

Round 2 confirmed the narrowing of finding 5 (A4 as an engineering choice) and of the E6-E14
per-fitter tests.

---

## Round 3 — Codex

Read-only re-review done.

No new material blocker found. Round 2 findings addressed:
- Stopping rule now single: no verdict before season end; require `>=8` week clusters.
- A3 now labeled conditional until train-only decontamination rerun.
- A4 narrow engineering-only scope remains defensible.
- Test scope now defensible: decontamination screen test added.

Risk 6 call defensible. `3.2` constant remains user decision, but T9 is explicitly blocked until decision lands. Good enough.

Minor non-blocker: Toolchain note says econometrics/statistical-analysis unavailable; current bench has econometrics. Fix wording before commit to avoid stale process docs.

VERDICT: APPROVED
### Claude's response

Converged at round 3 of a possible 5.

The one non-blocker was half right and is fixed. `statistical-analysis` **is** installed on the
Codex bench -- my Phase 0 listing was truncated before it and PLAN.md wrongly said it was
absent. `econometrics` genuinely is not there (`ls ~/.agents/skills/econometrics` -> No such
file or directory). The Toolchain note now says exactly that.

Loop summary: 3 rounds, 14 findings raised, 12 accepted in full, 2 accepted with narrowed scope,
1 rejected with reason (per-fitter unit tests for E6-E14), 1 item deliberately left open as the
user's call (the 3.2 constant, with T9 blocked until it is settled).

---

## Post-loop resolution — 2026-09-08

The one item the loop deliberately left open is settled. **Risk 6, the `3.2` win-rate-per-point
constant: kept for line shopping, still retired for the movement CLV claim** (user's decision).

The constant was estimated on the line-shopping sample itself -- 2024-25, 3,574 sides -- so it is
the in-sample conversion for that sample, and review section 1.5's objection was aimed at the
"3-5x the bar" phrasing on movement bets, which sit on larger spreads where a point is worth
less. Two different uses of one number; only one of them was wrong.

Condition carried into the build: the S1 results section states that the value column inherits
the constant's limits (in-sample, dominated by 3/7 crossings on small spreads). T9 is unblocked
and becomes agent I in Wave 1 of `build-brief-2026-09-08.md`.

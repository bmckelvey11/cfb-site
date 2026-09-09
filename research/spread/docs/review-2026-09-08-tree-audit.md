# Review — the spread tree, 2026-09-08

> **Open items absorbed 2026-09-08 into `plan-2026-09-08-master.md`.** This audit remains the
> record of what was found and what was fixed, each finding with its resolution date. It is
> not superseded — the master carries only what was still open. One caution when reading it
> as history: the stopping rule it records (amendment B1's MDE gate) was itself later
> replaced; the master's §3 states the rule in force.

Full pass over `research/spread/`: the theory behind each claim, the code that produces it,
the operations that feed it, and how the tree is organised. Econometrics audit checklist
walked in full (leakage, specification, dependence, power, multiplicity, shrinkage, estimated
regressors, selection, identification, stability, scoring); findings below in severity order.
One new computation was run for this review (§1.1, week split); everything else reads the
saved outputs and the code.

## 0. Verdict

| era | verdict | one line |
|---|---|---|
| Margin era (`archive/spread-margin-era/prediction-tracker-findings.md`) | **sound** | Tight null, defects recorded, corrections applied. Cite freely. |
| Line shopping (`line-shopping-results.md`) | **sound with caveats** | The caveats are already in the file (snapshot = close unverified, juice unpriced). |
| Movement era (`line-movement-results.md`) | **sound with caveats** (resolved 2026-09-08) | Decontaminated (amendment A3): E4 keeps 90% of its R², the ridge falls to E4's level. Cite the decontaminated E4 as an upper bound at the opener; PT's `line` is 0.7 pts short of the true close. |
| Version B (forward test) | **grader in place** (2026-09-08) | `eval_version_b.py` written before in-season closes; amendment B1 replaces the 300-game rule with an MDE gate. First read: slope 0.20 on 42 games, no verdict. |

## 1. Theory

### [BLOCKER → resolved 2026-09-08] The movement headline has not been decontaminated

> **Resolution.** Amendment A3 run: E4 R² 0.170 → 0.153 (90%), γ 0.29, CLV unchanged; E6 0.248 → 0.163; E14 0.136 → 0.107. `line-movement-results.md` § A3. Summary sentences rewritten.

- **What.** `line-movement-results.md` leads with E6 ridge: R² 0.248, +2.33 pts CLV, 57.8% ATS
  at the opener; E4 γ = 0.30. `CLAUDE.md` and `README.md` restate this as "the panel works" /
  "the panel does predict where the line goes". The regressors are model values PT recorded
  **mid-week, at an unknown time between open and close**. `archive/spread-margin-era/prediction-tracker-findings.md` §4
  already established, on the opening-line margin target, that E6 retains **27%** of its effect
  once the 15 most market-like columns are removed, and that the partially anchored columns
  carry movement correlations of 0.49–0.76. The movement target makes this worse, not better:
  "prior movement skill" is MSE against the close, which ranks a column that reprints the
  mid-week line above every genuine forecaster. E4's top-20 screen and E6's loadings are
  therefore selected *for* market anchoring.
- **Why it bites here.** A column that is "the Wednesday line plus noise" predicts
  `close − open` with high R² and earns "CLV at the opener" mechanically, because the open→close
  move is mostly done by Wednesday. The archive cannot tell "the panel leads the market" from
  "the panel reports the line after it moved". The live chase diagnostic reading +0.999 is the
  same fact seen from the other side. The documents say the opener is unreachable — correct —
  but still assert the panel *leads*; that clause is unsupported.
- **What this review checked.** Split of the saved predictions by PT week (no refit):

  | week | n | sd(move) | R² E4 | R² E6 | E6 ≥ 2: bets / CLV / ATS at open |
  |---|---|---|---|---|---|
  | 1–2 | 2,312 | 2.94 | 0.158 | 0.289 | 301 / +2.77 / 61.3% |
  | 3–5 | 2,851 | 2.97 | 0.245 | 0.340 | 443 / +2.69 / 55.7% |
  | 6–9 | 3,977 | 2.12 | 0.142 | 0.174 | 476 / +1.90 / 57.6% |
  | 10+ | 4,928 | 2.19 | 0.120 | 0.171 | 347 / +2.09 / 57.6% |

  The effect is **not** a spring-opener artifact — weeks 3–5 are the strongest bucket and the
  by-season CLV means agree (3.04 ± 0.42 vs 2.95 ± 0.70). That removes one alternative
  explanation. It does not touch the contamination one, which is week-independent.
- **Resolves with.** Rerun `eval_line_movement.py` (both `--amend` and not) with the top-decile
  ρ models from `archive/spread-margin-era/scripts/diag_market_proxy.py` dropped — that script computes exactly the discriminator
  needed, `ρ_i = corr(f_i − open, close − open)`, and has never been pointed at this target.
  Report per-method retention of R² and CLV. If E4 keeps ≳ 60% and E6 collapses as it did on the
  margin target, the honest statement is "the *consensus* anticipates a fraction of the move; the
  ridge reads it off". If both collapse, the movement era closes the way the margin era did.
  About ten minutes of compute; no new free parameters. Until then, change the three summary
  sentences (`CLAUDE.md`, `README.md` "current position", `line-movement-results.md` "one-line
  result") to say *upper bound, undecontaminated*.

### [CAVEAT → resolved 2026-09-08] Version B cannot answer its own stopping rule at 300 games

> **Resolution.** Amendment B1: no verdict before the MDE reaches 0.2; the grader prints the MDE and the n it needs. First read shows sd(x) = 1.17, so that n is ~80–140 before clustering, not 1,000.

- **What.** `prereg-line-movement.md` B4: first read at ~300 graded games; close the tree if the
  slope is under 0.1 *with a CI excluding 0.2*.
- **Why it bites.** SE(slope) ≈ σ_resid / (σ_x √n). Reasonable in-season values: σ_resid
  (Monday → close move) ≈ 1.0 pt; σ_x (E4 − Monday line) ≈ 0.45 pt (week-2 snapshots: median
  |gap| 0.27–0.40). At n = 300 that is SE ≈ 0.13, a 95% half-width of ≈ 0.25, and an 80%-power
  MDE of ≈ 0.36. A point estimate of 0.10 cannot exclude 0.20 at that n. The rule needs
  SE ≈ 0.07, i.e. **n ≈ 1,000–1,200 games** before clustering by week, roughly two in-season
  years at 45 games a week. If in-season Monday→close moves are smaller than 1.0 (week 1 said
  0.06), σ_x shrinks with them and n grows further.
- **Resolves with.** Recompute the MDE on the first ~100 in-season graded games using the
  observed σ_resid and σ_x, and amend B4 to a rule the data can decide: either a wider closing
  threshold, or a season-end read with the CI reported and no verdict at 300.

### [CAVEAT → resolved 2026-09-08] Version B has no grading script, and the log is not yet gradable

> **Resolution.** `eval_version_b.py` (anchor rule, AN book-15 close, CFBD scores, cluster/HC1 SE). `weekly_slate.py` no longer logs a stale slate.

- `movement_forward_log.csv` holds 43 games × 7 snapshots, no close, no result, no
  season-week key. Nothing in `scripts/` joins it to Action Network closes or to scores. The
  09-08 snapshot re-logged the same 43 completed games with no book columns (`pt_rollover.py`
  exists for this and `weekly_slate.py` does not call it).
- Write `eval_version_b.py` **now**, before any in-season close exists: which snapshot counts as
  "Monday" (first capture after Sunday 23:59 ET), the AN close source (last pre-kick tick,
  book 15), the slope estimator and its season-week cluster SE, and the CLV/ATS tables of B5.
  Designing the join after seeing the numbers is the defect-8 pattern.

### [CAVEAT → measured 2026-09-08] PT's `line` is taken as the close on assumption

> **Resolution.** `check_pt_line_is_close.py`: 1,219 matched games, mean |Δ| 0.69, exact 31%, within 0.5 on 67%. It is a late line, not the close; recorded in `line-movement-results.md` § target.

- `prediction-tracker.md` calls `line` "the market spread"; every movement number treats it as
  the close. For a season file PT froze months later that is plausible, not shown.
  `README.md` says `compare_lines.py` checks "PT's line columns against the book feed" — it does
  not; that script is a **totals** open-vs-close comparison importing `models/totals`. The check
  was never written.
- Resolves with: join 2024–25 PT `line` to the AN scoreboard close (book 15) on matched games;
  report mean |Δ| and share within 0.5. Twenty lines.

### [CAVEAT → fixed 2026-09-08] The CLV → break-even conversion reuses one in-sample constant

> **Resolution.** The "3–5× the bar" paragraph is replaced; ATS at the opener is the stated measurement.

- "3.2 win-rate points per point of spread" comes from line-shopping P2 (2024–25, 3,574 sides,
  dominated by 3/7 crossings on small spreads). `line-movement-results.md` turns it into "break-
  even needs 0.75 pts CLV, these rules deliver 3–5× that", and `combining-predictions.md` §3
  builds a bet rule on it. Movement bets at |pred| ≥ 2 sit disproportionately on large spreads
  where a point is worth less. The ATS-at-opener column is the honest measurement and is
  present; the "3–5× the bar" phrasing should go.

### [NOTE] Smaller items, all already labelled in the files

- Fixed-set decay curve is post hoc (labelled). "E6 version A" is highlighted inside the A2 table
  although A2 registered E6w (labelled). Direction hit rate conditions on |pred| ≥ 1 (registered).
- Three targets have now been tried on one panel (margin vs close, margin vs open, close vs
  open). Each prereg controls multiplicity within its family only; there is no across-target
  correction. Low priority if §1.1 survives, because γ > 0 in 20/20 seasons is not a
  multiplicity artifact.
- Dependence: 20 season clusters, wild bootstrap, p floor 1/2000 — adequate. Same-weekend
  steam is absorbed by the season cluster.
- Line shopping: 29 season-week clusters with t(G−1) — fine. Its stated limits stand.
- `archive/spread-margin-era/prereg-spread-model.md` is committed and unfitted; the review of 09-02 already recommends
  not building it for spreads. Either fit it once or move it to `archive/` so the "not yet run"
  row stops looking like a queue.

## 2. Operations — the collector has been failing since Thursday (fixed 2026-09-08)

> **Resolution.** All three CFB tasks now allow battery starts, are not stopped on battery, and catch up missed starts; a forced run returned 0. Wrapper exits 3 without `CFB_DATA_ROOT`. Runbook updated.

- `CFB-PT-Snapshot`, `CFB-AN-History`, `CFB-CFBD-Daily` all show last result
  **0x800710E0 (request refused)** at 01:04 on 09-08. The task is `Interactive` logon with
  `DisallowStartIfOnBatteries = StopIfGoingOnBatteries = True` and `StartWhenAvailable = False`.
  `logs/line_timing.log` ends at Fri 09-04 06:30 ("unchanged"); the 09-08 01:15 snapshot was run
  by hand (no log line). About fifteen 6-hour slots were lost, including week-2 game day. The
  runbook calls this the one unrepairable failure; it has now happened once.
- Fix (user action, Task Scheduler UI): clear both battery conditions, set "run task as soon
  as possible after a scheduled start is missed", and consider "run whether user is logged on"
  (needs a stored password). None of that is in the repo.
- `collect_line_timing.cmd` defaults `CFB_DATA_ROOT` to `%USERPROFILE%\data\cfb`, a directory
  that does not exist. Root rule says the variable is required; the wrapper should fail loudly
  instead of writing into a ghost path. `diag_weight_concentration.py:46` carries the same stale
  hardcoded fallback.

## 3. Code (addressed 2026-09-08: tests added, `MARKET_LINES`/`SNAP_DIR` single-sourced, stale-slate guard, `compare_lines.py` moved to `models/totals/`)

Live path: `collect_line_timing.py snapshot` → `predict_upcoming.py` + `weekly_slate.py`, both
importing the estimator core from `eval_prediction_tracker_models.py` / `eval_combination_sweep.py`.
Sign handling is consistent (one flip on ingest, one flip for live rows, checked by `_check()`).
No lookahead found in the live path; `lineca` / `linemidweek` are excluded everywhere they must be.

- **Tests.** `tests/test_prediction_tracker.py` covers the *builder* only. The estimator core —
  `Anchor` (Frisch–Waugh nesting), `gamma_fit`, `wild_cluster_boot`, `holm`, the E6–E14 fitters —
  has no pytest. The "test asserting the anchor reproduces the original estimator to 1e-8" cited
  in `archive/spread-margin-era/prediction-tracker-findings.md` §3 and in the research bundle does not exist in `tests/`
  or `scripts/`; the only checks are inline `_check()` functions run on `__main__`. One
  `tests/test_spread_estimators.py` with three cases (Anchor = R0 at zero correction; `gamma_fit`
  recovers a known γ on synthetic deviations; `wild_cluster_boot` p is ~uniform under the null)
  would cover what the whole tree rests on.
- **`weekly_slate.py`.** Serves E6 at λ = 10⁴, the grid edge the results file itself calls
  mis-scaled; the served ridge is at a known-wrong setting. `PARAMS` are modal walk-forward
  choices frozen in code with no pointer to the JSON they came from. Forward log dedupes per
  snapshot but not per game-state, so a post-kickoff snapshot appends 43 dead rows.
- **Duplication.** `SNAP_DIR` defined three ways (`collect_line_timing`, `predict_upcoming`,
  `weekly_slate` via `base.cfb_paths`); `MARKET_LINES` defined in both `eval_line_movement` and
  `predict_upcoming`. Two alias tables (`build_prediction_tracker` for CFBD, `weekly_slate` for
  AN) are legitimately different targets. Minor: `eval_prediction_tracker_models.py:59` fills a
  missing `pt_week` with 0.
- **`compare_lines.py`** is a totals script (imports `models.totals.*`, grades `ou_open` vs
  `total`). It belongs in `models/totals/` and the README row describing it is wrong.

## 4. Organisation (addressed 2026-09-08: margin era archived, README and CLAUDE.md rewritten, session guide bannered, paths fixed)

- `README.md` is the tree's best asset: complete index, era tags, script → doc → output map.
  Keep it as the single entry point.
- **The headline numbers live in five places** — `CLAUDE.md`, `README.md` "current position",
  `session-guide-2026-09-02.md` §5.5 and §9, `line-movement-results.md`, `review-2026-09-02` §6.
  When §1.1 or version B changes the reading, five edits. Numbers should live in the results
  file only; the others point.
- **Stale paths.** `session-guide-2026-09-02.md` and `prediction-tracker.md` say `raw/…`; data
  moved to `ingest/` in `e2e9e5d`. The session guide also says "four snapshots exist" and cites
  scheduled-task health that is no longer true. It is a dated record and should say so at the
  top rather than be reading-order item 1.
- `prediction-tracker-research-bundle.json` (2,185 lines) is a generated artifact in git for two
  research prompts that are both answered. Allowed by `CLAUDE.md`; worth asking whether anything
  still reads it.
- Operational scripts (`collect_line_timing.*`, `pt_rollover.py`) live under `research/` while
  their runbook lives in root `docs/`. Acceptable — but the scheduled task points at the
  research path, so a future move breaks collection silently. Note, do not move.
- Leftovers: `processed/weekly_slate_2026w2.csv` (hand-named, superseded by the stamped files);
  `pt_model_season_stability.csv` (orphan, already flagged in README).

## 5. Order of work — all done 2026-09-08

1. Decontaminated rerun of `eval_line_movement.py` (§1.1). Ten minutes; decides how the tree
   describes itself.
2. Fix the scheduled task conditions (§2). Five minutes in the UI; every missed slot is gone.
3. Write `eval_version_b.py` and amend B4's stopping rule to one the sample can decide (§1.2–1.3).
4. PT-line-vs-AN-close check (§1.4); retire the `compare_lines.py` row or move the script.
5. `tests/test_spread_estimators.py` (§3).
6. Doc hygiene: one home for the headline numbers, `raw/` → `ingest/`, session guide dated (§4).

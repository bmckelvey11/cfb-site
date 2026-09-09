# Spread line movement — master plan

**Status:** plan of record, 2026-09-08. Absorbs the documents listed in §9. Execution detail
lives in two appendices — the task steps (`docs/superpowers/plans/2026-09-08-spread-next-steps.md`)
and the parallel dispatch (`build-brief-2026-09-08.md`). This document is the authority on what
is true, what is decided, and in what order it happens.

**What this does not absorb, and must not:** `prereg-line-movement.md` and
`prereg-line-shopping.md` are **binding pre-registrations whose evidential value comes from
their commit order**. Folding them into a later document would destroy the thing that makes them
evidence. `line-movement-results.md` and `line-shopping-results.md` remain the single home for
every number, per the audit's own finding that headline figures had spread across five files.
This master points at all four; it never restates their numbers as though it were their source.

---

## 1. The question, and the one number that answers it

The Prediction Tracker panel does not out-forecast the market on game margin — that question is
closed and archived (Harvey–Newbold p = 0.56, 50.3% ATS). Retargeted at **where the line goes**,
it does something: on the archive, the screened consensus anticipates roughly 15% of the
open→close move.

But the archive measures that at the **opener**, a price PT's timing cannot reach — week 1 of
2026 showed the opener is months gone by game week. So the whole tree reduces to one question:

> **Is any of that move still available at the first Monday snapshot of the week?**

That is version B. Everything else here exists to make its answer trustworthy.

## 2. Where the evidence actually stands (measured 2026-09-08)

**Archive, decontaminated. Amendment A6 (walk-forward) is the citable screen**; A3
(full-sample) is retained as run. Dropping the top decile of models by
`ρ_i = corr(f_i − open, close − open)` — 15 of 152 under A3, including three of the margin era's
"best forecasters", which is itself the finding:

| method | R² full panel | A3 full-sample screen | **A6 walk-forward screen** | A6 retention |
|---|---|---|---|---|
| **E4** screened consensus | 0.170 | 0.153 | **0.154** | **90.7%** |
| E6 ridge | 0.248 | 0.163 | **0.201** | 81.1% |
| E7 | 0.147 | 0.133 | 0.132 | 90.0% |
| E14 screened CSR | 0.136 | 0.107 | 0.113 | 82.9% |

E4's γ under A6: median **0.283**, range 0.182–0.323, positive in 20 of 20 seasons.

A6 builds the drop list for evaluation season *s* from seasons < *s* only, so it never sees its
own test set and A3's conditionality is discharged. The two final-season drop lists overlap 14 of
15 (A6 keeps `linedokter`). Across all 20 seasons A6's union is 33 models — early seasons flag
more, because with 5–13 years of history a ρ estimate is noisier. `--decontaminate` still
reproduces A3 byte-for-byte, so the recorded A3 result stands as run.

**A6 changed a number this plan leaned on, and it does not change the decision.** Under A3, E6
retained 66% against E4's 90% — the basis for calling E6 "the bigger loser to decontamination".
Under the honest screen E6 retains 81.1%, and its absolute R² (0.201) is **higher** than E4's
(0.154), closer to the full-panel ordering. E4 is still the more robust by retention, but the gap
is narrower than stated and E6 scores better. **The graded predictor stays E4 anyway** — see
decision 2.

**What the archive's "close" actually is.** PT's `line` is a late line, not the close: on **1,440**
matched 2024–25 games, mean |Δ| **0.69**, exact on 31.7%, within 0.5 on 66.9%. (An earlier
reading of this document said 1,219 — the same measurement on a smaller Action Network table.
The matching logic is unchanged and the merge loses no rows; the table grew.)

**A5 — is any of that residual move predictable?** No. Regressing `AN_close − PT_line` on each
predictor's deviation from PT's `line`, walk-forward predictions, season-week clusters, CIs
conditional on the fitted predictor: E4 **−0.033** [−0.059, −0.007], E6 −0.022 [−0.049, +0.006],
E14 −0.027 [−0.051, −0.003], n = 1,440 over 31 clusters. The pre-registered expectation was
0.0–0.10 with a CI including zero, and ≥ 0.2 excluding zero would have been evidence of unpriced
information; the result misses on sign and is an order of magnitude short. A one-SD disagreement
(sd ≈ 1.79) predicts a −0.06 shift against a mean residual move of 0.69. This was the only
evidence the archive could produce that the panel *leads* rather than *reports* — it does not
produce it, and it is too small to be read as a substantive negative either.

**Version B, live.** `data/processed/version_b.json`, 8 snapshots / 350 forward-log rows:

| | E4 | E6 | model median |
|---|---|---|---|
| slope | 0.202 | 0.434 | 0.182 |
| 95% CI | [0.004, 0.401] | [0.171, 0.697] | [−0.030, 0.393] |
| n graded | 42 | 42 | 42 |
| **week clusters** | **1** | **1** | **1** |
| SE kind | **HC1** | HC1 | HC1 |

**No verdict.** One cluster is not clustered inference, and the `n_for_mde_0.2 = 80` the grader
prints is derived from that same un-clustered SE — it is informational, not a target. E4 is the
registered predictor; E6 and the median are shown beside it with no selection among them.

## 3. The stopping rule, stated once

> No verdict before season end; at season end, confirmatory inference requires ≥ 8 week
> clusters, and with fewer the read is reported as inconclusive.

The observed MDE is reported at every read and triggers nothing. **Nothing in any spread
document may state this rule differently.** It replaced two earlier formulations: the original
B4 rule ("slope under 0.1 with a CI excluding 0.2 at ~300 games"), which the sample cannot
decide, and amendment B1's MDE gate, which made the stopping time depend on the data.

## 4. Decisions

1. **One confirmatory family: the version B E4 slope at the Monday anchor.** Everything
   archive-side (A1–A6) and all line-shopping work is **exploratory** and its sections say so.
   Holm applies within a family; no across-family correction is attempted, because with one
   confirmatory hypothesis none is needed. This replaced an earlier proposal to merely log the
   amendments — a ledger documents forks without controlling them.
2. **E4 is graded, not E6**, though E6 scores higher — on the full panel *and*, since A6, under
   the honest screen (0.201 vs 0.154). E4 remains the more robust by retention (90.7% vs 81.1%),
   but that case is weaker than it looked under A3's 66%. **This is exactly why it was fixed
   before data.** Prereg B1 registered E4 as the graded predictor and placed E6 and the model
   median beside it *with no selection among them*. Switching now, on a result seen after the
   fact, is the selection-on-outcome this tree exists to prevent. If E6 is genuinely the better
   predictor, the way to establish that is a new pre-registration and a forward test, not a
   substitution.
3. **The version B predictor set is frozen for the season.** `MODEL_COLS` and `PARAMS` in
   `weekly_slate.py` define `pred_close`; changing them mid-forward-test silently redefines the
   graded quantity. Any change is versioned (`model_set_version`) and existing forward-log rows
   are recomputed before a read quotes `pred_close`.
4. **A4's output is an engineering decision, not an inferential claim.** It chooses which λ
   `weekly_slate.py` serves. It does not license "the ridge works", carries no p-value, and is
   labelled exploratory. **A4 has run:** its pre-registered rule (retire E6 if it clears E4 by
   ≤ 0.02) did not fire — 0.2002 against 0.1537 — so E6 is kept, now served at **λ = 5e4**, with
   the model set versioned to 2 and all 350 forward-log rows recomputed. See risk 3: the grid
   edge did not resolve, it moved.
5. **The `3.2` win-rate-per-point constant is kept for line shopping, and stays retired for the
   movement CLV claim** (settled by the user, 2026-09-08). It was estimated on the line-shopping
   sample itself, so it is the in-sample conversion for that sample; the audit's §1.5 objection
   was to the "3–5× the bar" phrasing on movement bets, which sit on larger spreads where a
   point is worth less. Two uses of one number; only one was wrong. The S1 results section must
   carry the in-sample caveat.
6. **Version B's target is the Action Network consensus close** (book 15, last full-game tick
   before kickoff), not PT's `line` — see §2 for why.
7. **Weekly reads are reported but decide nothing**, now enforced by §3's rule rather than
   asserted.

## 5. What must change before the affected work runs

The audit's own findings were resolved on 2026-09-08 (decontamination run, scheduled task fixed,
grader written, PT-line check measured, estimator tests added, docs de-duplicated). The items
below were added by a later adversarial review. **All of them landed on 2026-09-08** across waves
0–2 of `build-brief-2026-09-08.md`; they are kept here as the record of what the review required.

**Pre-registration** (`prereg-line-movement.md` — appended to, never rewritten):

- An **amendment ledger**: every amendment (A2, A3, B1, and the queued A4, A5, B2) with what it
  changed, what motivated it, and whether that motivation was data-driven. A4's was — the grid
  edge was seen first.
- The **confirmatory/exploratory split** of decision 1, and §3's rule replacing B1's MDE gate.
- The **MDE computed from the cluster SE**, not the iid `σ_resid/(σ_x√n)` arithmetic, which
  understates what a clustered design needs.
- **Amendment A6** — the walk-forward decontamination screen, registered before it is run.
  Expectation on record: the walk-forward drop list overlaps the full-sample one substantially
  and E4's retention stays within a few points of 90%.

**Task steps** (the appendix): A4 labelled exploratory with the versioned model set; B2 taking
one capture per game per bucket on a fixed game set; the health check gating the *grade* rather
than the pull; the two undefined decision branches filled (T4's 10–14 publish count; T11's
slope-under-0.10-with-a-wide-CI case, which §3's rule makes the *likely* outcome); T10 relabelled
as blocked on an external dependency; T9's `3.2` resolution recorded; and four estimator tests —
`holm`, `pick_1se`, null p-value uniformity, and the walk-forward drop-list test.

## 6. Execution

Nine agents across four waves, dispatched per `build-brief-2026-09-08.md`. The wave structure
exists because three documents are wanted by nearly every task — the pre-registration, the task
steps, and `line-movement-results.md` — and parallel writers on those produce conflicts, or worse,
a model fitted against a half-written pre-registration.

| Wave | Who | What |
|---|---|---|
| **0** | one agent, blocks everything | Every contract edit in §5. Nothing may be fitted until it lands, because expectation text is committed *before* the run that tests it. |
| **1** | seven agents, parallel, disjoint files | **A** walk-forward decontamination screen (A6) · **B** version B inference (cluster-SE MDE, B2 buckets) · **C** collector health + Monday chain · **D** model publication times · **E** estimator tests · **F** hygiene · **I** line shopping (S1) |
| **2** | two agents | **G** amendment A4 on the walk-forward panel, and whether E6 keeps its place · **H** amendment A5 |
| **3** | one agent, alone | Every results section, from the JSON the earlier waves produced. Single writer on `line-movement-results.md`, the README and `CLAUDE.md`. |

**Agent A is the wave's priority.** A4 must run on the walk-forward panel or it bakes the
full-sample screen into a serving decision.

**Not in this build:** T10 (needs an Action Network scoreboard re-scrape owned by
`cfb_system_maker`) and T1 (a vendor backfill plus observing that a scheduled task fired on its
own — a fact about the machine, not the repo, and the last thing standing between the collector
fix being *claimed* and *verified*).

## 7. Risks and open questions

1. **The amendment stack against the prereg's own stopping rule.** The prereg says "one run of A;
   no interim looks; no re-thresholding". Since then: A2, A3, B1, with A4, A5, A6, B2 and S1
   queued. Each is honestly pre-registered before its own run — the right pattern — but the count
   is itself the forking-paths risk the pre-registration existed to prevent. Decision 1 is the
   control; the ledger is the record.
2. **A3's screen saw its own test set** — **closed 2026-09-08.** Amendment A6 rebuilt the screen
   walk-forward; A6 is now the citable screen and A3 is retained as run. It also reversed a
   framing this plan carried: E6 retains 81.1%, not 66%, and outscores E4 (see §2).
3. **A4 is post-hoc grid selection** — the data chose the grid. Bounded by decision 4, and the
   rule was applied as written rather than overridden after the fact. **But A4 did not resolve
   what it was run to resolve.** λ = 5e4 was chosen in 19 of 19 seasons that produced a choice,
   and 5e4 is the *new* grid's top edge — the old edge was 1e4, so widening moved the edge
   instead of finding an interior optimum. A ridge whose shrinkage parameter runs to whatever
   bound it is given is not well identified, and E6 is now served at such a bound. The honest
   next step is a fresh pre-registration — a wider or unbounded grid, or a different estimator —
   not another quiet widening, and not an override of a rule that was fixed before the run.
4. **A5 treats a walk-forward prediction as a fixed regressor**; its CI is conditional on the
   fitted predictor and must be labelled so.
5. **The collector fix is claimed, not verified.** The Task Scheduler conditions live in the UI,
   not in git, and T1's confirmation step is still unchecked. Enough 6-hour slots have now passed
   that `LastTaskResult` can simply be read.
6. **`archive/spread-margin-era/scripts/diag_weight_concentration.py:46`** still carries a
   hardcoded `C:/Users/mckel/data/cfb/processed` fallback. Archived and `hasattr`-guarded, so it
   is a note, not a defect.
7. **Three targets have now been tried on one panel** (margin vs close, margin vs open, close vs
   open). The audit deferred across-target multiplicity as low priority conditional on A3
   surviving decontamination, which it did — recorded here so it stops reading as an open item.

## 8. Out of scope

- New models, new data sources, new targets.
- Re-opening the margin era. `archive/spread-margin-era/` is audit history and is never cited as
  current; its nulls were about a different question and do not gate movement methods.
- Alpha-spending machinery for the weekly reads — §3's fixed checkpoint removes the sequential
  test rather than correcting for it.
- Per-fitter unit tests for E6–E14; they are exercised end to end by the registered runs.
- Scraping PT's constituent models directly. A downstream tree, opened only if the publication-time
  work shows the leading forecasters post before PT compiles **and** version B lands in the
  bettable branch.

## 9. Document map

**Absorbed into this document** (each bannered, retained as audit history):

| Document | Carried forward |
|---|---|
| `plan-2026-09-08-hardened.md` | Goal, decisions, assumptions, the risk register, the required amendments |
| `plan-review-log-2026-09-08.md` | What the three adversarial rounds settled, and the post-loop `3.2` resolution |
| `review-2026-09-08-tree-audit.md` | Its open items; its resolved findings stay there as the record of what was fixed and when |

**Live appendices — the authority on *how*:**

- `docs/superpowers/plans/2026-09-08-spread-next-steps.md` — task steps, code, expected output.
- `build-brief-2026-09-08.md` — wave structure, per-agent file ownership, acceptance checks.

Where an appendix disagrees with this document, this document wins and the appendix is corrected.

**Binding, never absorbed:** `prereg-line-movement.md`, `prereg-line-shopping.md` — appended to
in commit order, never rewritten.

**Single home for numbers, never restated here as source:** `line-movement-results.md`,
`line-shopping-results.md`.

**Still authoritative in their own right:** `README.md` (the tree's index — start there),
`prediction-tracker.md` (column dictionary), `combining-predictions.md` (how E4 and the book fair
combine). **Dated records:** `review-2026-09-02-composite-spread.md`,
`session-guide-2026-09-02.md`.

## 10. Constraints

- `CFB_DATA_ROOT` is required; data is never committed.
- **No lookahead.** A version B predictor may use only the snapshot it is anchored on and the
  archive fit; the close and the score enter as grading targets only.
- **Pre-registration order is not negotiable:** expectation text is committed *before* the run
  that tests it. One run per amendment.
- **Sign convention:** PT publishes positive = home favoured; the archive is negated. Live
  snapshots pass through `predict_upcoming.to_archive_convention` before touching fitted code.
  Check a number you know before trusting a table.
- Results land in `line-movement-results.md`; `README.md` and `CLAUDE.md` point, never restate.
- Run commands from the repository root. Default verification: `python -m pytest`.

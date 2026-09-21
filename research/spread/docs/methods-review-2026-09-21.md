# Methods review — the pred-tracker-model and its version B forward test, 2026-09-21

**Question.** Are the methods the pred-tracker-model is served and graded by sound enough that
the version B read, when it fires at season end, will mean what the pre-registration says it
means?

**Method.** The econometrics audit checklist (leakage, specification, dependence, power,
multiplicity, shrinkage, estimated regressors, selection, identification, stability, scoring)
walked against `weekly_slate.py`, `eval_version_b.py`, `prereg-line-movement.md` and its
amendment ledger, plus the repo's governing
[`docs/model-evaluation-standard.md`](../../../docs/model-evaluation-standard.md). Depth: **full
audit** on the live serving and version B paths; the archive era (A1–A7) is **not** re-audited —
`review-2026-09-08-tree-audit.md` did that and its findings carry their own resolution dates.

**Data.** `movement_forward_log.csv` as of the 2026-09-21T16:30:05Z snapshot: 19 snapshots,
205 Monday-anchored games, **147 graded** against an Action Network close, spanning **3 week
clusters** (2026-08-31, 2026-09-07, 2026-09-14). Archive: 2001–2025, 17,731 games.

**Reproduce.** [`research/spread/scripts/audit_version_b_methods.py`](../scripts/audit_version_b_methods.py)
prints every number below that `eval_version_b.py` does not. Read-only; grades nothing.

**No verdict is issued here.** Amendment B3's stopping rule stands: no verdict before season
end, and at season end confirmatory inference needs ≥ 8 week clusters. This review is about
the instrument, not the reading.

---

## Verdict

**Sound as registered, with two findings that change how the season-end read must be
interpreted and one statistic that is being misread today.**

The pipeline is unusually disciplined: the grader was committed before any in-season close
existed, the anchor/close/score/predictor definitions were fixed in advance, the stopping rule
is data-independent and enforced in code, the confirmatory family is declared as exactly one
hypothesis, and the amendment ledger labels its own data-driven entries. The checks that most
often sink work like this — leakage, selection, a data-dependent stopping time — all pass.

What is not sound is the assumption that the realized sample matches the registered design.
It does not, in two ways (F1, F2), and neither can be fixed by amendment without forfeiting
the confirmatory claim.

---

## F1 — [CAVEAT] The graded "Monday line" is a Tuesday line for 62% of games

**What.** `monday_anchor()` takes the earliest capture at or after Monday 00:00 ET, which is
faithful to amendment B1's wording. But the collector has not been capturing on Mondays for
most of the sample, so the rule resolves to whatever came next:

| week | n | median hours after Monday 00:00 ET | share anchored on a true Monday capture |
|---|---|---|---|
| 2026-08-31 | 42 | 42.5 | 0% |
| 2026-09-07 | 49 | 39.2 | 0% |
| 2026-09-14 | 56 | 18.5 | 100% |

Overall 56 Monday captures against 91 Tuesday captures — **38.1%**. Weeks 1–2 contain no Monday
anchor at all.

**Why it bites here.** B5 describes its trade as "a Monday bet." Two thirds of the graded bets
were struck at a Tuesday-afternoon price, after a day of additional market movement, which is
the exact axis the whole tree is measuring. This is **heterogeneity, not bias** — with three
weeks and the regimes perfectly confounded with week, the direction cannot be signed. The
consequence that matters is downstream: the season-end pool of ≥ 8 clusters will mix two anchor
regimes under one registered label, and B1's definitions are binding, so no amendment can
retroactively split them.

**Resolves with.** Nothing to compute — the table above *is* the remediation, recorded now so
the season-end read can condition on it. The forward-looking fix is operational: if the
collector runs Mondays from here, the regime stabilises and the mix is at least known per week.

## F2 — [CAVEAT] B4's registered regressor spends 3× its variance on a component that carries nothing

**What.** E4 is anchored on the opener, so its version B regressor decomposes exactly:

```
x = E4 - line_anchor = (open_pt - line_anchor) + (E4 - open_pt)
                       \____ R: revert ____/     \____ C: panel ____/
```

On the 147 graded games, `corr(x, -(line_anchor - open_pt)) = +0.844`, **R² = 0.713** — 71% of
the regressor's variance is the market's own move since the opener, reversed. `sd(R) = 1.42`
against `sd(C) = 0.82`. This is the mechanism `actionable-picks-2026-09-17.md` §0 established on
a single slate (corr −0.908 there); it is confirmed here on the graded forward log at the
Monday anchor.

Regressing `y` on the two parts separately (**exploratory**, HC1 fallback, 3 clusters — these
intervals are optimistic and are not cluster evidence):

| regressor | slope | 95% CI |
|---|---|---|
| x (B4's registered estimate) | −0.000 | [−0.094, +0.093] |
| R: open_pt − line_anchor | −0.023 | [−0.121, +0.075] |
| C: consensus deviation | +0.088 | [−0.073, +0.250] |
| C alone | +0.096 | [−0.061, +0.252] |

**Why it bites here.** B4's −0.000 is a variance-weighted blend of a null component and a
component whose point estimate is positive. The registered estimate therefore answers *"does
E4-as-served predict the move from the anchor"* — which is the right question for a bet — but
**not** *"does the panel carry information the market has not priced"*. Against the second
question it has materially less power than n = 147 suggests, because most of the leverage sits
in R. Reading a season-end null on x as evidence against the panel would be reading the wrong
hypothesis.

**Resolves with.** Nothing, deliberately. Amending B4's regressor would be motivated by seeing
this decomposition, and the amendment ledger's own rule bars a data-driven amendment from
carrying the confirmatory claim. B4 stands as registered; the decomposition is reported beside
it as a diagnostic, the same way A5 was.

## F3 — [CAVEAT] `beat_close` counts a line that never moved as a loss

**What.** B5 computes `beat_close = mean(side * y > 0)`. **52 of 147 graded games (35.4%)** have
`close == line_anchor` exactly — the line never moved. Those fall into the `> 0` complement:

| statistic | value |
|---|---|
| beat close, as coded | 33.3% |
| lost to the close (`side*y < 0`) | 29.3% |
| tied (`y == 0`) | 35.4% |
| beat close **among games that moved** | 51.6% (n = 95) |

**Why it bites here.** The printed 33.3% / 23.1% figures read as a catastrophic win rate against
a 50% reference, and were reported that way in conversation before this review. They are not a
win rate. The honest summary is that among lines that moved at all, the E4 side lands at a
coin flip. CLV is **unaffected** — ties contribute exactly 0 to the mean — so `CLV +0.09
[−0.14, +0.32]` stands as printed and remains the interpretable statistic.

**Resolves with.** A printing change in `eval_version_b.py`: emit the three-way split
(beat / tie / lost) plus the moved-only rate, rather than one percentage against an implied 50%.
No registered quantity changes. Offered, not applied.

## F4 — [NOTE] B2's capture-decay estimate currently covers one week

**What.** The fixed game set keeps only games present in all four buckets: **56 distinct games,
all from 2026-09-14**, with 91 dropped. All four bucket slopes are therefore one cluster, HC1,
on an identical game set — four views of the same 56 games, not four independent estimates.

**Why it bites here.** B2 is the instrument designed to measure exactly the anchor-timing
sensitivity that F1 raises. It cannot do that yet. This is a **coverage** finding, not a defect:
the fixed-game-set rule is the correct design and is what forces the honest n.

**Resolves with.** Time. Weeks 1–2 have no `mon` bucket (F1), so they can never enter the fixed
set; coverage grows only from week 3 forward.

## F5 — [NOTE] Checks that pass, recorded so they are not re-litigated

- **Leakage — clean.** `weekly_slate.build` fits on `base.load()` (2001–2025, 17,731 games) and
  passes `upto = 2025` to `prior_skill`. **Zero 2026 rows in the archive**, so neither the
  top-20 screen nor the γ fit sees any game in the forward log. The live snapshot is a separate
  file. The repo standard treats leakage as invalidating; there is none on this path.
- **Selection — clean.** 205 anchored, 147 played, **147 graded, 0 played games ungraded**. No
  missingness to model.
- **Stopping rule — data-independent and enforced.** `apply_stopping_rule` reads only
  `season_ended` and the cluster count, never the MDE; the MDE is stamped
  `informational_hc1_fallback` while under `MIN_WEEKS`. B3 replaced B1's MDE gate precisely
  because the latter was a data-dependent stopping time.
- **Dependence — handled, and honest about the fallback.** Season-week clusters throughout,
  with an explicit HC1 fallback below 5 clusters, labelled at every print site.
- **Multiplicity — declared.** One confirmatory hypothesis (the version B E4 slope); E6 and
  `pred_close` reported beside it with no selection; everything archive-side labelled
  exploratory.
- **Definition drift — checked.** The 2026-09-21 run emitted neither the `model_set_version` nor
  the `edge_def_version` warning, so all 147 graded rows share one model-set and one
  edge/side definition and are poolable.

## F6 — [NOTE] The registered power arithmetic was off by 3.3×

**What.** Amendment B1 assumed `σ_x ≈ 0.45` from the week-2 snapshots and derived that B4's
thresholds would need n ≈ 1,000–1,200. Realized `sd(x) = 1.50`.

**Why it bites here.** It does not bite the inference — B3 already severed the verdict from any
computed MDE, which is exactly the protection that makes a mis-specified power calculation
harmless. It is recorded because the larger σ_x comes from stale early-season openers (F2's R
component), so it is a symptom of F2 rather than good news about power: the extra variance is
in the component that carries no signal.

---

## What this review does not support

- It issues **no version B verdict** and moves no threshold. Three clusters, stopping rule in
  force, every interval above is an HC1 fallback.
- It does **not** re-audit the archive era (A1–A7). Those results and their caveats stand as
  `line-movement-results.md` and `review-2026-09-08-tree-audit.md` record them; no number from
  either is restated here.
- The F2 decomposition is **exploratory**. A positive point estimate on C with a CI spanning
  zero, on 147 games and 3 clusters, is not evidence the panel carries information. It is a
  reason not to read a null on x as evidence that it does not.
- Nothing here says the slate is bettable. `actionable-picks-2026-09-17.md` answers that, and
  the answer is still no.

## Open, for whoever reads next

1. Does the collector now run Mondays? F1's regime mix is the one thing that can still be
   improved before season end, and only operationally.
2. The `beat_close` printing fix (F3) — a contained change to `eval_version_b.py` that touches
   no registered quantity.

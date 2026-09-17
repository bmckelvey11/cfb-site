# What a day of testing The Prediction Tracker found — 2026-09-17

Entry point for the five studies run on 2026-09-17. **Every number lives in the study it belongs
to**; this file connects them and does not restate anything it does not own.

## The one-line answer

The pred-tracker-model's slate is not bettable, and the reason is the same everywhere it was
looked for: **the vendor panel's disagreement with the market is not information about the
market.** Five routes, two datasets, three estimands, one conclusion.

## The studies

| # | Study | Question | Answer | Standing |
|---|---|---|---|---|
| 1 | [`actionable-picks`](actionable-picks-2026-09-17.md) § 0 | What is the served `edge` column actually made of? | The market's own move since the opener, sign-flipped | **Decisive** |
| 2 | [`actionable-picks`](actionable-picks-2026-09-17.md) § 1–3 | Is there room to bet at the version B anchor? | ~0.7 pts of move exists in total; oracle ceiling below a CLV that already failed | **Decisive** |
| 3 | [`phcover-accuracy`](phcover-accuracy-2026-09-17.md) | Is PT's P(home covers) any good? | No usable signal, and worse than a constant | **Clean null** |
| 4 | [`linestd-confidence`](linestd-confidence-2026-09-17.md) | Is panel dispersion a confidence weight? | A real trend, far too small to reach the vig | **Clean** |
| 5 | [`phwin-accuracy`](phwin-accuracy-2026-09-17.md) | Is PT's P(home wins) any good? | A real forecast; loses to the line head-to-head | **Head-to-head clean; encompassing inconclusive** |
| 6 | [`model-columns-ats`](model-columns-ats-2026-09-17.md) | Does any of the ~150 models beat the close ATS? | Walk-forward selection lands on a coin flip | **Clean on walk-forward; 36 of 109 models unresolved** |

## The mechanism the studies share

Studies 1, 3, 4 and 6 are four measurements of the same object from different angles.

`weekly_slate.py` computes `edge` as E4 minus the **current** book fair, but E4 is fit anchored
on the **opener** and barely leaves it. So the served edge reproduces the move the market already
made, with the sign flipped — a retrace-to-opener trade (§ 0 of study 1). That inverts what
amendment A6 actually established, which is a momentum result measured *at* the opener, before
the move happens.

Study 6's baseline measures the same trade directly on 23 seasons of realized outcomes and finds
it losing. Study 3 finds that `phcover` is a squashed transform of that same panel-vs-market
disagreement and carries no ranking ability. Study 4 finds that weighting the trade by panel
agreement cannot lift it to break-even even extrapolated past the floor of the data.

Study 5 is the exception that clarifies the rule: `phwin` encodes the panel's **level**, not its
disagreement, and it is a genuinely good forecast — just not better than the line it sits beside.

## What is still open

1. **Version B has not returned a verdict and cannot yet.** Amendment B3 is binding: 2 week
   clusters of the 8 required, season live. Study 2 bounds what a verdict could be worth at the
   served anchor; it does not pre-empt it.
2. **`phwin`'s independent component.** Only 25% of its variation survives removing the line, and
   the encompassing test's MDE is 0.300 against a CI of [−0.05, +0.38]. A modest contribution is
   not excluded at this sample size.
3. **36 of 109 model columns** have a confidence interval whose upper bound clears break-even.
   None is demonstrably good; they are not demonstrably bad either.
4. **The 43 columns below the coverage screen** were never scored.
5. **The Monday anchor.** Both graded weeks anchored Tuesday. Week 1's Monday snapshot is on disk
   and replayable; week 3 already has one logged.

## What none of this establishes

- **Not that E4 or amendment A6 is wrong.** E4 fit at the opener is the registered object and its
  archive result stands. The defect found in study 1 is in reading its output against a later
  price, which is what the served `edge` column does.
- **Not a verdict on version B**, in either direction.
- **Not that PT is worthless.** It carries real information about margins — study 6 § 0 shows the
  model columns are not rescalings of the line, and study 5 shows `phwin` is a real forecast. The
  finding is that none of it survives contact with the closing line's *price*.

## One decision this raises

The `edge` and `side` columns `weekly_slate.py` writes are the same columns version B's forward
log records as its bet set. If § 0 of study 1 is right that those columns encode a retrace trade
rather than the momentum trade the prereg describes, then **the registered forward test is
grading a different trade than the one A6 motivated**. Whether that is an amendment or a code fix
should be settled before the remaining six week clusters accumulate under it.

## Reproduction

```bash
python research/spread/scripts/edge_vs_market_move.py        # study 1
python research/spread/scripts/version_b_ceiling.py          # study 2
python research/spread/scripts/eval_phcover_calibration.py   # study 3
python research/spread/scripts/eval_linestd_confidence.py    # study 4
python research/spread/scripts/eval_phwin_accuracy.py        # study 5
python research/spread/scripts/eval_model_columns_ats.py     # study 6
```

All six print a power block stating what the test could have detected. Added after a reader
pointed out that `phwin`'s encompassing null was being read as a proven null when the test was
underpowered by construction — the same check was then applied to every study, and it changed
study 4's stated conclusion.

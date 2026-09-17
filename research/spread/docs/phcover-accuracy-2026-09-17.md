# How accurate is PT's `phcover`? — 2026-09-17

**EXPLORATORY.** Not registered in `prereg-line-movement.md`. This is an unregistered question
about a column The Prediction Tracker publishes, not a version A or B read, and no verdict
follows from it.

## Question

PT ships `phcover` — its stated probability that the home team covers — in every snapshot from
2017 on. Does it carry usable information?

## Answer: no. It is a restatement of the panel's disagreement with the market, and it does not rank covers.

Three findings, in the order that decides it.

### 1. `phcover` is not independent information

Regressing `phcover` on what is already in the panel:

| regressor | R² |
|---|---|
| `line` | 0.054 |
| `lineavg` | 0.000 |
| **`lineavg − line`** | **0.9945** |
| all three | 0.9945 |

`phcover` is a squashed monotone transform of **the model average minus the market line** — the
same panel-versus-market disagreement that `actionable-picks-2026-09-17.md` § 0 decomposes.
Testing `phcover` is therefore testing that object through a different link function, not
testing a second opinion.

### 2. It does not discriminate

AUC against the realized cover indicator, season-cluster bootstrap CI:

| | value |
|---|---|
| AUC | **0.4888** [0.4753, 0.5028] |
| seasons with AUC > 0.500 | **2 of 9** |
| `phcover` sd | 0.0767 (IQR 0.098) |

0.500 is no ability to rank. The interval contains 0.500, so `phcover` is not *significantly*
backwards — it is simply uninformative. Per season it lands above 0.500 twice in nine tries
(2019, 2025); the worst is 2024 at 0.455.

### 3. It is worse-calibrated than a constant

| | value |
|---|---|
| Brier | 0.25754 |
| Brier of the constant base rate (0.4951) | 0.24998 |
| **Brier skill score** | **−0.0303** [−0.0389, −0.0209] |

A negative skill score means always answering "49.5%" forecasts better than `phcover` does. The
season-cluster interval excludes zero, so this is not a wash — `phcover` is *significantly*
worse than a constant.

Deciles of `phcover` against realized cover rate:

| decile | n | mean `phcover` | realized cover |
|---|---|---|---|
| 1 | 667 | 0.366 | **0.525** |
| 2 | 667 | 0.426 | 0.486 |
| 3 | 667 | 0.454 | 0.498 |
| 4 | 667 | 0.475 | 0.493 |
| 5 | 667 | 0.494 | 0.523 |
| 6 | 666 | 0.513 | 0.467 |
| 7 | 667 | 0.532 | 0.510 |
| 8 | 667 | 0.552 | 0.477 |
| 9 | 667 | 0.580 | 0.504 |
| 10 | 667 | 0.636 | **0.469** |

The table leans backwards — the decile PT is most confident about covers least often. But the
top-versus-bottom gap is **+0.0555 [−0.0083, +0.1157]** on season clusters, an interval
containing zero. **The inversion is not established.** Read this table as noise around a flat
line, not as a fade signal.

### The bet that does not exist

Betting the top decile's home side: 667 bets, **0.4693** ATS against the 0.5238 break-even at
−110. Fading it — betting the bottom decile's home side: 667 bets, **0.5247** ATS, which is
0.0009 above break-even. Even the best-looking slice of a 6,669-game sample lands exactly on
the vig.

### 4. What these tests could have detected

A confidence interval containing the null only means something alongside the effect the test
could have resolved. Added 2026-09-17, after the same question was raised about the companion
`phwin` study.

| test | SE | MDE at 80% power | observed | reading |
|---|---|---|---|---|
| AUC vs 0.500 | 0.0070 | **0.0196** | 0.4888 | a true AUC of **0.520 or better would have been seen**. Real discrimination at that level is **excluded**. |
| decile gap (bottom − top) | 0.0343 | **0.0961** | +0.0555 | observed gap is **below** the MDE. The inversion is **unresolved**, not shown to be absent. |

So the two headline reads have different standing, and the doc should not have presented them
in the same voice:

- **The AUC null is informative.** 6,669 games over 9 season clusters is enough to exclude any
  discrimination worth acting on. Combined with the Brier interval above, "`phcover` carries no
  usable signal" is supported.
- **The decile-inversion null is not.** § 3 already said the inversion "is not established", and
  that remains the right wording — but the reason is that the test cannot resolve a gap this
  size, not that the gap was shown to be zero.

**On the collinearity objection** that applies to the `phwin` study: `phcover` is 0.9945
explained by `lineavg − line`, and its sd of 0.0767 collapses to a **0.0057** residual once that
is removed. So any test *conditioning on the market* would have essentially nothing to work
with. That objection does not bite here, because the AUC and Brier reads above are
**unconditional** — `phcover` is scored directly against realized covers, with no regression on
the line. They stand on their own.

## What this does not support

- **Not a claim that `phcover` is systematically backwards.** Both the AUC interval and the
  decile-gap interval contain the null, and per § 4 the decile test could not have resolved an
  inversion of the observed size anyway. The finding is absence of *usable* signal, not reversed
  signal.
- **Not a claim about PT's other columns.** `phwin`, `lineavg`, `linestd` and the ~50 model
  columns are untested here.
- **Not a version A or B read**, and it changes nothing about amendment B3's stopping rule.
- **Not a reason to drop `phcover` from ingest.** It costs nothing to keep and is now
  characterized.

A calibrated `phcover` would still not have been a bet: the bar is 52.38%, and calibration
around 0.50 clears nothing.

## Method

Data: `data/ingest/prediction_tracker_lines.csv`, the joined panel, seasons 2017–2025 —
6,796 games carrying `phcover`, of which **127 are pushes** (dropped: a push is not a binary
outcome), leaving **6,669 graded**. Base cover rate 0.4951.

Loading, the margin orientation and the season-cluster bootstrap come from
`eval_prediction_tracker_models.py` (`base.load()` keeps `match_status == 'matched'` only and
flips the margin on the 132 rows where CFBD's home differs from PT's home). Cover is scored on
the panel's own `line` in the archive's negated sign: home covers iff `y + line > 0`.

```bash
python research/spread/scripts/eval_phcover_calibration.py
```

Writes `data/processed/phcover_calibration.json`.

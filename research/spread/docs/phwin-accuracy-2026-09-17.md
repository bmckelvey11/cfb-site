# How accurate is PT's `phwin`? — 2026-09-17

**EXPLORATORY.** Not registered in `prereg-line-movement.md`. Third of the PT-column studies,
after `phcover-accuracy-2026-09-17.md` and `linestd-confidence-2026-09-17.md`. No verdict
follows from it.

## Question

`phwin` is PT's published probability that the home team wins outright. Is it accurate, and does
it beat the market line sitting in the same row?

## Answer: it is a genuinely good forecast — and the market line beats it anyway.

This is **not** the `phcover` result. `phcover` was pinned near 0.50 and carried no signal.
`phwin` is a real forecast with real spread (sd 0.242, range 0.006–0.997) and it works. It is
just dominated by something free.

### 1. What it is

`logit(phwin)` regressed on `lineavg` gives **R² = 0.9974** — `phwin` is the panel's mean
predicted margin pushed through a logistic link. On `line` (the market) the same fit gives
0.9367, and on the panel-vs-market disagreement only 0.0010. So `phwin` encodes the panel's
**level**, where `phcover` encoded its **disagreement**. That is why the two behave nothing alike.

### 2. In absolute terms it is good

| | value |
|---|---|
| AUC | **0.8016** |
| Brier | 0.17876 |
| Brier skill vs the base rate (0.5837) | **+0.264** |

Calibration by decile is close, with a mild **under**-confidence at the tails — the extremes are
more extreme in reality than `phwin` says:

| decile | n | mean `phwin` | realized home win |
|---|---|---|---|
| 1 | 680 | 0.153 | 0.129 |
| 2 | 680 | 0.295 | 0.281 |
| 5 | 679 | 0.553 | 0.541 |
| 9 | 679 | 0.858 | 0.876 |
| 10 | 680 | 0.943 | **0.968** |

### 3. The market line beats it, on both axes

The market is scored by `-line` for AUC, which is rank-based and needs no fitting, and by a
logistic map of home-win on `line` **fit walk-forward on strictly prior seasons** for Brier — so
the market is never handed in-sample information `phwin` did not have.

| | phwin | market | difference | 95% CI (season clusters) |
|---|---|---|---|---|
| AUC | 0.8016 | **0.8106** | −0.0090 | **[−0.0127, −0.0051]** |
| Brier | 0.17876 | **0.17527** | +0.00349 | **[+0.00183, +0.00484]** |

Both intervals exclude zero. `phwin` ranks worse and scores worse than the closing number it is
published beside.

### 4. And the line encompasses it

Head-to-head says which is better; the encompassing regression says whether `phwin` carries
anything the market does not. Logit of home-win on `[line, logit(phwin)]`:

| regressor | coefficient | 95% CI (season clusters) |
|---|---|---|
| `line` | −0.0997 | [−0.1185, −0.0802] |
| `logit(phwin)` | +0.1496 | **[−0.0508, +0.3691]** ← contains 0 |

Given the line, `phwin` adds nothing measurable. The market encompasses it.

## What this does not support

- **Not "phwin is bad."** AUC 0.80 and a +0.26 Brier skill score are a real forecast. Anyone
  without a line would find it useful. The finding is that it is **redundant**, not wrong.
- **Not a moneyline betting result.** The panel carries no moneyline prices, so nothing here is
  an ROI or a break-even test. Losing to the line on Brier and AUC makes a profitable moneyline
  play unlikely, but that was not measured.
- **Not a version A or B read.** Amendment B3's stopping rule is untouched.
- **Not a statement about E4.** `lineavg` is the raw unscreened panel mean; E4 is opener-anchored
  on a screened top-20 consensus.

## Method

Data: `data/ingest/prediction_tracker_lines.csv`, seasons **2017–2025**, 6,796 games carrying
`phwin`. Home wins iff `y > 0`; college football has no ties and the script asserts zero, so
there is no push case. The walk-forward market map scores 6,020 of those (2017 has no prior
season to fit on).

Loading, margin orientation and the season-cluster bootstrap come from
`eval_prediction_tracker_models.py`.

```bash
python research/spread/scripts/eval_phwin_accuracy.py
```

Writes `data/processed/phwin_accuracy.json`.

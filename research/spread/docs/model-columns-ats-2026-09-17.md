# Do PT's individual model columns beat the closing line ATS? — 2026-09-17

**EXPLORATORY.** Not registered in `prereg-line-movement.md`. Fourth of the PT-column studies,
after `phcover`, `linestd` and `phwin`. No verdict follows from it.

**Different estimand from the archive.** Amendments A2 and A6 tested these same columns against
the **movement** target — whether they anticipate where the line goes from the opener. This asks
the question the other three studies asked of PT's summary columns: bet the side a model
disagrees with the **closing** line on, does it clear the −110 break-even. Neither answers the
other, and nothing here re-litigates A2 or A6.

## Question

PT publishes ~150 named model columns. Does any of them, bet against the closing line, make money?

## Answer: none is demonstrably profitable, and picking the best one out-of-sample lands on a coin flip.

The walk-forward read is decisive (§ 1, and § 3 on its power). The per-model leaderboard is
weaker than it first looks: it convicts 73 of 109 and leaves 36 unresolved — see § 3.

### 0. These are not rescalings of the market

Worth establishing first, because it is what separates this sweep from the previous three
studies. R² of each model's prediction on `line`:

| | value |
|---|---|
| median | 0.823 |
| min | 0.310 (`linelog`) |
| models with R² ≥ 0.95 | 3 of 120 |

Unlike `phcover` (0.9945 on `lineavg − line`) and `phwin` (0.9974 on `lineavg`), the individual
models carry real independent variation. The sweep was worth running for that reason.

### 1. Walk-forward — the only read a bettor could have acted on

For each season, rank models by `base.prior_skill` over **strictly prior** seasons, take the
best, bet its side all season. One number, no multiplicity.

| | value |
|---|---|
| bets | 15,311 over 22 seasons (2004–2025) |
| ATS (pooled) | **0.4979** |
| ATS (season mean) | **0.5001** [0.4900, 0.5103] |
| p vs 0.5238 | **< 0.001** |
| seasons above break-even | **1 of 22** |

A dead coin flip, and significantly below the price. The rule settles on `lineespn` for the last
eight seasons and `lineatom` for six before that, so this is not thrashing between models — it
finds a stable pick, and the stable pick does not win.

*Selection is by prior **margin** skill (what `prior_skill` measures); grading is **ATS** against
the close. Stated explicitly because a reader would otherwise assume the two match.*

### 2. In-sample leaderboard — context, not a result

With 109 models the best in-sample number is high by construction. Season-cluster inference,
Benjamini–Hochberg q-values across the whole family:

| model | n | ATS | season mean | 95% CI | q |
|---|---|---|---|---|---|
| `linetsrslots` | 1,067 | 0.5248 | 0.5425 | [0.4579, 0.6271] | 0.460 |
| `linebemiss` | 2,028 | 0.4951 | 0.5376 | [0.4002, 0.6750] | 0.778 |
| `linecrunch` | 2,131 | 0.5237 | 0.5239 | [0.5060, 0.5418] | 0.991 |
| `linepiratings` | 11,003 | 0.5131 | 0.5139 | [0.5017, 0.5262] | 0.138 |
| `linecong` | 16,045 | 0.5093 | 0.5095 | [0.5025, 0.5165] | 0.001 |

The three models whose season mean exceeds 0.5238 are the three with the widest intervals; the
two best-looking have q of 0.46 and 0.78 and fewer than 2,100 games.

| | count |
|---|---|
| models screened | 109 |
| **CI lower bound clearing 0.5238** | **0** |
| CI lower bound clearing 0.5000 | 3 |
| season-mean ATS above 0.5000 | 48 |
| median season-mean ATS | 0.4987 |

**Read the q-values in the right direction.** 79 of 109 models have q < 0.10 — and **all 79 are
significantly *below* break-even, none above.** The test is two-sided against 0.5238, so
"significant" here means reliably losing. `linecong` is the clearest case: 16,045 games,
0.5095 [0.5025, 0.5165], q = 0.001 — a precisely estimated loser.

The distribution across all 109 is centred on a coin flip (mean 0.4984, sd 0.0122, median
0.4987). The models are not systematically wrong; they are systematically not worth −110.

### 3. What these tests could have detected

Added 2026-09-17, alongside the same block in the companion studies. "Zero models clear
break-even" is only half the picture; the other half is how many had the precision for a real
edge to have shown up.

| | count |
|---|---|
| CI lower bound above break-even (**a proven winner**) | **0** of 109 |
| CI entirely below break-even (**an edge excluded**) | **73** of 109 |
| CI upper bound above break-even (**an edge not excluded**) | **36** of 109 |

Median per-model SE is 0.0084, so the median MDE at 80% power is 0.0235 — enough to convict two
thirds of the family and no more. **The sweep does not prove every model is worthless.** It
shows that none is demonstrably good, and that 36 of them remain unresolved at this sample size.

The walk-forward read carries no such caveat:

| | value |
|---|---|
| SE | 0.00518 |
| MDE at 80% power | 0.0145 |
| gap to break-even | +0.0237 = **1.6x the MDE** |

That is the read the answer rests on, and it is well powered.

## What this does not support

- **Not a claim the models are uninformative.** They are not rescalings of the line (§ 0), and
  A2/A6 measured real content against the movement target. This says they do not convert to ATS
  profit against the close.
- **Not a claim that all 109 are unprofitable.** 73 have an edge excluded; **36 do not** (§ 3).
  The decisive result is the walk-forward, not the leaderboard.
- **Not a result about E4.** E4 is opener-anchored on a screened top-20 consensus, fit; these are
  raw single-model columns graded at the close. Different object, different estimand.
- **Not a survivorship-clean statement about the excluded 43 columns.** Models below the screen
  (< 1,000 graded games or < 3 seasons) were never scored. `linemaxy` has 50 games; a
  self-selected slate produces a cover rate not comparable to a model that prices everything.
  The screen was declared in the script before scoring, not tuned afterwards.
- **Not a version A or B read.** Amendment B3's stopping rule is untouched.

## Method

Data: `data/ingest/prediction_tracker_lines.csv`, **17,389 graded games, 2001–2025**, pushes
(`y + line == 0`) dropped. 152 model columns after excluding `MARKET_LINES` (`lineca`,
`linemidweek`, which are market lines, not models); **109 pass the screen** of ≥ 1,000 graded
predictions and ≥ 3 seasons.

A model's column is a spread in the archive's negated sign, so the model favours **home** iff
`model < line`. Home covers iff `y + line > 0`.

Inference clusters on season: per-model per-season cover rates, then a one-sample t-test of
those season means against 0.5238. Loading, margin orientation, `prior_skill` and `bh_qvalues`
come from `eval_prediction_tracker_models.py`.

```bash
python research/spread/scripts/eval_model_columns_ats.py
```

Writes `data/processed/model_columns_ats.json`.

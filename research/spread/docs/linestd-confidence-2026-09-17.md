# Is PT's `linestd` a usable confidence weight? — 2026-09-17

**EXPLORATORY.** Not registered in `prereg-line-movement.md`. Companion to
`phcover-accuracy-2026-09-17.md`; same harness, same grading rules. No verdict follows from it.

## Question

`linestd` is the standard deviation of PT's model panel on a game. It is sign-free, so it cannot
pick a side — it can only claim to say **how much to trust something else**. Two versions of that
claim: does panel disagreement forecast how unpredictable the game is, and does the panel's own
signal work better where the panel agrees with itself?

## Answer: it modulates the signal a little, nowhere near enough to matter. And the panel's side loses on 23 seasons.

### 1. `linestd` does not forecast game volatility

| | value |
|---|---|
| corr(`linestd`, \|y + line\|) | **−0.006** |
| corr(`linestd`, \|line\|) | +0.473 ← the confound |
| corr(`linestd` residualized on \|line\|, \|y + line\|) | **−0.008** |

Panel disagreement says nothing about how far the game landed from the spread. The only thing
`linestd` tracks is **spread size** — big numbers carry more disagreement mechanically, which is
why the raw column looks like it means something. Residualizing on `|line|` removes that and
leaves zero.

### 2. Betting the panel's side loses, across the whole archive

The signal is `lineavg − line`: the market implies a home margin of `−line`, the panel implies
`−lineavg`, so the panel favours home iff `lineavg − line < 0`. This is the same object
`phcover` turned out to be a squashed transform of (`phcover-accuracy-2026-09-17.md` § 1).

| | value |
|---|---|
| bets | 16,056 (2003–2025) |
| ATS | **0.4943** |
| 95% CI (season clusters) | **[0.4871, 0.5015]** |
| break-even at −110 | 0.5238 |

The interval excludes break-even by a wide margin, and excludes 0.500 at the top end. On 23
seasons, taking the side the model panel favours against the market is a **losing** bet.

This is an independent archival confirmation of `actionable-picks-2026-09-17.md` § 0, which
found the same trade on the live 2026 slate by a different route — there, that the served `edge`
column is the market's own move sign-flipped.

### 3. No slice of `linestd` rescues it

Cover rate of the panel's side by `linestd` quintile, season-cluster CIs:

| quintile | n | mean `linestd` | ATS | 95% CI | AUC |
|---|---|---|---|---|---|
| 1 (most agreement) | 3,236 | 3.14 | 0.4994 | [0.4794, 0.5200] | 0.505 |
| 2 | 3,221 | 4.10 | 0.5008 | [0.4833, 0.5175] | 0.502 |
| 3 | 3,207 | 4.84 | 0.4839 | [0.4705, 0.4974] | 0.474 |
| 4 | 3,188 | 5.71 | 0.5060 | [0.4882, 0.5273] | 0.501 |
| 5 (most disagreement) | 3,204 | 7.58 | 0.4813 | [0.4649, 0.4990] | 0.478 |

No quintile's point estimate clears 0.5238, and the table is not monotone — the "most
agreement" quintile (0.4994) and the "most disagreement" quintile (0.4813) are both losers, with
quintile 4 the best of the five. Repeating the cut on `linestd` residualized on `|line|`, so the
quintiles are not a spread-size cut in disguise, gives the same picture (0.4818 to 0.5083).

**Corrected 2026-09-17** — this section first said "there is no monotone trend", resting on that
non-monotone table. Five separate quintile tests are a weak way to ask the question: each has a
median MDE of about 0.024, and a real slope can hide inside that. The powered version is one
regression, and it does find something (§ 4).

### 4. There *is* a trend — and it is far too small to matter

Regressing the win indicator on `linestd`, season-cluster bootstrap on the slope:

```
ATS = 0.5205 - 0.00517 x linestd     slope 95% CI [-0.01004, -0.00052]
```

The interval excludes zero. The panel's signal really does decay as the panel disagrees with
itself, so `linestd` is a genuine confidence modulator — the quintile table was simply too noisy
to show it.

It is also useless, and the arithmetic says so cleanly:

| | value |
|---|---|
| `linestd` at which the fit reaches break-even | **-0.64** |
| observed minimum `linestd` | 1.24 |
| fitted ATS extrapolated to `linestd` = 2 | 0.5101 [0.4967, 0.5239] |

Break-even is reached only at a **negative** dispersion, which cannot exist. And at the low end
the extrapolation does not survive contact with the data:

| cut | n | ATS |
|---|---|---|
| `linestd` <= 2.5 | 300 | **0.4733** |
| `linestd` <= 3.0 | 1,083 | 0.4995 |
| `linestd` <= 3.5 | 2,509 | 0.5054 |

So the trend is statistically real and economically irrelevant: you would need to extrapolate
past the physical floor of the variable to reach the vig.

### 5. What these tests could have detected

| test | MDE at 80% power | observed | reading |
|---|---|---|---|
| baseline vs break-even | 0.0103 | gap +0.0295 | **2.9x the MDE — decisive** |
| trend slope vs 0 | — | CI excludes 0 | powered; effect real but tiny |
| per-quintile vs break-even | ~0.024 | — | **1 of 5 quintiles has an upper bound above break-even** |

The pooled baseline and the trend are well powered. The individual quintile cells are **not** —
one of the five cannot exclude a small edge, which is why § 3 should be read as "no quintile is
demonstrably profitable", not "every quintile is demonstrably unprofitable".

## What this does not support

- **Not a claim that `linestd` carries no information at all.** § 4 finds a real negative slope.
  The claim is that the effect is far too small to lift the panel signal over the vig, and that
  most of `linestd`'s raw variation is spread size.
- **Not a claim that `linestd` forecasts volatility.** That one is a clean null (§ 1).
- **Not a claim about fading the panel.** The baseline 0.4943 [0.4871, 0.5015] is below
  break-even, so the other side of it is 0.5057 — also below 0.5238 once you pay vig on it. This
  is a null, not an inverted edge.
- **Not a version A or B read.** Amendment B3's stopping rule is untouched.
- **Not a test of E4.** E4 is an opener-anchored fitted predictor with a screened consensus;
  `lineavg` is the raw unscreened panel mean. The two are related but not the same object.

## Method

Data: `data/ingest/prediction_tracker_lines.csv`, seasons **2003–2025** — `linestd` reaches
further back than `phcover` (2017+), so this sample is 16,056 graded games against that study's
6,669. Pushes (`y + line == 0`) dropped.

Loading, margin orientation and the season-cluster bootstrap come from
`eval_prediction_tracker_models.py` (`base.load()` keeps `match_status == 'matched'` and flips
the margin where CFBD's home differs from PT's home). Home covers iff `y + line > 0`.

```bash
python research/spread/scripts/eval_linestd_confidence.py
```

Writes `data/processed/linestd_confidence.json`.

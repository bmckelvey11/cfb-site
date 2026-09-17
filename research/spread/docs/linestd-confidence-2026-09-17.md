# Is PT's `linestd` a usable confidence weight? — 2026-09-17

**EXPLORATORY.** Not registered in `prereg-line-movement.md`. Companion to
`phcover-accuracy-2026-09-17.md`; same harness, same grading rules. No verdict follows from it.

## Question

`linestd` is the standard deviation of PT's model panel on a game. It is sign-free, so it cannot
pick a side — it can only claim to say **how much to trust something else**. Two versions of that
claim: does panel disagreement forecast how unpredictable the game is, and does the panel's own
signal work better where the panel agrees with itself?

## Answer: no to both. And the panel's side loses on 23 seasons.

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

Nothing clears 0.5238 — not one quintile's interval even reaches it. There is no monotone trend:
the "most agreement" quintile (0.4994) and the "most disagreement" quintile (0.4813) are both
losers, and quintile 4 is the best of the five.

Repeating the cut on `linestd` residualized on `|line|`, so the quintiles are not a spread-size
cut in disguise, changes nothing (0.4818 to 0.5083 across quintiles, every interval below
break-even).

## What this does not support

- **Not a claim that `linestd` is meaningless as a descriptive statistic.** It measures real
  panel dispersion; it just has no forecasting content for the spread, and most of its variation
  is spread size.
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

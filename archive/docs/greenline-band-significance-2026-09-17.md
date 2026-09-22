**Superseded by** [greenline-totals-rule-search-2026-09-22.md](../../research/totals/docs/greenline-totals-rule-search-2026-09-22.md)

# Is the band split significant? Greenline unders, 2026-09-17

Reproduce: `python research/totals/scripts/band_significance.py --out research/totals/docs`.
Data: personal unders 2023-25 (`data/ingest/bet_history/history.csv`) and graded 2026 Greenline
under flags (`data/ingest/pff_scoreboard/pff_greenline_2026_w*.csv`). n = 201 history, 39 2026,
240 pooled. Pushes dropped. Bands from `greenline_unders.py`.

## Question

The week 3 slate is ordered by band (55-59.5 first, 50-54.5 last). Is the band effect
distinguishable from noise, once you account for the band having been chosen by looking at the same history?

## Records by band

| band | history 2023-25 | 2026 flags | pooled |
|---|---|---|---|
| <45 | 9-2 (82%, 52–95%) | 1-0 (100%, 21–100%) | 10-2 (83%, 55–95%) |
| 45-49.5 | 8-4 (67%, 39–86%) | 3-7 (30%, 11–60%) | 11-11 (50%, 31–69%) |
| 50-54.5 | 6-11 (35%, 17–59%) | 4-6 (40%, 17–69%) | 10-17 (37%, 22–56%) |
| 55-59.5 | 50-32 (61%, 50–71%) | 12-4 (75%, 51–90%) | 62-36 (63%, 53–72%) |
| 60-64.5 | 30-30 (50%, 38–62%) | 1-0 (100%, 21–100%) | 31-30 (51%, 39–63%) |
| 65+ | 11-8 (58%, 36–77%) | 1-0 (100%, 21–100%) | 12-8 (60%, 39–78%) |

## 1. All six bands at once (chi-square of independence)

| sample | chi2 | dof | p |
|---|---:|---:|---:|
| pooled | 10.79 | 5 | 0.056 |
| history only | 8.20 | 5 | 0.145 |
| 2026 only | 8.50 | 5 | 0.131 |

## 2. One band against the rest (Fisher exact, two-sided)

| band | sample | band | rest | p |
|---|---|---|---|---:|
| 55-59.5 | pooled | 62-36 | 74-68 | 0.112 |
| 55-59.5 | history only | 50-32 | 64-55 | 0.385 |
| 55-59.5 | 2026 only | 12-4 | 10-13 | 0.099 |
| 50-54.5 | pooled | 10-17 | 126-87 | 0.038 |
| 50-54.5 | history only | 6-11 | 108-76 | 0.076 |
| 50-54.5 | 2026 only | 4-6 | 18-11 | 0.282 |

## 3. Best-of-six correction (pooled)

Null: every band wins at the pooled rate 56.7%. 200,000 simulated seasons with the observed band sizes,
6 bands with n >= 10.

- P(best band reaches >= 63.3% by chance) = **0.817**
- P(worst band falls to <= 37.0% by chance) = **0.193**

These are the honest p-values for 'the strongest band looks strong' and 'the weakest band looks weak'
when six bands were inspected. They still overstate the evidence for the *specific* 55-59.5 band, because
the boundaries were set by hand after seeing 2023-25.

## 4. Trend in the market total (no bands)

| sample | mean total, wins | mean total, losses | Mann-Whitney p | Spearman(total, win) | p |
|---|---:|---:|---:|---:|---:|
| pooled | 56.8 | 57.3 | 0.987 | -0.001 | 0.987 |
| history only | 57.2 | 58.4 | 0.693 | -0.028 | 0.693 |
| 2026 only | 54.6 | 51.8 | 0.053 | +0.317 | 0.049 |

## 5. Out-of-sample: does the history ordering predict 2026?

Each 2026 under is scored by its band's 2023-25 win rate (the number that built the queue). If the
ordering carries information, 2026 winners should carry higher scores than 2026 losers.

- AUC = **0.475** (0.5 = no information), one-sided Mann-Whitney p = **0.617**, Spearman -0.046, n = 39.
- 2026 by proposed queue position: 55-59.5 12-4, <45 1-0, 45-49.5 3-7, 60-64.5 1-0, 65+ 1-0, 50-54.5 4-6.

## Reading

- Pooled, the six-band split is not significant at 5% (chi-square p = 0.056),
  and 55-59.5 vs rest has Fisher p = 0.112. That is the number the 'strongest thread' claim rests on.
- Correcting for having looked at six bands, the best band reaching 63% has p = 0.817 and the worst band
  falling to 37% has p = 0.193. The band pattern as a whole survives the multiple-look correction only if both are small.
- The pooled numbers include the 2023-25 history that chose the band. The clean test is 2026 alone: chi-square p = 0.131,
  55-59.5 vs rest p = 0.099, history-ordering AUC 0.47 (p = 0.617) on 39 flags.
- The trend test asks a different question (is win rate monotone in the total?) and is the one a skeptic would accept
  without bands; its answer is in section 4.

## What this does not support

- Treating any band as a rule. The out-of-sample sample is one graded week.
- A causal story (low totals = defensive games = under). The 50-54.5 dip breaks monotonicity; a real
  mechanism would not skip a band.
- Sizing by band. The bankroll projection uses one p for every flag; ordering is free, sizing is not.

## What settles it

Rerun after each graded week. The out-of-sample AUC in section 5 is the number to watch; ~150 2026 unders
gives it power to detect AUC 0.60 at the 5% level.

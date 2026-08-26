# Team stats behind the under bets — database analysis

Joined your 203 NCAAF unders to `data/processed/features.json` (78 features, 12,964 games).
Built an explicit 114-entry Action Network → CFBD abbreviation map; **190 of 203 bets matched (94%)**.
Feature coverage on matched bets: 87–100% depending on stat.

---

## 1. What the teams you bet actually look like

Your unders are **not** on bad offenses. They are on *above-average* ones:

| metric (both teams averaged, entering game) | your bets | league avg | delta |
|---|---|---|---|
| offensive PPA | 0.252 | 0.177 | **+0.075** |
| offensive success rate | 0.451 | 0.425 | **+0.027** |
| offensive explosiveness | 1.307 | 1.231 | **+0.076** |
| team talent | 643.2 | 508.0 | **+135.2** |

You are systematically **fading good offenses in high-profile games** — bigger brands, more talent,
better efficiency numbers than a random CFB game. That is a coherent, deliberate-looking profile:
it fits the "public loves overs in marquee matchups, so the total gets shaded up" thesis.

## 2. Do those stats predict whether your under hits? No.

Median split across your 190 matched bets (55.8% hit rate overall):

| feature | low half | high half | p |
|---|---|---|---|
| offensive success rate | 48.8% | 64.3% | 0.061 |
| offensive PPA | 51.2% | 61.9% | 0.213 |
| team talent | 50.5% | 61.1% | 0.188 |
| defensive PPA | 59.5% | 53.6% | 0.534 |
| explosiveness | 59.5% | 53.6% | 0.534 |
| total line | 57.3% | 54.3% | 0.770 |
| week | 51.4% | 61.2% | 0.189 |

Nothing significant. The most suggestive (success rate, p=0.061) points **counterintuitively** —
unders did *better* against high-success offenses.

## 3. Validating that against all 12,339 games — it does not hold

Under hit rate by quintile of combined offensive quality:

| quintile | success rate | PPA | talent | explosiveness |
|---|---|---|---|---|
| Q1 (low) | 50.92% | 49.16% | 49.69% | 50.81% |
| Q2 | 49.19% | 49.97% | 51.44% | 50.48% |
| Q3 | 50.74% | 51.07% | 50.31% | 49.06% |
| Q4 | 49.63% | 49.73% | 51.39% | 50.48% |
| Q5 (high) | 51.91% | 52.17% | 51.31% | 51.55% |

Every cell lands between 49% and 52%. **None reaches the 52.38% breakeven.** Best case
(PPA Q5) is 52.17%, ROI **-0.40%**.

### Why: the market already prices these stats

| stat | corr with posted total | corr with margin (pts − total) |
|---|---|---|
| offensive success rate | **+0.361** | **-0.025** |
| offensive PPA | **+0.373** | **-0.022** |
| explosiveness | +0.134 | — |
| talent | +0.045 | — |

Offensive efficiency correlates strongly with the *posted number* and essentially zero with the
*residual*. The bookmaker has already moved the total to absorb the information. Mean margin by
success quintile drifts only from +1.10 (Q1) to -0.27 (Q5) — under one point across the whole range.

**Conclusion: no team-stat pattern in the registry separates winning unders from losing ones.**

---

## 4. One situational pattern that does survive

Scanning situational flags rather than team stats:

| situation | record | under % | ROI | p | n |
|---|---|---|---|---|---|
| Conference game | — | 51.40% | — | — | 8,410 |
| Indoors | 224-188 | 54.37% | +3.80% | 0.224 | 412 |
| Neutral site | 189-148 | 56.08% | +7.07% | 0.096 | 337 |
| **Neutral site + indoors** | **69-40** | **63.30%** | **+20.85%** | **0.014** | **109** |

The combined cell is the strongest thing found anywhere in this project. It holds up better than
the seasonal effect did:

- Consistent across the season: wk1 63.3%, wk2-13 63.6%, wk14+ 63.0% — **not** a bowl-game artifact
- Both halves positive: 2013-2019 **58.5%** (n=53), 2020-2025 **67.9%** (n=56)
- Positive in 9 of 12 seasons with data

Mechanism is plausible and independent of the earlier (failed) weather story: **domed neutral-site
games are showcase events** — kickoff classics, conference championships, neutral-site bowls. Public
money piles onto marquee neutral games, and books shade those totals up. Removing weather variance
via the dome also removes a source of *over*-side variance.

**Caveats.** 109 games is small. p=0.014 does not survive Bonferroni across the ~25 tests in this
project (alpha ≈0.002). Neutral-site alone (n=337, the bigger sample) is only p=0.096. Treat as the
best available lead, not a proven edge.

**You have barely touched it:** of your 190 matched unders, only 10 were indoors, 13 neutral-site,
and **4 both** (3-1). This is unexploited, not something you have already been harvesting.

---

## 5. Bottom line

1. **Your selection has a clear signature** — you fade good offenses in high-talent games. It is a
   real, consistent strategy, not random picking.
2. **No team stat in the registry explains your results.** Efficiency metrics are fully priced into
   the total; their correlation with the residual is ~zero across 12,339 games.
3. **The one live lead is situational, not statistical**: neutral-site + indoor unders, 63.3% over
   109 games, stable across eras and across the season.
4. Your +8.9% ROI on 203 bets still has no measurable mechanism behind it in this data. That leaves
   variance or unmeasured judgment — and CLV remains the only fast way to tell them apart.

## Suggested next step

Paper-track neutral-site indoor unders for 2026 (~10-15 qualifying games per season, so it will
accumulate slowly). Do not size up on 109 historical games. If you want a faster read, pulling
closing lines for your existing 203 bets would settle the selection-skill question in one pass.

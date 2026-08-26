# CFB Bet History Analysis — 2023–2025 Seasons

Personal NCAAF bet history (`history.csv`, 580 rows) joined against the cfb_system_maker database (`data/processed/games.csv`, `features.json`, GraphQL `game`/`gameLines` for postseason gaps). Generated 2026-08-26.

## Method

- **Scope:** NCAAF full-game straight bets (spread / total / moneyline). 489 bets qualified; **488 matched** to database games by kickoff timestamp + team-abbreviation resolution (neutral-site home/away flips handled). 1 unmatched: ND @ PSU 2025-01-09 CFP semifinal — absent from the local GraphQL postseason dump.
- **Validation:** every matched bet was re-graded from database final scores. **0 mismatches** against the book's recorded results across all 488 — the join is trusted.
- **Excluded:** 13 NCAAF non-core rows (first-half, live, second-half, team-total, custom; net ≈ +0.3u), plus parlays/teasers and ncaab/nfl rows.
- **Stats:** breakeven at −110 is **52.38%**. Every split gets a 95% Wilson CI; key claims get a one-sided binomial p vs breakeven. ~40 splits were examined, so expect ~2 spurious p<.05 results — verdicts account for that.
- Units: 1u = $1,000. Stakes are near-flat (mostly 1u).

## Headline

| | Record | Win% | 95% CI | Units | ROI | p vs breakeven |
|---|---|---|---|---|---|---|
| **All 488 bets** | 261-224-3 | 53.8% | 49.4–58.2 | **+20.5u** (+$20,475) | +4.1% | .26 |

Profitable overall, but the total record alone is **not statistically distinguishable from luck** (CI contains 52.4%). The composition is what matters — see below.

Max drawdown: **−23.3u**, dug during the 2023 season.

## Season arc

| Season | Record | Win% | Units | ROI | p |
|---|---|---|---|---|---|
| 2023 | 114-124-1 | 47.9% | −17.6u | −7.4% | — |
| 2024 | 55-40-2 | 57.9% | +12.2u | +12.2% | .13 |
| 2025 | 92-60 | 60.5% | +25.8u | +15.6% | **.022** |

Monotonic improvement. 2023 was a losing year; 2025 clears breakeven with statistical support on its own. Worst stretches: Aug–Oct 2023 (−18.1u), Jan of every year (2024-01: 0-3; 2026-01: 2-6, −4.0u — bowl/CFP betting is a recurring small leak).

## Where the profit comes from: totals, not spreads

| Market | Record | Win% | 95% CI | Units | ROI | p |
|---|---|---|---|---|---|---|
| **Totals** | 134-97 | **58.0%** | 51.6–64.2 | **+27.9u** | +11.6% | **.043** |
| Spreads | 126-121-3 | 51.0% | 44.8–57.2 | −3.7u | −1.4% | .67 |
| Moneylines | 1-6 | — | — | −3.7u | −63% | — |

All net profit (and then some) comes from totals. Spreads are a coin flip that pays juice. The 7 moneylines — all longshot-flavored (plus-money dogs 0-7, −5.8u including ML-adjacent stakes) — are a pure leak.

- **Unders:** 114-87 (56.7%, CI 49.8–63.4), +19.0u. The bread-and-butter bet (201 of 231 totals).
- **Overs:** 20-10 (66.7%), +8.8u — great rate, tiny sample.

### Totals by line height

| Total | Record | Win% | Units | Note |
|---|---|---|---|---|
| **< 52** | **36-11** | **76.6%** | **+21.7u** | p≈.0004 — biggest outlier in the book |
| 52–58.5 | 43-42 | 50.6% | −2.3u | dead weight |
| 59–65.5 | 46-38 | 54.8% | +6.0u | mildly positive |
| 66+ | 9-6 | 60.0% | +2.4u | small |

Low-total (defensive) games are where the totals edge concentrates — both unders (9-2) and overs (12-4) in that bucket. The mid-range 52–58.5 bucket, where the most volume went (85 bets), returned nothing. Even after multiple-comparison discounting, <52 is the single most persuasive split in the data.

## Closing line value — the skill evidence

CLV vs the database consensus closing line (positive = you got a better number than close):

| Market | Mean CLV | Beat close | Matched | Worse than close |
|---|---|---|---|---|
| **Totals** (n=227) | **+0.45 pts** | 67-39 (63.2%), +24.2u | 36-26 (58.1%) | 29-30 (49.2%), −3.1u |
| Spreads (n=250) | +0.07 pts | 52-46 (53.1%) | 33-36 | 41-39 |

The totals story is coherent: you beat the closing number on average, and results grade **monotonically with CLV** — beat-close bets won 63.2% (p≈.013), worse-than-close bets were a coin flip. That's the classic signature of real number-picking skill on totals. On spreads there is no CLV and no gradient — consistent with the flat P&L.

Vs the *opening* line, spread bets that took a worse number than open actually won more (59.4%) than those that beat open (46.2%) — i.e., you did better betting *with* line movement than against it. Sample is modest (n=183 with open lines); treat as a lean, not a law.

## Spread-side splits (all noise-to-negative)

- **Home spreads: 50-58-2 (46.3%), −10.7u** vs away spreads 76-63-1 (54.7%), +6.9u. One-sided p for homes beating breakeven: .90 — the home side has been the losing half.
- Favorites 70-64-3 (−0.1u) vs dogs 55-57 (−4.6u): nothing.
- Spread-size buckets: no bucket clears noise; dogs +14.5 to +21 worst (4-7, −2.7u).
- Pregame-Elo edge of the bet side: no gradient (54%/46%/52%).
- Bet-side entering ATS form: no gradient — teams ≥60% ATS won 52.8%, teams ≤40% ATS won 58.5%. Your ATS-momentum reads add nothing.
- Conference sides: Big Ten sides 13-17 (−3.6u), SEC sides 19-20-1; C-USA 9-4 and Mountain West 11-4 positive — all small-n noise territory.

## Situational

| Split | Record | Win% | Units | p | Read |
|---|---|---|---|---|---|
| **Weeks 9+ (late season)** | **63-29** | **68.5%** | **+30.9u** | **.001** | Survives even harsh multiple-comparison discounting |
| Weeks 4–8 | 99-86-2 | 53.5% | +5.1u | — | Marginal |
| Weeks 0–3 | 77-83 | 48.1% | −12.1u | — | Below water every season |
| Tue+Wed (MACtion) | 24-8 | 75.0% | +15.2u | .005 | Overlaps weeks 9+; small n but consistent |
| Sat | 190-171-3 | 52.6% | +8.1u | — | Volume, ~breakeven |
| Late night (10:15pm+) | 6-8 | — | −1.9u | — | Small leak |

The late-season number is the strongest situational signal in the book: your entire +20.5u lifetime profit is more than covered by weeks 9+ (+30.9u over 92 bets). Early-season betting (weeks 0–3) has lost money in aggregate across all three years — 160 bets, −12.1u — which is exactly when priors are weakest and books' power ratings are as blind as yours.

Time slot (noon/afternoon/prime): flat. Weather: unders in wind ≥12mph went 11-12 while calm-air (<6mph) unders went 48-32 (60.0%) — if anything the market already over-shades windy unders. Dome/temp splits: nothing actionable.

## Verdicts

**Keep**
1. **Totals, especially in low-total games (<52).** The one market with ROI, CLV, and a results-follow-CLV gradient. 
2. **Late-season volume (weeks 9+ / November MACtion).** 68.5% over 92 bets, p≈.001 — the most defensible edge here.
3. **Line shopping on totals.** Your beat-close bets earn +24u; your worse-than-close bets lose. Getting the number *is* the edge — if the good number is gone, the bet mostly isn't there.

**Stop**
4. **Plus-money moneyline dogs.** 0-7, −5.8u. Pure leak, no thesis visible.
5. **January bowl/CFP betting.** 2-9 across three postseasons (−6.5u). Small but repeated.

**Reduce / re-examine**
6. **Weeks 0–3.** −12.1u over 160 bets, negative all three years. Either sit out or cut stakes until your in-season data advantage exists.
7. **Home spreads.** 46.3% over 110 bets. Not statistically damning, but paired with the flat spread P&L overall: your spread process adds no value yet — treat spreads as entertainment-sized or route them through the backtester before betting.
8. **Mid-range totals (52–58.5).** Your highest-volume bucket, zero return. Volume ≠ edge.

**Honest caveat:** verdicts 1–2 were selected *after* looking at ~40 splits. The prospective test is the 2026 season: if low-total totals and weeks-9+ bets keep clearing 55%+ on new money, the edge is real; if they regress to ~52%, this was partly selection.

## Appendix

- Unmatched (excluded): ND @ PSU 2025-01-09 CFP semifinal (2 rows in raw CSV, 1 qualifying).
- Excluded NCAAF non-core: 6 first-half, 1 live, 1 second-half, 2 team-totals, 1 custom, 2 other — net ≈ +0.3u.
- Analysis script: one-off, run against `data/processed/` + `data/graphql/`; bet-to-game join validated by re-grading (0/488 mismatches).

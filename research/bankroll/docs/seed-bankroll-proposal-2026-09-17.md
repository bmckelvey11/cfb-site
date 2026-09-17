# Seed bankroll proposal: $20,000 for the rest of the 2026 college football season

Prepared September 17, 2026. This is a private request to family for a **gift** that
funds a betting bankroll. Nothing is owed back. It is not an investment, not a loan,
and not a security. What follows is what the money would fund, what has been earned
so far, and what the model says is likely to happen to it.

Every number below comes out of a script in this repository. Reproduce with:

```
python research/bankroll/scripts/mc_combined_totals.py --paths 100000
python research/bankroll/scripts/bankroll_config_sweep.py --paths 50000 --out research/bankroll/docs
```

---

## 1. The ask

| item | value |
|---|---|
| amount | **$20,000** |
| horizon | weeks 4–15 of the 2026 regular season, September 24 to December 12. Twelve weeks. Week 3 (this weekend) is not in the projection |
| what it funds | two totals strategies, both already running, at flat stakes |
| expected bets | ~87: ~76 Greenline unders and ~11 over-zero overs |
| recommended stake | Greenline **$100 per bet** (0.5%), over-zero **$200 per bet** (1%) |
| what happens after | bankroll and profit stay in the operation for 2027, where the larger of the two edges does most of its work |

## 2. The answer in one paragraph

**Median outcome is a gain of $540 to $730 over twelve weeks. Roughly one season in
three ends below $20,000. No modeled path loses a quarter of the money, and none goes
to zero.** The range is bracketed because the main strategy's win rate rests on two
defensible readings of the record, and neither can be ruled out yet. Everything below
reports both.

| Greenline prior | median | 90% band | P(down) | P(−25%) | busts |
|---|---:|---|---:|---:|---:|
| `pooled` (141–109) | **$20,727** (+3.6%) | $18,773 – $22,679 | 27.0% | 0.0% | 0.0% |
| `n49` (27–22) | **$20,542** (+2.7%) | $18,060 – $22,979 | 35.8% | 0.0% | 0.0% |

## 3. What gets bet

Two strategies. One bankroll. Flat stakes off the starting $20,000, no compounding.

### Over-zero (floor-bias OVERs)

A model built in this repository. It finds games where the market total is pinned
too low by the way books price a heavy favorite's opponent, and bets the OVER when
the expected bias clears a threshold.

| fact | value | source |
|---|---|---|
| walk-forward record, 2016–2025 | **151–83, 64.5%** (95% CI 58.2–70.4%) | `models/over_zero/docs/ROI_HITRATE.md` |
| ROI at −110 | +23.2% (CI +11.1 to +34.4%) | same |
| planning win rate | **58.2%**, the CI floor, because the threshold was picked on this data | `MODEL_GUIDE.md` |
| price rule | −120 or better | same |
| bets left in 2026 | **~11**. Volume is front-loaded into weeks 1–3, already played | `mc-combined-totals-2026-09-17.md` |
| 2026 so far | 17–8 through week 2 | `site/lib/weekly-results.json` |

This is the better-evidenced edge, and it is nearly spent for 2026. Its median
contribution from here is **+$133**. It matters for 2027, when it fires 30–50 times.

### Greenline totals (PFF vendor flags, unders)

PFF publishes a projection per game and flags totals where it disagrees with the
market. Flags are captured Wednesday, graded Monday. ~85% of flags are unders.

| fact | value | source |
|---|---|---|
| 2026 graded flags | **27–22, 55.1%** (CI 41–68%), one week | `greenline-season-review-2026-09-16.md` |
| 2023–25 personal unders, mostly the same flags | **114–87, 56.7%** (CI 49.8–63.4%), 201 bets | `bet-history-analysis-2023-2025.md` |
| pooled prior | 141–109, posterior mean 56.4%, P(losing) 10% | `mc-combined-totals-2026-09-17.md` |
| 2026-only prior | 27–22, posterior mean 55.0%, P(losing) 35% | same |
| historical rate bet | ~13% of flags, **~6 a week**, ~76 over 12 weeks | same |
| price | −110, break-even 52.38% | same |

The 2023–25 record is the same signal in earlier seasons, bet by the same person. It
is legitimate prior evidence. It is **not** independent confirmation of PFF, and this
document never treats it as one. Those 201 unders also sat six points higher in total
than the 2026 flags (median 58.5 vs 52.5), so the pooled 56.4% probably reads high.
That is why the 2026-only prior is carried alongside it everywhere.

### Conflict rule

Rare, but it has happened: week 2, Rice @ Notre Dame, over-zero said OVER 54.5 and
Greenline flagged UNDER 55.5. Betting both pays juice twice for a hedge. **Rule:
Greenline takes the game, over-zero skips it.** Greenline carries the volume.

### Excluded

The spread model in `research/spread/` is research, not a bet. Greenline spreads and
moneylines went 21–28 and 21–25 in week 2 and are not funded.

## 4. How the projection works

One simulated path is one whole remainder-of-season. 100,000 paths for the headline,
50,000 per cell of the sweep.

- **Win rates are never fixed.** Each path draws its own win rate from the Beta
  posterior of the graded record, so the spread of outcomes includes not knowing the
  true rate, not just luck.
- **Bets on the same Saturday are correlated** through one scoring-environment
  shock (Gaussian copula, ρ = 0.10 assumed, ρ = 0.25 as sensitivity). Because
  over-zero is all overs and Greenline is mostly unders, a high-scoring day helps one
  and hurts the other.
- **Volume is resampled**, not fixed: over-zero from its week-4+ history
  (8, 11, 9, 11, 14 bets in 2021–25), Greenline as Poisson around 6.4 a week.
- **Flat stakes off the starting bankroll**, no stop-loss. A path can go through zero
  and keep betting, so the bust rate is reported on every row.
- Pushes not modeled: zero realized on all 484 graded bets, all on half-point lines.

## 5. Choosing the stake: the sweep

Greenline stake from 0.25% to 2% of bankroll, coverage from the historical 13% up to
every flag, both priors. Over-zero held at 1%. Full grid in
[`bankroll-config-sweep-2026-09-17.md`](bankroll-config-sweep-2026-09-17.md).

![Stake by coverage sweep](figs/bankroll-config-sweep-2026-09-17.png)

**Objective (a):** largest median gain such that at most 1% of paths end down 25% and
none go through zero, under **both** priors.
**Objective (b):** downside ratio = median gain ÷ (median − 5th percentile). Shown as
a column; higher is better.

Supported rows only (13% coverage, the population the record came from):

| GL stake | median (pooled / n49) | 5th pct (pooled / n49) | P(−25%) (pooled / n49) | ratio (pooled / n49) | passes (a) |
|---:|---|---|---|---|:---:|
| 0.25% | $20,432 / $20,338 | $19,161 / $18,852 | 0.0% / 0.0% | 0.34 / 0.23 | yes |
| **0.50%** | **$20,727 / $20,542** | **$18,773 / $18,060** | **0.0% / 0.0%** | **0.37 / 0.22** | **yes** |
| 1.00% | $21,315 / $20,936 | $17,685 / $16,203 | 0.2% / 1.9% | 0.36 / 0.20 | pooled only |
| 1.50% | $21,902 / $21,342 | $16,521 / $14,279 | 1.8% / 7.0% | 0.35 / 0.19 | no |
| 2.00% | $22,494 / $21,739 | $15,330 / $12,327 | 4.3% / 11.8% | 0.35 / 0.18 | no |

Three things the grid says:

1. **0.5% is the largest stake that passes under the conservative prior.** 1% passes
   only if the pooled prior is right. Recommended: **$100 per Greenline bet**, with
   $200 as the upgrade once the 2026 flags alone reach ~250 graded (four more weeks).
2. **Stake does not change the downside ratio.** It runs 0.34–0.37 under pooled and
   0.18–0.23 under n49 at every stake. Staking more buys a bigger median and a
   bigger 5th-percentile loss in the same proportion. There is no free stake.
3. **Coverage is what improves the ratio** (0.34 → 0.50 under pooled at 0.25%), and
   coverage is exactly the assumption the record does not support. Betting more of
   the flags is the lever, and it is unpriced until the ledger says which flags get
   taken. The best conditional row (0.5% at 25% coverage, median $21,261 / $20,918)
   is shown for that reason and not recommended.

## 6. Risk, stated plainly

At the recommended $100 / $200 stakes:

| measure | pooled | n49 |
|---|---:|---:|
| P(season ends below $20,000) | 27.0% | 35.8% |
| P(ends below $15,000) | 0.0% | 0.0% |
| P(passes through $0) | 0.0% | 0.0% |
| 5th-percentile ending bankroll | $18,773 | $18,060 |
| worst single week, median | −$427 | −$442 |
| total staked over 12 weeks | ~$9,800 | ~$9,800 |

The 5th percentile means one season in twenty ends worse than about −$1,900. The
30-ish percent chance of a losing season is mostly parameter uncertainty: the true
Greenline win rate has a 10–35% chance of being below break-even, and the season is
too short to average that away.

Correlation only bites the tail. Median is flat across ρ; the 5th percentile moves
by a few hundred dollars. ρ is assumed, not measured.

## 7. What this does not support

- **Greenline as independently validated.** n=49 in 2026, CI 41–68%. The pooled prior
  is 80% personal history of the same signal.
- **The pooled prior transferring in full.** The 201 unders sit ~6 points higher in
  total than the 2026 flags. Pooling probably overstates; by how much is unknowable
  from what exists.
- **Any coverage above 13%.** Every conditional row assumes the picked-flag win rate
  applies to flags that were passed on.
- **A reproducible selection rule.** "Bet ~6 of 49 flags a week" is a volume
  assumption. No script picks which six. The historical picks were hand-filtered and
  price-shopped.
- **A 2027 projection.** Not modeled. Over-zero at full-season volume and a full
  graded Greenline season are what it needs, and neither exists yet.
- **Compounded returns.** Simultaneous Saturday kickoffs make them unachievable;
  every figure here is flat-staked.

## 8. What the money does each week

| day | step | command |
|---|---|---|
| Wednesday | capture Greenline flags | `scripts/pull_pff_scoreboard.py --greenline` |
| Wednesday | seed the bet ledger | `research/bankroll/scripts/greenline_bet_log.py --seed` |
| Thursday–Saturday | bet ~6 unders at −110 or better, over-zero board at −120 or better | `models/over_zero` site |
| Monday | grade flags, mark which were bet | `grade_greenline.py`; `greenline_bet_log.py --mark` |
| Monday | rerun the projection with the new record | `mc_combined_totals.py` |

Marking which flags get bet is the one step that is not automated and the one that
resolves the biggest open question. Four more graded weeks gets the 2026 flags to
n≈250 on their own, at which point the prior stops doing the work and the stake
decision in §5 gets revisited.

## Data and dates

over-zero: 234 walk-forward bets 2016–2025, `models/over_zero/docs/backtest_bets.csv`.
Greenline: 49 graded flags, 2026 week 2, `data/ingest/pff_scoreboard/greenline_graded.csv`;
201 personal unders 2023-08 to 2025-12, `data/ingest/bet_history/history.csv`.
Projection span weeks 4–15, 2026. Seeds 20260917. Sweep: 50,000 paths per cell,
40 cells; headline table §2 from the sweep's 0.5% rows.

Related: [`mc-combined-totals-2026-09-17.md`](mc-combined-totals-2026-09-17.md),
[`under-selection-profile-2026-09-17.md`](under-selection-profile-2026-09-17.md),
[`bankroll-config-sweep-2026-09-17.md`](bankroll-config-sweep-2026-09-17.md).

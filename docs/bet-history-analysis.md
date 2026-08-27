# Action Network bet history — NCAAF analysis

Source: `~/Downloads/history.csv` (manual export). 564 straight bets + 5 parlays/teasers.
NCAAF subset: **502 bets, 2023-08-26 → 2025-12**, 269-230-3, **+21.8u on 519u risked = 4.2% ROI**.

Coverage caveat: profile shows 521-507-5 NCAAF all-time. This export is 2023+ only — roughly half your
NCAAF history is missing, and the missing half is older.

## Headline: you got better, sharply, after 2023

| season | n | units | ROI |
|---|---|---|---|
| 2023 | 245 | -17.75 | **-7.3%** |
| 2024 | 99 | +13.70 | **+13.4%** |
| 2025 | 158 | +25.85 | **+15.0%** |

2024-25 combined: **152-103 (59.6%), p=0.012** vs the -110 breakeven of 52.38%.
The improvement shows up in *every* bet type, not one lucky bucket:

| type | 2023 ROI | 2024 ROI | 2025 ROI |
|---|---|---|---|
| under | +1.2% | +19.9% | +11.5% |
| over | +21.4% | +9.6% | +51.9% |
| spread_away | -9.2% | +24.0% | +19.4% |
| spread_home | -15.3% | -6.6% | +1.0% |

A uniform lift across independent categories is the signature of a genuine process change,
not variance in one bucket.

## Strongest pattern: late season >> early season

Holds independently in all three seasons — the only pattern here that does:

| season | Aug-Oct | Nov-Dec |
|---|---|---|
| 2023 | -13.9% | **+6.1%** |
| 2024 | +10.5% | **+24.1%** |
| 2025 | +0.2% | **+33.5%** |

Nov-Dec all seasons: **105-65 (61.8%), p=0.0086**.

Plausible mechanism: by November, team-quality priors are real (10+ games of data) while
public perception still lags preseason ranking. Early season you are betting on noise.

## Candidate systems

| system | n | record | ROI |
|---|---|---|---|
| Nov-Dec + under | 70 | 44-26 (62.9%) | **+20.7%** |
| Nov-Dec + spread | 85 | 51-34 (60.0%) | **+16.4%** |
| Aug-Oct + spread_home | 70 | 29-41 (41.4%) | **-18.7%** |

That last one is the clearest *negative* system: early-season home spreads are your leak.
Cutting them alone would have added ~14u.

## Persistent structural leans

- **Home spreads are bad**: -11.7u over 111 bets (-10.2%). Away spreads +7.7u (+5.0%).
  You're paying for home-field bias that the market already prices.
- **Unders are your bread and butter**: 203 bets, +18.9u (+8.9%) — but 56.7%, p=0.125,
  *not* individually significant.
- **You bet almost exclusively -110 to -120** (97.4% of bets). No line shopping visible in the data.

## What I checked and rejected

- **Bet sizing skill — rejected.** >1u bets show +13% ROI vs 1u at -8.3%, which looks like
  confidence tracking outcomes. It doesn't: 2023 was 177 bets at 1.0u, 2024-25 is ~all 1.1u.
  Stake is a proxy for season. No sizing signal.
- **Team leans — rejected.** Best/worst teams (UTAH +62%, OU -28%) all have n≤8. Noise.
- **Live betting — insufficient data.** 2 bets.

## Statistical honesty

The 2024-25 result (p=0.012) does **not** survive Bonferroni correction across the ~12 subgroups
I tested (alpha 0.0042). Nov-Dec (p=0.0086) doesn't either. Treat both as *promising leads that
need forward testing*, not established edges. 502 bets sounds like a lot; for distinguishing a
55% bettor from a 52.4% bettor it isn't.

Missing from this export and needed to actually confirm an edge: **closing line value**. CLV is
the only fast-converging skill signal; win rate takes thousands of bets. If AN's export can
include closing odds, that changes the analysis qualitatively.

## Recommended next steps

1. Stop betting early-season home spreads. Clearest, best-supported negative.
2. Forward-test "Nov-Dec unders" on 2026 as a live paper system before sizing up.
3. Pull CLV if obtainable — it would settle in ~100 bets what win rate needs 2000 to show.
4. Backtest the Nov-Dec total lean in `cfb_system_maker` against the full 13k-game set;
   that has the sample size this export lacks.

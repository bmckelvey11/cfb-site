# Win-probability onset timing vs. bet outcome: NULL (as a bench-timing story)

Triggered by the 2025 season review (`docs/ROI_HITRATE.md`: 27–24, +1.07% ROI,
the weakest and largest test season). Hypothesis going in: qualifying bets are
huge-favorite/floor-bias games, so maybe favorites who clinch the win early get
benched, garbage time suppresses their scoring below the spread-implied number,
and that's costing the model. Tested directly against CFBD's per-play win
probability. The mechanism doesn't hold — but a real, different pattern
does.

Run:
```
python research/2026-08-31_win_prob_onset/pull_win_probability.py          # all seasons
python research/2026-08-31_win_prob_onset/pull_win_probability.py --season 2025
python research/2026-08-31_win_prob_onset/analyze_onset.py
```
Data: CFBD `MetricsApi.get_win_probability`, one call per qualifying game_id
(not a season-wide scrape). Source: `docs/backtest_bets.csv`, `passes_filter
== 1` (bias > 1.75), all seasons 2016–2025, N=234. Raw per-play win-probability
pulls are not committed (12MB+, reproducible via the pull script above) —
regenerate locally if you want to re-check a number.

## [A] The 2025 spot-check looked damning, alone

51 qualifying 2025 bets, 43 with CFBD win-probability coverage (8 games had
zero rows — smaller-school data gaps). `onset_frac` = play index where the
favorite's win probability first crosses 95%, as a fraction of the game's
total plays. `fav_gap` = favorite's actual points minus the spread/total-implied
number.

**Pearson r(onset_frac, fav_gap) = −0.65, n=43.** Strong. Games where the
favorite locked up the win late scored well below implied; games that locked
it up early scored well above. Read naively, that's the garbage-time story:
early clinch → bench → fewer points → the OVER misses.

## [B] The full 2016–2025 qualifying set: real, but far weaker

234 qualifying bets, 223 matched to CFBD win-probability data, 222 crossed the
95% threshold at some point in-game.

**Pearson r(onset_frac, fav_gap) = −0.19, n=222.** Same direction, much
smaller. The 2025 number was itself close to the tail of what 43 points of
noise can produce around a true −0.2-ish relationship — worth naming since
it's exactly the kind of single-season overreaction §8/§9 of `docs/MODEL_GUIDE.md`
warns against.

| onset (fraction of game before fav hits 95% WP) | N | avg fav_gap | win rate |
|---|---:|---:|---:|
| 0–20% | 114 | +3.3 | 70.2% |
| 20–35% | 46 | +7.0 | 73.9% |
| 35–50% | 30 | +1.1 | 70.0% |
| **50%+** | **31** | **−5.9** | **35.5%** |

Not a slope — a cliff. 86% of qualifying bets clinch by halftime and win
70–74% regardless of exactly how early. The entire effect sits in the 14% of
games where the favorite hasn't reached a 95% win probability by halftime (or
never does).

Per-season, restricted to 2022+ where CFBD's win-probability series has enough
resolution to trust (older seasons return sparse snapshots; several pre-2021
games register `onset_frac ≈ 0` from a coarse first row, not a real instant
clinch — those seasons are excluded here as unreliable, not because the effect
disappears):

| season | N | r(onset, fav_gap) | win rate |
|---|---:|---:|---:|
| 2022 | 34 | −0.18 | 55.9% |
| 2023 | 39 | −0.44 | 71.8% |
| 2024 | 30 | −0.41 | 63.3% |
| 2025 | 43 | −0.65 | 58.1% |

Consistently negative across the four best-resolved seasons — this isn't a
2025-only artifact — but 2025's magnitude is the high end of that range, not
the typical case.

## [C] Why it isn't a bench-timing / garbage-time mechanism

`onset_frac` is not an independent predictor of `fav_gap` — it's collinear
with it. A favorite that reaches 95% win probability in the first quarter is,
by definition, already scoring fast; a favorite still under 95% at halftime is
having a flatter game than the spread implied. Both the slow win-probability
climb and the scoring shortfall are downstream of the same thing: **the
favorite underperforming its number on the field**, not a separate effect
where clinching early causes a bench decision that then costs points. There is
no lead-lag here for a garbage-time story to exploit — CFBD's win-probability
series is contemporaneous with the score, not predictive of it.

## Conclusion

**Not a bettable or actionable mechanism.** The correlation is real (r=−0.19,
n=222, holds up across 2022–2025 individually) but it restates "the favorite
had a flat game" rather than identifying a fixable or exploitable cause. It
does not change the betting rule, and it does not point to a leading
indicator available before or during the game that isn't already baked into
the live score. Filed as a clean negative result on the *bench-timing*
hypothesis specifically — the underlying "favorite occasionally underperforms
its spread" fact is exactly the acknowledged blind spot in
`docs/MODEL_GUIDE.md` §8 ("the model is deliberately blind to weather,
injuries, and pace"), just now with a number attached instead of a guess.

**What this null does and does not say.** It does not say 2025 was normal
variance and nothing more — the 35.5% win rate in the "clinches after
halftime" bucket is a real, replicated-across-seasons soft spot, just one with
no independent trigger to bet around. It also does not rule out that some
*other* in-game signal (pace, injury news, live line movement) could predict
which favorites are about to have a flat night — this analysis only tested
win-probability timing, and found that specific candidate collinear with the
outcome rather than causal or predictive of it.

---
Qualifying bets: `docs/backtest_bets.csv`, bias > 1.75, 2016–2025 (N=234, 223
matched to CFBD win-probability data) | win-probability threshold: 95% |
generated 2026-08-31

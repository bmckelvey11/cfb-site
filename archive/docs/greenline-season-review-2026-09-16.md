**Consolidated into** [greenline-findings.md](../../research/totals/docs/greenline-findings.md) — its numbers are carried there under "The 2026 season on its own, all three markets". This file stays as the dated record of what week 2 showed; `greenline_season_review.py` writes a new dated review rather than updating this one.

# PFF Greenline picks, 2026 season to date

Generated 2026-09-16 by `research/totals/scripts/greenline_season_review.py`. Graded at the line in the capture, -110 on spreads and totals, market price on moneylines. Intervals are 95% Wilson. Pushes excluded from win% and calibration.

**Graded weeks:** 2. **Pending:** week 3 (57 flags)

## Record by market

| market | record | win% | 95% CI | units | ROI |
|---|---|---:|---|---:|---:|
| total | 27-22 | 55.1% | 41–68% | +2.55u | +5.2% |
| spread | 21-28 | 42.9% | 30–57% | -8.91u | -18.2% |
| moneyline | 21-25 | 45.7% | 32–60% | +1.58u | +3.4% |
| all | 69-75 | 47.9% | 40–56% | -4.79u | -3.3% |

Break-even at -110 is 52.4%. At n=144 pooled, the smallest true win rate a one-sided test would reliably detect is 63%; per market it is total 70%, spread 70%, moneyline 71%. Anything short of that is not evidence either way.

## By side

| market | side | record | win% | 95% CI | units | ROI |
|---|---|---|---:|---|---:|---:|
| total | over | 5-5 | 50.0% | 24–76% | -0.45u | -4.5% |
| total | under | 22-17 | 56.4% | 41–71% | +3.00u | +7.7% |
| spread | away | 15-18 | 45.5% | 30–62% | -4.36u | -13.2% |
| spread | home | 6-10 | 37.5% | 18–61% | -4.55u | -28.4% |
| moneyline | away | 7-16 | 30.4% | 16–51% | -5.97u | -26.0% |
| moneyline | home | 14-9 | 60.9% | 41–78% | +7.55u | +32.8% |

## Closing-line value (PFF board close)

- **total**: mean +0.36 ± 0.32 pts (n=44); beat close 19, lost 12, flat 13
- **spread**: mean +0.34 ± 0.29 pts (n=44); beat close 24, lost 10, flat 10

Positive means the number moved toward PFF's side after the capture. This is the board PFF shows, not Pinnacle, so it measures whether PFF's flags lead their own displayed market.

## Does PFF's own ranking work?

| market | top half by value | bottom half |
|---|---|---|
| total | 13-11 | 54.2% | 35–72% | +0.82u | +3.4% | 14-11 | 56.0% | 37–73% | +1.73u | +6.9% |
| spread | 7-17 | 29.2% | 15–49% | -10.64u | -44.3% | 14-11 | 56.0% | 37–73% | +1.73u | +6.9% |
| moneyline | 12-11 | 52.2% | 33–71% | -3.35u | -14.5% | 9-14 | 39.1% | 22–59% | +4.92u | +21.4% |

## Calibration of PFF's stated probabilities

| market | n | mean stated p | actual win% | Brier (PFF) | Brier (market) |
|---|---:|---:|---:|---:|---:|
| total | 49 | 55.0% | 55.1% | 0.2478 | 0.2500 |
| spread | 49 | 56.3% | 42.9% | 0.2685 | 0.2500 |
| moneyline | 46 | 45.0% | 45.7% | 0.1341 | 0.1384 |

Market Brier uses 0.5 for spreads and totals (a flag is a bet against a -110 line) and the vig-free price for moneylines. PFF beating the market column means its stated probabilities carry information; a stated-p above the actual win% means the numbers are overconfident.

## Pending: week 3

- 57 flagged games; totals 49 under / 8 over; spreads 36 away / 21 home; moneylines 21 away / 32 home.
- mean stated edge: totals +2.50%, spreads +4.07%.

## Reading

**Bottom line.** One graded week. Totals are the only market with a positive record, and the interval on it (41–68%) contains break-even. Spreads went 21-28 and PFF's stated 56% cover probability on them was not borne out (Brier worse than a coin). Moneylines net positive only because the home-side picks hit; the away-dog picks lost 6 units. None of these is a finding yet: the smallest effect one week can detect is a 70% win rate per market.

**What holds up across weeks so far**

- The under tilt is structural, not situational: 39 of 49 total flags in week 2, 49 of 57 in week 3. It comes from the projection sitting below the market on nearly every game -- projection minus Pinnacle fair total, week 2: median -1.35 over the 48 week-2 flagged games (both sides) matched to Pinnacle, 37/48 below; week 3: median -1.53 over 48 unders, 44 below Pinnacle (`greenline_vs_pinnacle.py`).
- PFF's totals probabilities were calibrated in week 2 (stated 55.0%, actual 55.1%, Brier 0.248 vs 0.250 coin). Its spread probabilities were not (stated 56.3%, actual 42.9%, Brier 0.269).
- PFF's `value` ranking does not order outcomes. Top-half-by-value did no better than bottom-half on totals, and worse on spreads (7-17 vs 14-11). Week 2's 4%+ totals bucket went 3-6 (`greenline-w2-grade-2026-09-15.md`). Do not size by their number.
- CLV against PFF's own board is small and positive on both totals (+0.36 ± 0.32) and spreads (+0.34 ± 0.29). The intervals barely exclude zero and the reference is PFF's displayed line, not a sharp close, so treat as weak.

**What this does not support**

- Any claim that Greenline totals beat break-even. n=49, CI 41–68%.
- Any per-band or per-bucket conclusion. Week 2's 55-59.5 band (11-3) is 14 games.
- Anything about spreads or moneylines beyond "one bad week"; the moneyline home/away split (14-9 vs 7-16) is the kind of split that appears by chance across ~40 sub-samples.
- Repriced results. All grades are at PFF's captured number; `match_greenline_books.py` shows books hang a different number on a third of the slate.

**What settles it.** Four more graded weeks gets totals to n≈250, where a true 56% would separate from 52.4% about half the time; eight weeks gets there reliably. Keep capturing Wednesday (`pull_pff_scoreboard.py --greenline`), grading Monday (`grade_greenline.py`), and rerun this script.

**Reproduce**

```
python scripts/pull_pff_scoreboard.py --season 2026
python research/totals/scripts/greenline_season_review.py --out research/totals/docs/greenline-season-review-<date>.md
```

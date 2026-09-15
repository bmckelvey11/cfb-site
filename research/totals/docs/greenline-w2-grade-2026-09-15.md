# PFF Greenline unders, 2026 week 2 — graded

**Question.** Did the 36 positive-edge unders PFF Greenline flagged for week 2
(captured 2026-09-10 11:13 ET, `data/ingest/pff_scoreboard/greenline_unders_2026_w2.md`)
win at the line PFF showed?

**Method.** `research/totals/scripts/grade_greenline.py --week 2`. Each flag is
graded at the PFF line in the capture (not the close), -110 both ways, pushes
returned. Finals come from the refreshed PFF schedule
(`scripts/pull_pff_scoreboard.py`, pulled 2026-09-15 12:10 ET). Six flags needed a
fallback, added to the script today:

- Five games PFF still lists as `Canceled` with no score (kickoff time was TBD at
  capture, so `kickoff_raw` is midnight): LAT@LSU, JVST@OHIO, BUFF@FIU, GAST@KENN,
  NMSU@HAW. All five played. Finals taken from `core.fact_game` in the warehouse,
  joined on calendar day plus a strong shared token in both team names. The
  Hawai'i apostrophe broke that join; alias added in `match_greenline_books.py`.
- NAVY@FAU had no `market_over_under` in the Greenline capture. Line taken from
  the under list captured at the same time (58.5).

Each row in `greenline_graded.csv` carries `score_source` and `line_source`.

**Data.** 49 Greenline total flags for week 2 (39 under, 10 over); 36 of the
unders are the positive-edge list. Games of 2026-09-11/12.

## Results

The 36-pick under list:

| segment | record | win% | units | ROI |
|---|---|---:|---:|---:|
| all 36 | 21-15 | 58.3% | +4.09u | +11.4% |
| top 10 by PFF edge | 4-6 | 40.0% | -2.36u | -23.6% |
| band <45 | 1-1 | | | |
| band 45-49.5 | 3-5 | | | |
| band 50-54.5 | 4-6 | | | |
| band 55-59.5 | 11-3 | 78.6% | +7.00u | +50.0% |
| band 60-64.5 | 1-0 | | | |
| band 65+ | 1-0 | | | |

All 49 flags (script output):

| segment | record | win% | units | ROI |
|---|---|---:|---:|---:|
| all | 27-22 | 55.1% | +2.55u | +5.2% |
| under | 22-17 | 56.4% | +3.00u | +7.7% |
| over | 5-5 | 50.0% | -0.45u | -4.5% |

By PFF's own value bucket (unders): <2% 2-3, 2-3% 4-2, 3-4% 13-6, 4%+ 3-6.

Projection accuracy (n=49): PFF projection MAE 10.54 vs market line MAE 10.68;
PFF closer in 28 of 49. Mean error +0.50 for PFF, -0.36 for the market, so the
slate landed roughly on the market number and slightly over PFF's.

## What this does and does not support

- 21-15 is a profitable week but the 95% interval on 36 picks runs about 42% to
  73%. Break-even (52.4%) sits inside it. One week decides nothing.
- The 55-59.5 band carried the whole result (11-3); every other band was at or
  below .500. That matches the direction of your own 2023-2025 under history in
  that band (50-32) but is 14 games, not evidence.
- PFF's ranking did not order the picks: the ten highest edges went 4-6 and the
  4%+ bucket went 3-6. Do not size by PFF's `value` yet.
- PFF's projection was not more accurate than the market line this week (MAE
  10.54 vs 10.68, closer in 28/49). The under tilt is not coming from a better
  total number.
- Lines are PFF's shown number at capture, not what a book offered. A repriced
  grade (via `match_greenline_books.py`) would move some results.

## Reproduce

```
python scripts/pull_pff_scoreboard.py --season 2026
python research/totals/scripts/grade_greenline.py --week 2
```

Pool weeks with `--all` once more captures exist.

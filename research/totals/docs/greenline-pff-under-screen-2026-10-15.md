# Nineteen PFF team stats against every Greenline under, three eras: nothing survives

2026-10-15

## Question

Which team-level PFF stats, if any, separate the Greenline unders that win from the ones that
lose, well enough to filter bets? The registered test
([pff under filters](greenline-pff-under-filters-2026-09-28.md)) asked this of five features
on 2026 alone, because `stg.pff_*` then started at 2025. PFF now reaches back to 2014, so the
2020 and 2022-23 eras can join, and this screen asks the wider question on all three.

## Answer

**No PFF stat survives.** Of nineteen, none reaches the pre-set bar (discovery BH q < 0.10),
so nothing went to the 2026 holdout as a candidate. Pooled over all 402 unders, the best is
offensive yards after contact per carry (BH q 0.11, Holm 0.11). It is the one lead worth
registering, and it is not a filter yet.

The registered five-feature test, rerun on 2026 weeks 2-7 (n=230), is still null: smallest
Holm p 0.239 (`run_heavy`, still pointing the wrong way, 22-36).

## Method

Script: [`pff_under_screen.py`](../scripts/pff_under_screen.py). Nineteen features were
declared in the script before any result was seen.

- **Sample.** Every graded Greenline under from `under_filters.greenline_unders()`: 2020
  PFF_hist (117 with PFF profiles), 2022-23 exports (56), 2026 flags weeks 2-7 (229; graded
  2026-10-15 with `grade_greenline.py --week 2 ... --week 7`). Personal 2023-25 unders are
  excluded, per the unit rule.
- **Outcome.** Cover margin, the capture line minus the actual total, in points. Positive
  means the under won by that much. A continuous margin carries more information than
  win/loss. The win/loss split is reported beside it.
- **Features.** Team-level ratios of PFF sums: passing (grade, YPA, depth of target, big-time
  throw rate, turnover-worthy rate, sack rate), offensive shape (pass rate, plays per game),
  rushing (run grade, explosive-run rate, yards after contact per carry), blocking grades,
  and defense (pressure rate, pass-rush, coverage and run-defense grades, run-stop rate,
  missed-tackle rate). Each game's value is the mean of the two offenses, or the two
  defenses.
- **No lookahead.** A team's profile pools last season's regular season with this season's
  games strictly before the game's CFBD week. Early in the year the profile is mostly last
  season; later it is mostly this one. 99.3% of PFF team-weeks fall on a CFBD game week for
  the same team, so the strict `<` window cannot see the game itself.
- **Test.** For each feature, OLS of the margin on the feature (z-scored within era) with
  era fixed effects. Standard errors are clustered by slate date, and p-values use a t with
  G−1 degrees of freedom.
- **Discovery and holdout.** The screen runs on 2020 + 2022-23 (n=173). Benjamini-Hochberg q
  and Holm p are taken across all nineteen. A candidate needs discovery q < 0.10 before it
  is scored once on 2026 (n=229). Caveat: five related features were already seen on 2026
  weeks 2-4 in the registered run.
- **Trial count.** 19 in the screen, plus 1 market-wide follow-up (below) = 20.

## Numbers

Slopes are points of cover margin per 1 SD of the feature (+ favours the under).

| feature | discovery slope | disc. p | disc. q | 2026 slope | 2026 p | pooled slope | pooled p | pooled q |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| off_yco | −2.70 ± 1.16 | 0.024 | 0.456 | −1.65 ± 0.89 | 0.084 | −2.11 | 0.006 | 0.111 |
| off_pass_rate | +1.51 ± 1.36 | 0.272 | 0.886 | +1.55 ± 1.20 | 0.215 | +1.53 | 0.088 | 0.556 |
| off_adot | −1.18 ± 1.06 | 0.273 | 0.886 | +2.11 ± 0.72 | 0.010 | +0.70 | 0.305 | 0.882 |
| off_run_grade | −0.68 ± 1.49 | 0.649 | 0.886 | −2.49 ± 0.77 | 0.005 | −1.71 | 0.026 | 0.249 |
| (15 others) | | ≥ 0.37 | ≥ 0.886 | | | | ≥ 0.26 | ≥ 0.88 |

The full table is in the script's output (`--csv`). Discovery and 2026 slopes have the same
sign on only **8 of 19** features, which is what noise gives.

**The one lead: yards after contact.** When both offenses break tackles well, the unders
lose. Split into within-era thirds:

| YCO third | n | under win% | mean margin |
| --- | ---: | ---: | ---: |
| low | 135 | 59.3% (80-55) | +3.8 |
| mid | 133 | 52.6% (70-63) | +0.6 |
| high | 134 | 46.3% (62-72) | −2.4 |

The ordering holds in each era (2020 64/59/46%, 2022-23 58/56/53%, 2026 57/49/45%).

**It is not a market-wide mispricing.** As a single follow-up trial, the same feature was
tested against the close-minus-actual residual on every FBS regular-season game with a
REST-backed close, weeks 2-14 of 2015-2026 (`--market off_yco`). The slope is +0.06 ± 0.21
points per SD over 6,056 games (p 0.79). Under win% by third is 50.9 / 50.5 / 50.4. If the
YCO effect is real, it lives inside Greenline's flags, for example a PFF projection that
under-weights a good run game, and not in the market. That story is untested.

## What this does not support

- **Not a filter.** YCO missed the discovery bar (q 0.456) and its pooled q 0.11 comes from
  the same rows that picked it out. Dropping the top third would have kept 150-118 (56.0%)
  across eras and 81-72 (52.9%) in 2026. Both numbers are measured after looking.
- **Not `off_run_grade` or `off_adot`.** Each is strong in 2026 alone (p 0.005, 0.010) and
  absent or reversed in discovery. A holdout-only effect is what twenty tries produce.
- **Not that PFF stats are useless for totals.** This asks only whether they rank PFF's
  own under flags. The market-wide grade tests are in
  [pff-grade-residual-tests](pff-grade-residual-tests-2026-09-22.md).
- **Not a reason to keep screening.** A second wider screen of the same 402 rows costs
  multiplicity and buys nothing (findings row E).

## Next

If YCO is worth anything it has to show up prospectively. A registration would read:
from 2026 week 8 on, compare under flags where the two offenses' pooled YCO is in the
within-season top third against the rest, using the margin slope as the test. Detecting a
2-point-per-SD slope at 80% power needs a standard error near 0.7. The 2026 rows give 0.89
at n=229, which scales to about 350 new graded unders, or roughly the rest of this regular
season.

## Reproduce

```
python research/totals/scripts/grade_greenline.py --week 2 --week 3 --week 4 --week 5 --week 6 --week 7
python research/totals/scripts/pff_under_filters.py
python research/totals/scripts/pff_under_screen.py --csv data/exports/pff_under_screen.csv
python research/totals/scripts/pff_under_screen.py --market off_yco
```

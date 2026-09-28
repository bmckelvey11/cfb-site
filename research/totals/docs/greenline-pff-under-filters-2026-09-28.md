# Team-level PFF stats as filters on Greenline unders — first run, null

2026-09-28

## Question

Open question F in [greenline-findings](greenline-findings.md): do team-level PFF stats pick
out the Greenline unders that win? Five features were registered on 2026-09-22 in
`pff_under_filters.py`, before any result was seen, behind a power gate (MDE ≤ 65%). At n=88
the gate failed and the search did not run. With week 4 graded, n=136 and the gate opens.

## Answer

**No feature survives Holm.** The smallest adjusted p is 0.337 (`run_heavy`). Every
feature's own detection floor is 72–75%, so this rules out only very large effects.

## Method

As registered, unchanged: each feature requires **both** relevant teams on the under side of
the FBS median, CMH test from `under_filters.py`'s harness (one era here, so it reduces to a
single 2×2), Holm across all five.

Features are built from the **2025 full regular season** (weeks 0-14) for both teams, not
2026 season-to-date. That is the registered construction for 2026 rows, not a fallback:
132 of 136 rows used it and 4 had no PFF match. The script's stated reason ("PFF 2026 is
loaded through week 2") is now dated, but changing the window after seeing results would
be a second look, not a correction.

## Data

2026 Greenline under flags, weeks 2-4, graded at the capture line (`greenline_graded.csv`,
2026-09-28). 70-66 (51.5%, Wilson 43–60%). Pooled MDE 63.0% against a 52.38% break-even.
The 2020 and 2022-23 eras cannot join: `stg.pff_*` begins at 2025.

## Numbers

| feature | on | off | CMH p | Holm p | MDE on |
| --- | --- | --- | ---: | ---: | ---: |
| pass_rush | 21-18 | 47-46 | 0.876 | 1.000 | 72% |
| run_heavy | 11-20 | 57-44 | 0.067 | 0.337 | 75% |
| no_deep | 13-18 | 55-46 | 0.312 | 1.000 | 75% |
| weak_qb | 17-14 | 51-50 | 0.828 | 1.000 | 75% |
| coverage | 20-16 | 48-48 | 0.710 | 1.000 | 73% |

## What this does not support

- **Not that these features are useless.** At 72–75% floors on the kept side, only a filter
  hitting three-quarters of its games could have shown up.
- **Not a signal in `run_heavy`.** It points the wrong way (both offenses run-heavy went
  11-20), and 0.067 raw is 0.337 after Holm across five.
- **Not season-to-date PFF.** Every row used last season's team profile.
- **Not a reason to add a sixth feature.** The registration closes the family at five.

## Reproduce

```
python research/totals/scripts/grade_greenline.py --week 2 --week 3 --week 4
python research/totals/scripts/pff_under_filters.py
```

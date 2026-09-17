# PFF team report — Georgia Bulldogs, 2026 (sample)

Sample of what the PFF Developer API returns for one team, rendered as a readable report.
Pulled 2026-09-16 through Restish (`ci` API-key profile). **2 games played** — every
rate below rests on that sample, so denominators are printed in every row. Two blowouts also mean
deep rotation: 54 players graded on offense, 51 on defense, most of them under 30 snaps.

Endpoints: `team-summary ncaa 2026 173` (/v1, per game) and
`team-report ncaa georgia-bulldogs <report> --season 2026 --week-group REG` (/v2, per player) for
offense, defense, passing, rushing, receiving, special-teams. See [`docs/pff-cli.md`](pff-cli.md).

## Game log

Team grades, one row per game. 0-100, where 60 is roughly average.

| Wk | Opp | H/A | Score | Overall | Off | Def | Pass | Run | Pass blk | Coverage |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| 1 | TENNST | H | 63-3 | 98 | 95.2 | 92.1 | 88.2 | 93.2 | 88.6 | 80.4 |
| 2 | WKUHIL | H | 70-20 | 91.7 | 80.1 | 81.7 | 72.1 | 77.1 | 81.3 | 85.2 |

Remaining 10 scheduled games come back `locked` with null grades: wk3 ARKANS, wk4 OKLAHO, wk5 VANDYC, wk6 BAMACT, wk7 AUBURN, wk9 UFGATO, wk10 OLEMIS, wk11 MIZZOU, wk12 SOUTHC, wk13 GEOTEC.

## Quarterbacks

Source: `passing`. EPA columns are PFF's own; `npaEpa` excludes penalties, `noScreenEpa` excludes screens.

| Player | Gm | Dropbacks | Att | Cmp% | Yds | TD | INT | Grade (pass) | BTT% | TWP% | aDOT | TTT | EPA |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| Gunner Stockton | 2 | 33 | 32 | 87.5 | 436 | 8 | 0 | 86.4 | 6.1 | 0 | 6.6 | 2.34 | 1 |
| Ryan Puglisi | 2 | 19 | 18 | 50 | 128 | 1 | 0 | 72.1 | 0 | 10.5 | 10.4 | 2.54 | -0.1 |
| Ryan Montgomery | 2 | 7 | 6 | 50 | 66 | 1 | 0 | 83.6 | 16.7 | 14.3 | 7.4 | 2.5 | 0.3 |
| Hezekiah Millender | 1 | 3 | 1 | 100 | 17 | 0 | 0 | 60.4 | 0 | 0 | -1 | 4.27 | 1.1 |
| Drew Miller | 1 | 1 | 1 | 0 | 0 | 0 | 0 | 55.7 | 0 | 100 | — | 3.8 | -1.5 |

BTT = big-time throws, TWP = turnover-worthy plays, both as a share of dropbacks. TTT = average time to throw (s).

## Backfield

Source: `rushing`. Ordered by carries, not by grade - a 10-carry elusive rating swings wildly.

| Player | Gm | Att | Yds | YPA | TD | YCO | YCO/att | MTF | Brk% | Rec | Rec yds | Grade (run) |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| Bo Walker | 2 | 11 | 49 | 4.5 | 0 | 26 | 2.4 | 3 | 0 | 0 | 0 | 67.1 |
| Nate Frazier | 2 | 10 | 127 | 12.7 | 4 | 86 | 8.6 | 6 | 66.1 | 1 | 5 | 92.8 |
| Nick Peal | 2 | 10 | 46 | 4.6 | 0 | 43 | 4.3 | 5 | 0 | 0 | 0 | 86.3 |
| Jae Lamar | 2 | 6 | 26 | 4.3 | 1 | 17 | 2.8 | 3 | 0 | 0 | 0 | 61 |
| Chauncey Bowens | 2 | 5 | 28 | 5.6 | 0 | 9 | 1.8 | 1 | 64.3 | 4 | 77 | 65.5 |
| Hezekiah Millender | 2 | 5 | 23 | 4.6 | 0 | 10 | 2 | 1 | 0 | 0 | 0 | 67.6 |
| Dwight Phillips Jr. | 2 | 4 | 29 | 7.3 | 0 | 17 | 4.2 | 1 | 51.7 | 1 | 4 | 81.5 |
| Landon Roldan | 2 | 2 | 13 | 6.5 | 1 | 1 | 0.5 | 0 | 0 | 1 | 17 | 60.8 |

YCO = yards after contact. MTF = missed tackles forced. Brk% = share of yards on breakaway runs (15+).

## Receivers

Source: `receiving`. Route count is the denominator that matters - YPRR on 20 routes is noise.

| Player | Pos | Gm | Routes | Tgt | Tgt% | Rec | Yds | TD | YPRR | aDOT | YAC/rec | Slot% | Grade (route) |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| Isiah Canion | WR | 2 | 31 | 5 | 8.9 | 3 | 28 | 0 | 0.9 | 10 | 10.7 | 3.1 | 55.5 |
| Chauncey Bowens | HB | 2 | 21 | 4 | 7.1 | 4 | 77 | 1 | 3.67 | -3.5 | 22.8 | 9.5 | 82.9 |
| Talyn Taylor | WR | 2 | 17 | 5 | 8.9 | 5 | 59 | 2 | 3.47 | 4 | 8.8 | 41.2 | 83.1 |
| London Humphreys | WR | 2 | 17 | 4 | 7.1 | 2 | 11 | 1 | 0.65 | 14.3 | 4.5 | 27.8 | 54.1 |
| Jaden Reddell | TE | 2 | 17 | 2 | 3.6 | 2 | 38 | 1 | 2.24 | 12.5 | 6.5 | 45 | 74.1 |
| Tyler J. Williams | WR | 2 | 14 | 4 | 7.1 | 2 | 33 | 0 | 2.36 | 7.3 | 7 | 92.9 | 65.4 |
| Jeremy Bell | WR | 2 | 14 | 1 | 1.8 | 1 | 54 | 1 | 3.86 | 35 | 19 | 21.4 | 71.1 |
| Lawson Luckie | TE | 2 | 14 | 1 | 1.8 | 1 | 4 | 0 | 0.29 | 1 | 3 | 41.2 | 53.5 |
| Sacovie White-Helton | WR | 2 | 13 | 4 | 7.1 | 4 | 104 | 1 | 8 | 3.8 | 22.3 | 76.9 | 82.7 |
| Craig Dandridge | WR | 2 | 12 | 5 | 8.9 | 4 | 92 | 0 | 7.67 | 14.8 | 5.8 | 100 | 85.3 |

## Offensive line

Source: `offense`, linemen only, ordered by snaps.

| Player | Pos | Snaps | Pass blk snaps | Run blk snaps | Grade (pass blk) | Grade (run blk) | Pen |
| --- | --- | --- | --- | --- | --- | --- | --- |
| Ekene Ogboko | T | 89 | 47 | 42 | 62.7 | 74.2 | 0 |
| Zykie Helton | G | 73 | 44 | 29 | 72.5 | 60.5 | 0 |
| Jahzare Jackson | T | 56 | 31 | 25 | 84.4 | 79.1 | 0 |
| Drew Bobo | C | 53 | 35 | 18 | 69.2 | 71.2 | 0 |
| Dontrell Glover | G | 52 | 30 | 22 | 83.5 | 69.2 | 1 |
| Juan Gaston | T | 46 | 28 | 18 | 82.8 | 74.6 | 0 |
| Marcus Harrison | G | 45 | 19 | 26 | 84.8 | 63.5 | 0 |
| Daniel Calhoun | T | 41 | 20 | 21 | 84.1 | 60.1 | 1 |
| Michael Uini | G | 40 | 17 | 23 | 81.2 | 68 | 0 |
| Malachi Toliver | C | 38 | 19 | 19 | 72.8 | 66.6 | 1 |

## Defense

Source: `defense`, 20+ snaps, ordered by snaps. Nobody is past 60 snaps this season.

| Player | Pos | Gm | Snaps | Rush | Cov | Tkl | Stops | MT | Prs | Sk | Grade | Run def | Coverage | Pass rush |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| Tyriq Green | S | 2 | 68 | 0 | 38 | 2 | 0 | 0 | 0 | 0 | 57.2 | 59.5 | 56.3 | — |
| Braylon Conley | CB | 2 | 57 | 1 | 32 | 2 | 2 | 0 | 1 | 0 | 74.3 | 69.3 | 70.9 | 65.4 |
| Blake Stewart | CB | 2 | 55 | 5 | 24 | 2 | 0 | 1 | 2 | 0 | 62.5 | 58.3 | 56 | 86.9 |
| Rasean Dinkins | S | 2 | 48 | 0 | 22 | 2 | 0 | 0 | 0 | 0 | 64.8 | 71 | 60.8 | — |
| Chris Cole | LB | 2 | 45 | 16 | 13 | 3 | 3 | 0 | 3 | 0 | 90.3 | 83.9 | 71.8 | 83.8 |
| Khalil Barnes | CB | 2 | 43 | 1 | 30 | 0 | 0 | 0 | 0 | 0 | 63.4 | 62.5 | 63 | 60 |
| KJ Bolden | S | 2 | 43 | 0 | 32 | 2 | 1 | 0 | 0 | 0 | 68.8 | 68.1 | 67 | — |
| Gentry Williams | CB | 2 | 40 | 0 | 23 | 1 | 1 | 0 | 0 | 0 | 69.5 | 70 | 67.2 | — |
| Demello Jones | CB | 2 | 40 | 0 | 23 | 1 | 1 | 0 | 0 | 0 | 79.8 | 70.6 | 83.2 | — |
| Todd Robinson | S | 2 | 39 | 0 | 20 | 4 | 2 | 0 | 0 | 0 | 71.1 | 73.3 | 67.4 | — |
| Zayden Walker | LB | 2 | 38 | 10 | 15 | 2 | 1 | 1 | 2 | 0 | 69.7 | 61.3 | 63.5 | 75.6 |
| Terrell Foster | LB | 2 | 37 | 3 | 15 | 7 | 4 | 1 | 1 | 0 | 89.9 | 80.2 | 87.3 | 55.9 |
| Ellis Robinson IV | CB | 2 | 37 | 0 | 21 | 4 | 1 | 0 | 0 | 0 | 73.5 | 62.5 | 73.3 | — |
| Caden Harris | CB | 2 | 36 | 0 | 17 | 0 | 0 | 0 | 0 | 0 | 70.6 | 62.9 | 70.6 | — |

Prs = total pressures (hurries + hits + sacks). MT = missed tackles.

## Special teams

Source: `special-teams`. Specialists only; 72 rows in the raw table once coverage units are included.

| Player | Pos | Snaps | FG/XP | Kickoff | Punt | Long snap | Kick ret | Punt ret | Misc ST |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| Peyton Woodring | K | 35 | 72.2 | 81.8 | — | — | — | — | 61.7 |
| Will Snellings | LS | 25 | — | — | — | 79.5 | — | — | 63.5 |
| Tyriq Green | S | 18 | — | — | — | — | 82.7 | — | 61.4 |
| Sacovie White-Helton | WR | 16 | — | — | — | — | 61.8 | 50.1 | 60.4 |
| Craig Dandridge | WR | 7 | — | — | — | — | — | 65 | 60 |
| Drew Miller | P | 6 | — | — | 63 | — | — | — | 60.3 |
| Harran Zureikat | K | 6 | 60 | 67.8 | — | — | — | — | 60 |
| Bo Walker | HB | 2 | — | — | — | — | 58 | — | 60 |

## What this does not support

- **Two games.** Nothing here separates a player from the sample. Frazier's elusive rating is 469 on
  10 carries; over 145 carries in 2025 it was 74.5. Treat every rate as provisional until ~4 games.
- **Opponent quality is not adjusted.** Tennessee State (FCS) and Western Kentucky, both at home, both
  blowouts. PFF grades are play-by-play judgments, not strength-adjusted.
- **Grades are a result of the game.** Using these as pre-game features means rolling earlier weeks only -
  see the no-lookahead rule in the root `CLAUDE.md`.
- **`team-summary` and `team-report` cover different scopes once a postseason exists.** `team-summary` has
  no `--week-group` and returns every game; these `team-report` pulls are `REG`. For 2026 to date they
  agree because there is no postseason yet. For 2025 they do not.
- **This is not the warehouse path.** `pull_pff_modeling.py --team-reports` no longer pulls `team-report`
  (`TEAM_REPORTS = ()`, dropped 2026-09-10 as redundant with the weekly leaderboards). This sample came
  from direct Restish calls and nothing was written under `data/`.

## Reproduce

```bash
export PFF_API=$(grep -E '^PFF_API=' env.env | cut -d= -f2- | tr -d '\r')
restish pff team-summary ncaa 2026 173 -p ci -o json --rsh-print b > team_summary_2026.json
for rep in offense defense passing rushing receiving special-teams; do
  restish pff team-report ncaa georgia-bulldogs $rep --season 2026 --week-group REG \
    -p ci -o json --rsh-print b > report_$rep.json
  sleep 0.7
done
```

Franchise id 173 and slug `georgia-bulldogs` come from `team-directory ncaa --season 2026`.

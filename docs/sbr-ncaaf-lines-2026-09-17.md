# Pre-2013 lines from the Sportsbook Reviews Online archive — 2026-09-17

**Reproduce:** `python scripts/scrape_sbr_ncaaf_lines.py`
**Out:** `{CFB_DATA_ROOT}/ingest/sbr_ncaaf_lines.csv` (5,497 games, not committed)

## The question

`core.fact_game_line` is empty before 2013 — CFBD's floor, not a pull gap
([cfbd-lines-coverage-2026-09-17.md](cfbd-lines-coverage-2026-09-17.md)). The Prediction
Tracker tape covers 2001–2012 but carries spreads only, never an over/under
([pre-2013-lines-sources-2026-09-17.md](pre-2013-lines-sources-2026-09-17.md)). Can the
Sportsbook Reviews Online archive supply pre-2013 **totals and moneylines**, and is the
result trustworthy?

## Answer

Yes for 2007–2012. 4,652 games in the gap plus 845 in 2013 as a validation season, each
carrying an opening and closing spread, an opening and closing total, both moneylines and
a second-half line, joined to a CFBD `game_id`.

| season | pairs | matched | unmatched | collisions | ML disagrees |
| ---: | ---: | ---: | ---: | ---: | ---: |
| 2007 | 712 | 712 | 0 | 109 | 1 |
| 2008 | 718 | 717 | 1 | 105 | 7 |
| 2009 | 769 | 769 | 0 | 123 | 8 |
| 2010 | 808 | 808 | 0 | 139 | 5 |
| 2011 | 812 | 811 | 1 | 136 | 8 |
| 2012 | 837 | 835 | 1 | 134 | 3 |
| 2013 | 846 | 845 | 1 | 127 | 3 |

Parsing was clean: **0 dropped rows** across all seven seasons, **1** rotation-number
discontinuity (2009), **1** unparseable pair (2012), **5** games unmatched to CFBD.

## Method

Each season is one HTML table, two rows per game (`V`/`H`, or `N`/`N` for bowls), columns
`Date, Rot, VH, Team, 1st, 2nd, 3rd, 4th, Final, Open, Close, ML, 2H`. Three problems had
to be solved; each solution is a claim that the validation below tests.

**1. Which row is the spread and which is the total.** Nothing in the markup says.

The moneyline looks like the answer — the favourite is priced negative and carries the
spread — and it is right on the great majority of pairs. It is *not* reliable: SBR
transposes the two moneylines on some games. 2009 Boise State at Louisiana Tech lists the
winning favourite at `+1150` and the losing home underdog at `-850`, which sends an
ML-led rule to the wrong row and yields a "spread" of 52 against a "total" of 20.5.

**Magnitude is the rule used instead**: a football total (~30–90) always exceeds its
spread. It is correct on every pair inspected, including the ML-transposed one. A
plausibility guard catches the residual case where a large spread meets a low total, and
the moneyline is retained as an independent cross-check whose disagreements are counted
(`ml_disagrees`, 1–8 per season) rather than hidden.

The guard's spread ceiling is **70, not 50**. Twenty-three rows are genuine FBS-vs-FCS
blowouts past 50 — Florida State −67.5 over Savannah State in 2012, final 55–0; Oklahoma
State −58 over Savannah State, final 84–0. A ceiling of 50 rejects real data.

**2. Orientation.** SBR writes the spread as a positive number on the favourite's row;
this repo wants it negative when CFBD's home team is favoured. Names cannot decide this:
string similarity picks the wrong side of Florida / Florida International and Miami /
Miami (OH), precisely the ambiguous pairs. **Scores decide it instead** — the favourite's
`Final` is compared against CFBD's `home_points`, which is exact whenever the two scores
differ. This resolved 100% of matched games (5,497/5,497); the `VH` flag and name
similarity are coded as fallbacks for tied games and never fired.

**3. The CFBD join.** `(season, unordered score pair, date ± 1 day)` against `stg.game`,
with normalized team names breaking ties. The date allowance is needed because SBR dates
by kickoff and CFBD by UTC start. Collisions are real and frequent — 105–139 per season,
so roughly one game in six shares a season, date and score with another, and **names are
load-bearing, not decorative**. Dates are `MMDD` with no leading zero; a month ≤ 7 rolls
into the following calendar year, which is how January bowls are placed.

## Validation

The check is against the Prediction Tracker spread on the same `game_id`, 5,037 shared
games. These are two independent market snapshots, so exact agreement is not the test —
books close half a point apart routinely. A defect would appear as a non-zero bias, a fat
tail, or sign disagreement.

| season | n | bias | median \|diff\| | within 2.0 | sign flips | neutral bias |
| ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| 2007 | 712 | −0.056 | 0.50 | 96.8% | 7 | +0.203 |
| 2008 | 717 | −0.066 | 0.50 | 95.7% | 5 | −0.160 |
| 2009 | 713 | −0.074 | 0.50 | 96.9% | 1 | −0.574 |
| 2010 | 717 | −0.042 | 0.50 | 96.2% | 3 | +0.107 |
| 2011 | 714 | −0.034 | 0.50 | 95.2% | 8 | −0.037 |
| 2012 | 728 | −0.003 | 0.50 | 96.0% | 4 | +0.029 |
| 2013 | 736 | −0.052 | 0.50 | 95.8% | 1 | +0.235 |

**Overall: bias −0.047, median |diff| 0.50, 96.1% within 2 points, 29 sign flips (0.6%).**
Neutral-site games were broken out separately because a flip confined to bowls would hide
inside an aggregate; their bias stays within ±0.6 and their median |diff| is 0.50 in every
season, so no neutral-specific error exists.

Two checks that do not depend on the Prediction Tracker at all:

- **Spread sign.** `corr(spread_close, home margin) = −0.717`, mean spread **−6.83**
  against mean home margin **+6.76**. That mirror is the shape the repo documents
  elsewhere (`prediction-tracker.md`: −4.75 / +4.53; `games.csv`: −6.66 / +6.65), so the
  sign convention is right.
- **Total level.** Mean closing total **54.38** against mean actual points **54.78**,
  `corr = +0.432` over 5,200 games. A total sitting 0.4 points under realised scoring is
  what a fairly priced market looks like.

## What this does not support

- **2001–2006 remains spread-only.** The archive starts at 2007. Nothing here supplies a
  total for the six earlier seasons the Prediction Tracker covers.
- **`half2_fav` / `half2_dog` are halftime prices** — post-kickoff information. They are
  carried for completeness and must be tagged `result_lookahead` and kept out of every
  pre-game feature. Nothing in this session used them.
- **The 29 sign disagreements are benign, but that is an inference.** All 29 sit at
  `|spread_close| <= 3`, and 24 of them at `<= 1.5` — near-pick-'em games where the two
  sources straddle zero and the sign carries almost no information. **None** occurs above
  3 points. So this is not a systematic orientation fault leaking into real favourites.
  What was *not* done is a per-game adjudication of which source is right on those 29, so
  the direction of the disagreement remains unattributed.
- **The moneylines were not validated.** Only the spread was checked against an
  independent source and only the total's level was sanity-checked. No per-game
  verification of `moneyline_fav` / `moneyline_dog` was performed, and SBR is known to
  transpose them.
- **Nothing was loaded into the warehouse.** This writes a CSV under `data/ingest/`,
  following the `prediction_tracker_lines.csv` precedent. Promotion into
  `core.fact_game_line` needs a `build_core` loader entry and a `provider_key` decision,
  and is still the separate task
  [pre-2013-lines-sources-2026-09-17.md](pre-2013-lines-sources-2026-09-17.md) scopes.
- **The 5 unmatched games and 1 rotation break were not chased.** They are named in the
  coverage table and left alone.

## Provenance

`robots.txt` (checked 2026-09-17) disallows only `/go/` and allows `/scoresoddsarchives/`.
Raw HTML is cached under `{CFB_DATA_ROOT}/raw/sbr/` so parser iteration does not re-hit
the site; `--refetch` forces a re-download, with a 2-second delay between pages. The
archive 404s unrecognised user agents, which is why an earlier pass in this session
wrongly recorded the site as dead.

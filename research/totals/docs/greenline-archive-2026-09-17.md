# PFF Greenline archive: parsing the 2020–2023 exports

2026-09-17

## Question

Two piles of old PFF files sat outside the repo. What Greenline history do they actually
contain, and does that history say anything about whether Greenline's picks win?

## Data

Source: `~/OneDrive/Betting/NCAA_betting/`. Parsed into one long-form CSV by
[`parse_greenline_history.py`](../scripts/parse_greenline_history.py); graded by
[`greenline_archive_review.py`](../scripts/greenline_archive_review.py).

| Source | Era | Rows in | What it carries |
| --- | --- | --- | --- |
| `PFF_hist.xlsx` | 2020 season, weeks 1–18 | 2,584 | 3 line snapshots (opening market, opening Greenline, close), cover + break-even probability per side, graded result, PFF's own CLV |
| `ncaa-best-bets*.csv` | 3 slates: 2022-09-30→10-02, 2023-10-17→22, 2023-11-02→05 | 672 | Greenline value plus public cash/ticket split. No grading. |

Output: `$CFB_DATA_ROOT/ingest/pff_scoreboard/greenline_history_archive.csv`
(8,772 rows) and `..._team_map.csv` (133 abbreviations).

Four things found in the sources that shrink them:

- **Both `PFF_hist.xlsx` sheets are byte-identical, and both are season 2020.** The tab
  labelled `2019` is a copy. There is no 2019 data in that file.
- **Two of the four `ncaa-best-bets` CSVs are md5-identical** (`(1) - Copy - Copy - Copy`
  and `(2) - Copy - Copy`). Deduplicated on content hash.
- **Every row is one side of a two-sided table.** 862 away + 862 home + 430 over + 430
  under = 2,584, and pooled `Bet Result` is exactly 1,273 W / 1,273 L. The pick has to be
  derived; see Method.
- **The `2023-week*_picks.xlsx` files are a different thing** — the user's own model
  (`game, line, pick, stake, edge, lineavg, linestd`), not Greenline — and 11 of 12 are
  OneDrive cloud stubs. Not parsed.

## Method

**Deriving the pick.** `Difference` = PFF's cover probability minus the break-even implied
by the quoted price — its own claim, not a measured edge. Verified before use: the two
sides' `Difference` sums to minus the book overround (mean −0.0459, median −0.0480, 98.1%
inside [−0.09, −0.01], against 1 − 2×110/210 = −0.0476), and **no game/market ever has two
positive sides** (0 of 1,292). So `Difference > 0` selects at most one side unambiguously.
That gives **368 picks** out of 1,292 bet-slots in 2020.

**No lookahead.** The flag comes from the **opening Greenline** snapshot, the point at
which the number existed. Selecting on the closing `Difference` yields a different and
smaller set (323 vs 368), so closing selection is result-informed. The closing block is
used only for CLV; grading happens at the opening Greenline line.

**Price-aware grading.** Hit rate is not comparable across markets: a moneyline pick on a
+135 dog breaks even at 42.6%, not 52.38%. Each split is judged against the mean
break-even of its own rows, and ROI is computed from the implied decimal price
(`payout = 1/breakeven − 1`) rather than a flat −110.

**Game matching.** `PFF_hist` has full school names and no kickoff, so it joins on
season + week + both names via `toks`/`NAME_ALIASES` from
[`match_greenline_books.py`](../scripts/match_greenline_books.py), falling back to
season + names because PFF numbers the postseason straight on (weeks 17–18) while CFBD
restarts it. The exports carry abbreviations (`BAMA`, `MST`, `M-OH`) and exact kickoffs;
rather than hand-writing a map, each abbreviation's candidates are intersected across
every kickoff it appears at and then constraint-propagated through its partner. That pins
**133/133 with no hand-written aliases**, including the collision-prone set
(`MST`=Mississippi State, `MISS`=Ole Miss, `MSU`=Michigan State, `MIZZ`=Missouri,
`M-OH`=Miami (OH)). The solved map is written beside the output to be audited.

The exports' spread sign convention was verified, not assumed: `line` on
`game_away_home_spread` is the **home** team's spread, same sign as CFBD — corr +0.994
against `core.fact_game_line.spread_close` over n=219, mean |diff| 0.80, median 0.50, 96%
within 3 points.

`game_id` attached on 8,328 of 8,772 rows. Unmatched: 16 `PFF_hist` slots (mostly
neutral-site/postseason naming) and 1 export slot (`SMU@UCF` 2022-10-02, no game within
±6h).

## Numbers

Greenline picks, 2020, **graded at the opening Greenline line** — the line in the capture,
not the close, per the unit's standing rule. `mde%` is the minimum win rate this n could
distinguish from its own break-even (one-sided, α 0.05, power 0.80).

| split | n | hit% | breakeven% | hit−be | roi% | mde% | verdict |
| --- | --- | --- | --- | --- | --- | --- | --- |
| ALL ROWS (both sides) | 2560 | 50.0 | 51.8 | −1.8 | −3.46 | 54.2 | below floor |
| picks: all | 366 | 48.4 | 47.5 | +0.9 | +2.90 | 54.0 | below floor |
| picks: moneyline | 132 | 41.7 | 40.0 | +1.7 | +6.48 | 50.6 | below floor |
| picks: spread | 104 | 49.0 | 51.8 | −2.7 | −5.24 | 64.0 | below floor |
| picks: total | 130 | 54.6 | 51.7 | +2.9 | +5.79 | 62.6 | below floor |

**Every split sits below the floor its own sample size could detect.** Consistent with
`greenline-season-review-2026-09-16.md` on the 2026 capture: nothing here is evidence in
either direction.

The all-rows row is the arithmetic identity, printed to keep it visible — 50.0% on a
mirrored table is not a result.

CLV (PFF's own, close vs its own opening number), picks only:

| market | n | mean | median | p |
| --- | --- | --- | --- | --- |
| moneyline | 132 | +0.0584 | +0.0220 | <0.0001 |
| spread | 105 | +0.0088 | +0.0040 | <0.0001 |
| total | 131 | +0.0061 | +0.0030 | <0.0001 |
| pooled | 368 | +0.0256 | +0.0060 | <0.0001 |

**The pooled CLV figure is a moneyline artifact** — 82% of the CLV mass comes from the 132
moneyline rows, one of which reaches +0.567. Excluding moneylines: n=236, mean +0.0073,
median +0.0030. Direction is consistently positive and statistically clean in all three
markets, but for spread and total the magnitude is under one point of win probability,
i.e. well inside half a point of line.

## What this does not support

- **Not an independent audit.** These are PFF's own published lines, its own cover
  probabilities and its own CLV, graded against its own opening number. It prices
  Greenline against its close, not against a book you could actually reach. Per unit
  rules, grading belongs at the line in the capture — this file has no book price in it.
- **No split clears its MDE**, so none of the above is evidence that Greenline wins or
  loses, in either direction. The ROI column is descriptive, not a projection.
- **2020 is the COVID season** — reduced and reshuffled schedule, cancellations, unusual
  home-field conditions. One season of one vendor's self-report is not a basis for sizing,
  and it should not be read as out-of-sample confirmation of anything.
- **The 2022–2023 export slates are ungraded** (no result or CLV in the source) and cover
  three slates. They contribute public cash/ticket splits and Greenline value only.
- **Relation to the κ=0.5 planning prior** (`bankroll-planning-prior-kappa-half`): this
  archive does not move it. It is the same vendor, self-reported, below floor, and from a
  season not represented in the pooled record. Treat as prior evidence at most, per the
  standing rule that the personal 2023–25 unders are not an independent sample.

## Reproduce

```bash
python research/totals/scripts/parse_greenline_history.py
python research/totals/scripts/greenline_archive_review.py
```

## Excluded deliberately

`~/OneDrive/Betting/action_network_NCAAF_model/` (`combined_csv.csv`, `week*_ML.csv`,
`week*_total.csv`, `spread/week*_spread.csv`) is **Action Network's PRO projections**
(`GRADE`, `EDGE`, `BET %`, `MONEY %`), a different vendor's model. Folding it into a file
named greenline-anything would make the record unauditable. 13 of its 16 files are also
OneDrive cloud stubs. If that vendor's record is wanted it needs its own parser and its
own write-up.

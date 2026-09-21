# The ledger system

**Question this answers:** what records a bet or a pick in this repo, which script writes
which file, and what the numbers in those files mean.

Living doc — it describes current code, so it is fixed or archived when the code changes
(root `CLAUDE.md`, docs lifecycle). Verified against the tree on 2026-09-21 at `0800020`.

There is no single ledger. There are five, split by what they record:

| | What a row is | Code | File on disk | Live? |
| --- | --- | --- | --- | --- |
| **Manual bet ledger** | a bet you placed | [`ledgers/ingest_bets.py`](../ledgers/ingest_bets.py) | `$CFB_DATA_ROOT/processed/bet_history_graded.csv` | built, never run for real |
| **Action Network betlog** | a bet from a book export | [`cfb_system_maker/betlog.py`](../cfb_system_maker/betlog.py) | `<data-dir>/betlog/bets.csv` | dormant |
| **Greenline bet log** | a PFF totals flag, and whether it got bet | [`research/bankroll/scripts/greenline_bet_log.py`](../research/bankroll/scripts/greenline_bet_log.py) | `$CFB_DATA_ROOT/ingest/pff_scoreboard/greenline_bet_log.csv` | live |
| **Over-zero pick history** | a pick the model qualified | [`models/over_zero/scripts/pick_history.py`](../models/over_zero/scripts/pick_history.py) | `$CFB_DATA_ROOT/processed/over_zero/qualified_picks_history.csv` | live |
| **Totals forward CLV ledger** | a total the model liked at bet-time | [`models/totals/clv.py`](../models/totals/clv.py) | `models/ledgers/totals_clv_ledger.jsonl` | **broken path — see below** |

The organizing distinction: the first two are **bet ledgers** (what you actually wagered),
the last two are **pick ledgers** (what a model said, graded against the close whether or
not money moved). `greenline_bet_log.py` straddles them on purpose — it exists to measure
the gap between flags produced and flags bet.

---

## 1. The manual bet ledger — `ledgers/`

The spine of the system, and the only one you type into by hand.

```
research/spread/scripts/weekly_slate.py      → processed/weekly_slate_latest.csv
  ↓  ledgers/build_slate_sheet.py
ingest/bet_history/slate_latest.csv          ← you mark `bet` = Y on rows you took
  ↓  ledgers/ingest_bets.py
processed/bet_history_graded.csv             ← game_id, opener, close, CLV, result, P&L
```

You supply eleven columns; everything else is looked up:

```
placed_at,away,home,market,side,line,odds,stake,book,source,notes
```

`python ledgers/ingest_bets.py --init` copies
[`manual_bets_template.csv`](../ledgers/manual_bets_template.csv) into place if you would
rather type a sheet from scratch than generate one.

### What it looks up

- **`game_id`** — matched on team-name tokens against games kicking off within ±7 days of
  `placed_at`, via `strong()`/`toks()` from `research/totals/scripts/match_greenline_books.py`.
  Loose on purpose: abbreviations and mascots both work if one distinctive word survives.
- **Opener and close** — from `core.fact_game_line`.
- **Result and P&L** — from `core.fact_game` points, settled by
  `spread_result` / `total_result` / `settle`.

### Conventions that are easy to invert

**`line` is the number as *you* took it**, from your side. Taking the home team at -3.5 is
`-3.5`; taking the away dog at +3.5 is `+3.5`. Totals take the total. Moneylines leave it
blank. The warehouse stores `spread_close` home-relative, so `pick_close()` flips the sign
for an away-side bet before any comparison happens.

**CLV differs by market, and positive always means the market came to you:**

| Market | CLV | Unit |
| --- | --- | --- |
| spread | `line_taken − close_on_your_side` | points |
| total | delegated to `models.totals.clv.clv_points` — `close − line` for OVER, `line − close` for UNDER | points |
| moneyline | `implied(close) − implied(taken)` | probability |

Spread and total CLV are both points and comparable to each other. **Moneyline CLV is a
probability and is not comparable to either** — that is what the `clv_unit` column is for,
and `report()` groups by it rather than pooling.

**`close_source` says whose close was used.** Your book when the warehouse carries it,
otherwise the median across providers, labelled `median(n providers)`. A median-derived CLV
is never silently presented as your book's number; the report prints how many rows fell
back.

### What it will not tell you

- **No CLV before 2023.** `core.fact_game_line` starts there. Older bets still get a result
  and P&L, they just carry a null `clv`.
- **Openers are thin.** Only bovada, espn bet and draftkings carry `spread_open`/`total_open`,
  so `open_line` is often null even on a matched recent game.
- **Spread only, from the slate sheet.** `weekly_slate.py`'s live book feed requests
  `markets=spreads` from the-odds-api, so a generated sheet has no total or moneyline number
  to carry. Totals and moneylines have to be hand-typed.

### Safety properties worth knowing

- **Never writes to your input file.** Output goes to a separate graded CSV.
- **Unmatched rows are reported, never dropped** — they land in the output with
  `match_status` of `unmatched` / `ambiguous` / `invalid` and a `match_note`.
- **Teams entered backwards are named, not guessed.** If `away`/`home` are swapped, the row
  reports `looks reversed: warehouse has X @ Y` rather than grading a flipped spread.
- **`build_slate_sheet.py` refuses to overwrite `slate_latest.csv`** — that file holds your
  Y/N marks and a second run would erase them. `--force` overrides; a timestamped copy is
  written every run either way.
- **The `bet` column is opt-in.** A generated sheet grades only rows marked `y`/`yes`/`1`/`true`;
  a hand-typed sheet has no such column and every row counts.

### Reproducing the sign rules

```bash
python ledgers/ingest_bets.py --self-check
```

Pins American-odds payout and implied probability, spread and total cover tests including
both pushes, push-is-not-a-loss settlement, all four CLV signs, the away-side spread flip,
and the median fallback. Passes as of 2026-09-21. Broader coverage:
`tests/test_ingest_bets.py`, `tests/test_build_slate_sheet.py` (59 tests with the betlog and
totals-CLV suites, all passing).

---

## 2. The other four

**`cfb_system_maker/betlog.py`** — imports an Action Network bet-history CSV export
(`data/ingest/bet_history/history.csv` is one such export, 2023–2025). Handles the stray
`data:text/csv;charset=utf-8,` artifact line real exports carry, keeps only
`spread_home`/`spread_away`/`over`/`under` at full-game period, and matches to CFBD games
through `team_abbreviations.resolve_team`. Driven by `python -m cfb_system_maker.cli betlog
import --csv <path>`; rendered at the Flask app's `/betlog` page. Design spec:
[`superpowers/specs/2026-08-27-clv-betlog-ingestion-design.md`](superpowers/specs/2026-08-27-clv-betlog-ingestion-design.md).
Analysis built on this export lives in [`clv-analysis.md`](clv-analysis.md) and
[`bet-history-analysis-2023-2025.md`](bet-history-analysis-2023-2025.md) — note the standing
caution that those unders are mostly Greenline flags, not independent picks.

**`research/bankroll/scripts/greenline_bet_log.py`** — one row per PFF totals flag per week,
seeded idempotently from the raw captures, marked by hand (`--mark`) or from a book export
(`--import-book`). Its point is coverage: which flags actually got bet.

> The `bet` column is **three-valued** — `y`, `n`, or blank — and **blank means NOT YET
> MARKED, not "no"**. `--coverage` refuses to compute on a week containing blanks, because
> defaulting them to "no" manufactures a 0% coverage rate, which is the exact number the
> ledger exists to measure. A week where nothing was bet is marked `n` across the board with
> `--none`; that is a real observation.

Both sides resolve to CFBD team ids before matching (PFF via `pff_schedule` +
`pff_franchise.cfbd_team_id`, the book via `core.dim_team.abbreviation`) because the two
vocabularies disagree on 32 of 137 teams. Indexed in
[`research/bankroll/docs/README.md`](../research/bankroll/docs/README.md).

**`models/over_zero/scripts/pick_history.py`** — appends every qualified pick each time the
slate runs, keyed on `(model, run_at, view, away, home)`, with a lock file so concurrent runs
cannot interleave. This is a *pick* ledger: it records what the model said and at what price
it was playable (`bet_to`), not what was wagered. ROI against it is computed walk-forward by
`models/over_zero/monitor/roi_report.py`.

**`models/totals/clv.py`** — forward CLV: `snapshot` logs a takeable total (DraftKings /
ESPN Bet only, never Bovada) at bet-time when the model's edge clears `MIN_EDGE = 3.0`;
`refresh-closes` fills `close`/`clv`/`hit` later; `summarize` reports. JSONL, one row per
game, keyed on `game_id` so a re-snapshot updates rather than duplicates.

---

## What is built but not running

Stating this plainly, because the code reads as though all five are in use:

- **`processed/bet_history_graded.csv` does not exist.** `ingest_bets.py` has never been run
  to completion against real data. `ingest/bet_history/manual_bets.csv` still holds only the
  three `EXAMPLE ROW - delete me` lines from the template.
- **A real slate sheet does exist** — `ingest/bet_history/slate_latest.csv`, 57 games from
  2026-09-18 — but with no `bet` column marked, so an ingest run would exit with
  `no rows marked bet`.
- **No `betlog/bets.csv` anywhere under the data root.** The `cfb_system_maker` betlog path
  has a parser, a CLI subcommand, a Flask page and tests, but no imported data; `/betlog`
  renders its empty state. The 2023–2025 analysis was done before this path existed.
- **The totals forward CLV ledger is orphaned by a path bug.** `DEFAULT_LEDGER` is
  `Path(__file__).resolve().parents[1] / "ledgers" / ...`. When the file was
  `cfb_totals_model/clv.py` (`4222d8b`) that resolved to repo-root `ledgers/`. Commit
  `96799f3` rehomed it to `models/totals/clv.py`, adding a directory level, so it now
  resolves to `models/ledgers/totals_clv_ledger.jsonl` — **a directory that does not exist**.
  The 113 rows at [`ledgers/totals_clv_ledger.jsonl`](../ledgers/totals_clv_ledger.jsonl) are
  the pre-move leftover: weeks 1–4 of 2026, all written in one run at
  `2026-08-27T04:36:04Z`, **zero closes filled and zero graded**. A `snapshot` today would
  create a fresh empty ledger elsewhere and never touch them. Not fixed here — fixing it is
  a decision about which path is canonical, not a doc edit.
- **`ledgers/bankroll.py` is not part of this system.** Untracked, hardcoded (20k bankroll,
  5% edge, 10 weeks), calls `plt.show()`, and overlaps `research/bankroll/` — which owns
  staking and projection per root `CLAUDE.md`. Left in place.

Live and accumulating: `greenline_bet_log.csv` (8.5 KB) and
`qualified_picks_history.csv` (344 KB, written today).

## What this doc does not establish

It describes plumbing, not skill. No ROI, hit rate or CLV figure here is a result — the
graded output the manual ledger would produce is empty, and any number eventually computed
from it is bound by [`model-evaluation-standard.md`](model-evaluation-standard.md).

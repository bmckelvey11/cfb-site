# Value sources other than beating the closing spread

The Prediction Tracker work established one narrow thing: **a panel of 154 public models cannot
beat the closing full-game spread** (50.31% ATS on 12,560 bets, p = 0.0020 *below* breakeven).
That is the hardest bar in the market and it is not the only one. This surveys what else this
repo already holds data for, ranked by strength of existing evidence.

## 1. Your own bet history already says where the value is

`docs/bet-history-analysis-2023-2025.md`, from real settled bets 2023-2025:

- **All net profit comes from totals. Spreads are a coin flip that pays juice.**
- **Key numbers are the leak.** Lines near 3 went 29-32-1 (-5.2u) and near 7 went 20-23 (-4.8u):
  combined **49-55-1, -10.0u**. Every other spread line went **77-66-2, +6.3u**.
- Plus-money moneyline dogs: 0-7, -5.8u.

This is the strongest evidence in the repo and it is empirical, not modelled. Two actionable
rules follow with no model at all: **stop betting spreads on key numbers**, and **stop betting
longshot moneylines.** Both are subtractive, which is why they are credible — they cost nothing
to adopt and the sample is your own money.

## 2. Markets the analysis never touched, already on disk

`data/raw/actionnetwork/` holds 99 full history files covering **7 books** with, per book:

| market | present | tested so far |
|---|---|---|
| full-game spread | yes | **yes — no edge** |
| total | yes | no |
| moneyline | yes | no |
| team totals (`core_bet_type_6_team_score`) | yes | no |

Every conclusion in `docs/prediction-tracker-findings.md` is about the first row only. Totals,
moneylines and team totals are untested here, and your bet history says totals is where the
profit was.

The files also carry the **full tick path** — 2,421 updates on one August game reaching back to
2 April — which is what a CLV study needs and what `cfb_totals_model/clv.py` was built for.

## 3. Line shopping — promising, not yet established

Across ~5 live books per game the closing home spread differs by a **median of 1.0 point**
(mean 0.97; 57.6% of games differ by >= 1 point, 29.3% not at all).

For scale: breakeven at -110 needs 52.38%, so the gap to a coin flip is ~2.4 points of win
rate. Moving off a key number is worth roughly 1.5-2 points of win rate. **Shopping is
plausibly comparable to the entire edge that modelling has failed to find** — and it requires
no model, only discipline about where the bet is placed. It also directly addresses the key
number leak in §1: the value of getting off 3 is exactly what shopping buys.

**Two false starts before this number, both recorded because they are the reason not to trust
it yet:**

1. First pass gave mean 2.42 points. Suspected alternate lines; there were none.
2. Real cause was **stale books**. Book 30 quotes carry `line_status = None` while live books
   read `normal` — it sat at -8.5 while six books held -6.5. Filtering to `normal` cut the mean
   from 2.42 to 0.97. My first "a full point of free value" example was that same stale book.

A residual 13.5-point maximum says the tail is still not clean, and the sample is 99 games from
one slice. **Do not act on the 1.0 figure until it is computed over the full archive with the
tail explained.**

## 4. Beat the *later* close instead of the current one

The panel beats the **opening** line by -2.615 MSE in 20 of 20 seasons. That was dismissed as
unreachable because the archive has no publication timestamps — but the constraint is
historical, not permanent. `scripts/collect_line_timing.py` now captures timestamped snapshots,
and `pt_upcoming_predictions.csv` logs every prediction against the line available at that
instant.

If predictions systematically anticipate line movement, they are tradeable at the open even
though they cannot beat the close. Week 1 says not yet:
`corr(line move, edge_vs_open) = +0.988` — the apparent edge is the move that already happened.
That correlation falling materially below 1 is the signal to watch.

## Ranking

1. **Adopt the two subtractive rules from §1 now.** No model, own-money evidence.
2. **Quantify line shopping properly** (§3) — full archive, tail explained, ATS win-rate gain
   measured against actual outcomes. Cheapest real edge on the list.
3. **Test totals and team totals** (§2) with the harness built for it. Your record says totals.
4. **Watch the CLV signal** (§4). Costs nothing; already running.
5. Full-game closing spread: **closed.** Do not reopen without new information.

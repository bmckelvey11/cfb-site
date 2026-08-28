# paper_models — Arscott (2022) censoring-bias recreation

Recreation of *"Market efficiency and censoring bias in college football
gambling"* (SSRN 4197428): the over/under line ignores that team scores are
left-censored at 0, so the **over** is underpriced when expected censoring bias
is high.

**Start here: [docs/MODEL_GUIDE.md](docs/MODEL_GUIDE.md)** — the full writeup
with figures: how the model works, the evidence, which games qualify, and the
betting playbook (filters, pricing, sizing, stop rules). Score a game with
`python monitor/score_game.py SPREAD TOTAL`.

## The strategy, for visitors

**The idea in one paragraph.** A football team cannot score fewer than zero
points. When a huge underdog is expected to score only ~5–8 points, its bad
days all get truncated to 0 while its good days run free — so its *actual*
average score sits slightly above what the betting lines imply. Both teams'
truncation effects add up in the game total, which means in exactly these
games (big spread, low total) the real combined score beats the posted
over/under more often than the market prices. Bookmakers' lines don't
correct for this; the model computes the size of the effect — the "bias
number", in points — directly from the spread and total on the board.

**The rule.** Bet the **over** on the full-game total when the bias number
exceeds **1.75**, at −120 or better. Quick screen: `(total − spread) / 2 ≤
~7.5` — the underdog's implied score. In practice: MAC paycheck road games,
FCS mismatches, service-academy matchups. About 2% of games qualify, ~30–50
bets a season.

**The evidence, honestly stated.** Walk-forward backtest (each season bet by
a model trained only on earlier seasons, 2016–2025): **64.5% win rate over
234 bets**, 95% range 58.2–70.4, against a 52.38% break-even. Plan on the
~58% lower bound — the threshold was partly chosen on this data, and the
point estimate is inflated by that selection. The band just below (bias
1.00–1.75) shows no demonstrable edge and is excluded. Nine of ten test
seasons profitable; no decay detected through 2025; the mirror-image "under"
edge was tested and refuted. Full audit trail — including the negative
results — is in the guide and `monitor/`.

**Try it:**

```bash
pip install -r requirements.txt
python monitor/score_game.py 28 40.5        # spread 28, total 40.5 -> full verdict
python monitor/review_game.py 28 40.5       # verdict + prices, sizing, sensitivity
python monitor/bias_bins.py                 # reproduce the threshold evidence
```

Live-line scoring (`v1/predict_week.py --fetch`) needs a free
[CFBD](https://collegefootballdata.com/) API key in `env.env`
(`CFBD-API = <key>`).

**This is research, not financial advice.** A few dozen bets a year, a
losing season 4–35% of the time even if the edge is fully real, and the edge
may fade as books adapt — it is published research (and now a public repo).
Read [§8 Failure modes](docs/MODEL_GUIDE.md#8-failure-modes--limits) before
staking anything, and bet only what you can afford to lose where it's legal.

## Versions

- **[v1/](v1/) — Floor Bias model** — frozen reference. Named for the mechanism:
  scores censored at the **floor** of 0 bias totals up → bet the over. Full
  recreation (Tobit, censoring bias, probit, Kelly), backtested on 13 seasons of
  real CFBD data (2013–2025). Headline as originally published: bet the over
  when expected bias > 1.0 → 56.6% win over 680 bets. **Do not edit — this is
  the baseline.** Note the *operational* bet rule has since moved to
  **bias > 1.75** (see [docs/MODEL_GUIDE.md](docs/MODEL_GUIDE.md) §3): the
  1.00–1.75 band shows no demonstrated edge once the bins are made disjoint.
  v1's code and numbers stay frozen as the reference implementation.

- **[v2/](v2/)** — tightens two v1 caveats: analytic (OPG) standard errors in
  place of the BFGS approximation, and dropping the favorite/underdog error
  independence assumption. Both proven immaterial on this data; v1 stands.

- **[v3/](v3/)** — tests whether the over-edge is genuinely censoring or just a
  repackaging of "low total / lopsided game." Verdict: `biasTotals` dominates
  the raw total and spread in- and out-of-sample; nothing simpler replaces it.
  v1's single-feature rule is the best line-only strategy.

## Extensions & sibling models

- **[floor_bias_1h/](floor_bias_1h/)** — Floor Bias extended to **first-half**
  totals. Theory predicts a stronger over edge (1H censoring bias ~2.3× larger,
  underdog shutouts 3.9× more common). Ready to run: approximation mode now,
  true backtest the moment real 1H lines are supplied (`--half-lines`). Approx
  results show the edge survives de-biasing the 1H scoring excess.

- **[saturation_bias/](saturation_bias/)** — the ceiling-side mirror: does the
  theory extend to betting the **under** via a soft scoring ceiling? **Negative
  result.** The ceiling isn't identifiable (no pile-up at the top), the fitted
  relationship runs the wrong way, and no OOS under strategy survives. The
  censoring asymmetry is real: floor → over edge, no symmetric under edge.

- **[monitor/](monitor/)** — operational truth tools: the **edge-decay
  monitor** (per-season and trailing-window probit slope + win% with CIs,
  trend test — no decay through 2025) and the **walk-forward backtest**
  (train on seasons ≤ t−1, bet season t: 56.83% over 681 bets, Wilson 95%
  lower bound above breakeven — the deployable-protocol check behind v1's
  headline).

Run instructions are in each version's README.

## Data dependency

Scripts read CFBD data from the local `data/` folder (`data/raw/games_{season}.json`,
`data/raw/lines_{season}.json`, `data/processed/games.csv`) — a copy of the
same files produced by the sibling `cfb-site` repo's scraper. To refresh with
newer seasons, re-run `python -m cfb_system_maker scrape --season ...` from
`cfb-site` and copy the updated `games_*.json`/`lines_*.json`/`games.csv` into
this repo's `data/`. `v1/run_on_project_data.py` also accepts an explicit
`--csv` path if your layout differs.

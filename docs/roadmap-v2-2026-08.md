# Roadmap v2 — Features & Fixes (2026-08-26)

Successor planning doc to [bet-labs-parity-plan.md](bet-labs-parity-plan.md) (v1.0, shipped 2026-07-20).
Inputs: competitive survey of 11 system-builder/betting tools (2026-08-26, summarized in §1),
codebase inventory (435 tests, 53-feature registry, 5.2 GB raw data), and the seven-doc
analysis arc under `docs/` whose conclusion reframes the whole product:

> **The edge found in 344 real bets is CLV (+0.29 pts, p=0.0023), not game selection.**
> Blanket unders, seasonal timing, and stat angles are dead or priced
> ([clv-analysis.md](clv-analysis.md), [seasonal-totals-backtest.md](seasonal-totals-backtest.md)).
> The product measures game selection exhaustively and CLV not at all.

That inversion drives the milestone order below: season-readiness fixes first (season starts
~2026-08-29), then CLV/bet-tracking as the flagship milestone, then finance-grade result
metrics, then the weekly-loop features, then differentiators.

---

## 1. Competitive landscape (what other system builders do)

Surveyed: Action Labs (ex-Bet Labs), BetQL, Unabated, OddsJam/OddsShopper, Outlier.bet,
Props.cash, Rithmm, Pikkit/Betstamp, Cleat Street, KillerSports SDQL, plus TrendSpider/
QuantConnect for finance backtesting UX.

Key market facts:

- **Nobody in the sports space ships real statistical validation.** Wilson CI / permutation p /
  holdout / BH correction is already this project's moat; market norm is raw record + ROI with
  a docs-page warning about small samples.
- **The trackers (Pikkit, Betstamp, OddsJam) made CLV the product.** Auto-CLV per bet vs
  Pinnacle/consensus close, CLV% over time, expected (CLV-implied) profit next to actual
  profit, dual-baseline (your book's close vs best-available close).
- **Action Labs' retention loop is "system matches today" alerts** — saved systems scan the
  slate, matches surface on the odds board + email/push. That is the feature that converts a
  backtester into a daily-use product.
- **Finance tools ship result depth sports tools don't**: equity curve + max drawdown,
  in-sample vs out-of-sample columns, parameter sweeps, bet-by-bet drill-down.
- **Rithmm/Cleat Street angles**: prompt→model creation; verified live record per published
  system (backtest frozen at save date, everything after tracked separately).
- **Outlier's UI grammar**: traffic-light green/yellow/red cells on hit-rate tables, split
  chips that recompute instantly.

Feature matrix and full per-product notes preserved in the survey; the "worth stealing"
shortlist is folded into the milestones below.

---

## 2. Milestone v1.1 — Season Readiness & Debt (target: this week; season starts ~08-29)

Small, mostly-known items. Everything here is either already due or newly-armed by v1.0 code.

| # | Item | Why now | Shape |
|---|------|---------|-------|
| 1.1 | **Merge `fix/web-app-review-2026-08-26`** | 26 review-fix commits sitting ready; season needs them live | PR → master |
| 1.2 | **Commit the 7 analysis docs** + record `20260826-register-player-success-rate-endpoints` quick task in STATE.md | Uncommitted findings are the basis of this roadmap; bookkeeping drift | docs commit + STATE.md row |
| 1.3 | **Live in-season verifications** (deferred at v1.0 close, due ~08-29): Current Matches shows real unplayed games with posted lines; feature-filtered systems match via season-to-date stats | The two `human_needed` items blocking honest v1.0 closure | Run `upcoming` pipeline week 1, verify dashboard panel |
| 1.4 | **Hide Duplicates** (parity-plan step 11) | No longer YAGNI: `d9c93e4` made total systems match either side — the self-collision condition it was deferred on | When one `game_id` yields two candidate bets, drop the game; toggle like fade |
| 1.5 | **Close T-01-03**: `describe()` silently drops feature filters whose `(op, control)` combo it can't render while `feature_ok()` still applies them | Accepted risk from Phase 1, flagged "close before combos multiply"; registry now 53 features / 8 groups | Fallback sentence (`"<label> matches <op> <value>"`) so no active filter is ever invisible |
| 1.6 | **Bundled example system: neutral-site + indoor unders** | The one lead surviving the analysis arc (63.3% over 109 games, p=0.014, era-stable) and all three needed features (`neutralSite`, `gameIndoors`, `venue_dome`) already registered | Add to Example Systems tab; becomes the natural first paper-tracked system in v1.2 |

Done when: branch merged, week-1 Current Matches verified live, 1.4/1.5 tested, STATE.md clean.

---

## 3. Milestone v1.2 — CLV & Bet Tracking (the flagship)

Rationale: five of seven analysis docs converge on CLV as the real, measured edge; the closing
lines have been sitting in `data/raw/lines_*.json` all along (36,735 rows, 12 providers); and
the strongest competitor tools (Pikkit, Betstamp, OddsJam) are built on exactly this. Today the
product has **no bet-log ingestion path and no CLV surface at all** — analysis ran off a manual
`~/Downloads/history.csv` plus a 114-entry AN→CFBD abbreviation map living in a scratchpad.

| # | Item | Shape |
|---|------|-------|
| 2.1 | **Bet-log ingestion** | `betlog` CLI subcommand: import Action Network history CSV → `data/betlog/bets.csv` (own file, no `GameRecord` schema change — the `upcoming.csv` pattern). Promote the AN→CFBD team-abbreviation map to a first-class module + test. Join bets to `game_id` by date+teams. |
| 2.2 | **CLV computation** | For each joined bet: bet number vs consensus closing number from `lines_*.json` → CLV in points; convert to cents/implied-prob where sensible. Pure function in `backtest.py` style, heavily tested. |
| 2.3 | **CLV surfaces** | Bet-log page: per-bet CLV column (traffic-light), aggregate CLV with the same stats treatment as hit rate (t-stat, per-season split); CLV-over-time chart beside money-won. "Expected profit (CLV-implied) vs actual" — the Pikkit/Betstamp framing. |
| 2.4 | **Live record per saved system** (Cleat Street pattern) | Freeze `saved_at` (already in JSON); bets/matches after save date grade into a separate "live record" shown next to the backtest record. Honest forward-test built into every system card. |
| 2.5 | **Paper tracking of system matches** | When Current Matches flags a game, snapshot (system, game, line, timestamp) to a matches log; grade after results land; CLV-grade against close. Turns every saved system into a self-verifying forward test with zero manual effort. |
| 2.6 | **Dual-baseline CLV** (Betstamp refinement, stretch) | CLV vs consensus close *and* vs best-available close across the 12 providers already in raw lines. |

Done when: import → join → CLV → page renders for the real 502-bet history; week-N system
matches auto-accumulate a graded paper-track log.

---

## 4. Milestone v1.3 — Finance-Grade Results Depth

Cheap, high-credibility additions; all compute from data already in `BacktestResult`.

| # | Item | Shape |
|---|------|-------|
| 3.1 | **Max drawdown + longest losing streak** | From the existing ordered `bet_details` running sum; two chips + shaded drawdown region on the money-won chart. Absent from every sports competitor. |
| 3.2 | **In-sample vs holdout columns in the header** | Holdout split already exists — surface it by default as side-by-side chips ("2013–22: 56.1%, +41u · holdout 23–25: 54.2%, +9u"), QuantConnect-style. |
| 3.3 | **Year-over-year consistency strip** | Per-season mini record/ROI sparkline row under the chips; flag "profitable in N of M seasons" (Bet Labs doctrine, already computed in `season_breakdown`). |
| 3.4 | **Traffic-light table grammar** | Green/yellow/red ROI cells in modal value tables and per-season tables, **gated by Wilson CI so small samples render grey** — makes the stats stack visible instead of buried. |
| 3.5 | **Bet-by-bet drill-down upgrade** | Past Matches gains: filter values at bet time, running units column, CSV export. |
| 3.6 | **Export everywhere** | No `send_file`/download exists anywhere today. CSV export for bet details, per-season breakdown, compare table; JSON export of a saved system. |
| 3.7 | **Surface `/search-runs/`** | Orphan route today (no inbound links, `data/search_runs/` empty). Add index page listing runs + dashboard link; run one real beam search to populate. |

---

## 5. Milestone v1.4 — The Weekly Loop (alerts, lines, shopping)

Converts research into game-day action. Sequenced after v1.2 because alerts without CLV
grading just reproduce the game-selection trap the analysis arc closed.

| # | Item | Shape |
|---|------|-------|
| 4.1 | **Match alerts** | Scheduled `upcoming` refresh + digest of new system matches. v1: CLI command emitting a summary (cron/Task Scheduler); v2: email. Show fetch timestamp + line-moved caveat (parity-plan 13 note). |
| 4.2 | **Line shopping surface** | 12 providers already in raw lines; `filter_providers` exists. New per-game view: each book's number vs consensus, best-available highlighted. Directly serves the CLV finding ("the edge is timing and number-hunting"). |
| 4.3 | **"Shop this game" filter** | From [stat-angles-retest.md](stat-angles-retest.md): GBM disagreement (+3.68% ROI walk-forward, p=0.025) as a *shopping filter*, not a bet trigger — flag which upcoming games are worth hunting numbers on. Requires `v1_fit.json` model path productionized. |
| 4.4 | **Alternate-line / teaser records** (DASH-04, descoped from v1.0) | Re-grade matched bets at spread ±6/6.5/7/10 via parameterized `grade_bet`; popover off the Record chip. Partial decisions preserved in 05-CONTEXT.md. |
| 4.5 | **Outcome distribution view** (Unabated pattern, stretch) | For a system or matched game: histogram of historical margins/totals of matched games, not just cover %. Helps totals systems most. |

---

## 6. Milestone v1.5 — Differentiators (pick opportunistically)

| # | Item | Notes |
|---|------|-------|
| 5.1 | **System-as-text** | Serialize filters to a compact readable string (SDQL-inspired); `describe()` already renders sentences. Makes systems copy/paste-shareable; future-proofs any sharing surface. |
| 5.2 | **NL theory → prefilled filters** | "Describe your angle" box mapping to registry filters via LLM; narration infra (`/narrate-run`, Anthropic client) already exists. Fits the `theory` field. |
| 5.3 | **Parameter sweep helper** | Filter-detail scatter already shows per-value ROI; add best-contiguous-range highlight + one-click "set filter to this range" (TrendSpider pattern). Guard with the overfit sub-score so it doesn't become an overfitting machine. |
| 5.4 | **Moneyline bet type** | Third `bet_type`; deferred in v1.0 until spread/total UX settled — it now is. Needs moneyline prices from lines data + ML grading path. |
| 5.5 | **Held data pulls** (REMINDERS.md) | `gamePlayerStat` GraphQL remaining seasons; `advanced_box_score`, `win_probability`, `player_season_overview` REST opt-ins. Only pull when a registry feature needs them. |

Explicitly still deferred (unchanged from v1.0): Think Tank multi-user sharing, widget/embed,
public-betting-% filters (no CFBD source).

---

## 7. Fixes & debt register (standalone, any time)

| Item | Severity | Notes |
|------|----------|-------|
| `describe()` silent filter drop (T-01-03) | High-trust | Scheduled as 1.5 |
| Hide Duplicates now reachable via either-side totals | Correctness | Scheduled as 1.4 |
| `filter_modal.js` tested only by source-contract grep (58 KB, most complex UI surface) | Coverage ceiling | Add a thin browser smoke pass (Playwright/preview) over open→edit→save→chips; keep contract tests |
| No export path anywhere | Gap | Scheduled as 3.6 |
| `/search-runs/` orphan route, empty data dir | Gap | Scheduled as 3.7 |
| Action Network client ships but persists nothing | Gap | Subsumed by 2.1 bet-log ingestion |
| Quick-task bookkeeping drift (`dd871dd` landed, unrecorded) | Hygiene | Scheduled as 1.2 |

---

## 8. Sequencing summary

```
v1.1 Season Readiness   ── this week (hard date: season ~08-29)
v1.2 CLV & Bet Tracking ── September; flagship; unblocks honest forward-testing all season
v1.3 Results Depth      ── can interleave with v1.2 (disjoint files: chips/templates vs betlog)
v1.4 Weekly Loop        ── mid-season; alerts + line shopping compound with v1.2's CLV grading
v1.5 Differentiators    ── opportunistic
```

Positioning note from the survey: market clusters at $20–30/mo (consumer research), $80–100
(serious tools), $150–250 (pro EV/simulation). A CFB-only backtester with real statistical
validation + today-matching + honest CLV would be credible at the $20–30 slot — nothing at
that price does honest backtesting. Not a goal yet; a fact worth keeping.

Next formal step: start the milestone via `/gsd-new-milestone` using §2 (v1.1) as the
requirements seed.

# Next-Steps Roadmap (post Phase 2)

**Goal:** Prioritized queue of next development items for cfb_system_maker. Each item, when picked, gets its own TDD implementation plan (`docs/superpowers/plans/`) before any code.

**Objective (from project summary):** Extend the web app so betting systems can filter on the broader CFBD dataset already scraped to `data/raw/` (REST, 61 endpoints) and `data/graphql/` (Hasura tables) — weather, betting-line extras (opening spread/total, moneylines), pregame Elo/win-prob, neutral site, conference game, returning production, team talent, recruiting, coach/venue/conference metadata — and make the resulting systems statistically trustworthy (item 2).

**Inputs:** project summary prompt (2026-07-16), phase-2 plan (complete per handoff), `.remember/remember.md`, CLAUDE.md, live `data/` inspection.

**Current state (verified 2026-07-16):** Phase 1 + 2 shipped: registry/enrich/feature-filters, running as-of-week stats, SystemStats + streaks, save/load, coverage %, `_meta`/stale warning, `/compare`. Data is lopsided: `games_*.json` spans 1992–2025 and `lines_*.json` 2020–2024, but most enrichment sources (ppa_games, pregame_win_prob, weather, rankings, sp/elo/fpi/srs, talent, recruiting, advanced stats, teams_ats) exist for **2023 only**. GraphQL base tables are pulled (incl. poll/pollRank). `data/systems/` is empty — `/compare` has nothing to compare until some systems are saved (user workflow, not a dev item).

**Locked decisions (already made — do not relitigate; canonical text in the summary doc):**

1. **No lookahead bias.** Season-final snapshots (FPI, SP+, season Elo/records/ATS/PPA, adjustedTeamMetrics) stay out as filters unless computed as running/entering-game or as-of-week values. Post-game outcome fields (havoc, attendance) allowed only inside the fenced "result stats (lookahead — analysis only)" group.
2. **Generic feature layer.** Declarative registry (`features.py`) — one `FeatureDef` per field (key, label, group, source, join, control, team_scoped, validate, null_policy, lookahead_safe). Adding a field = one registry row, zero new filter code. Enriched values ride the `features.json` sidecar with `_meta`; `GameRecord`/`games.csv` frozen. Nulls fail closed.
3. **Side perspectives.** Team-scoped values stored `home_*`/`away_*`. Spread bets: home/away/bet_side/opponent. Totals: home/away/either. Saved systems store base key + perspective (not resolved).
4. **One filter loop** for both spread and over/under (`bet_type`-aware perspective resolution).
5. **`SystemStats` pure stdlib:** break-even rate, edge, Wilson 95% CI, one-sided z/p, ROI std error/t-stat, streaks, low_sample flag (<30 decided).
6. **Save/load:** `data/systems/{name}.json`, web save-as + load dropdown, CLI `--save/--load`.
7. **YAGNI cuts stay cut:** LOOKAHEAD_POLICY.md + CI script, `--incremental` enrich, tags, duplicate_system, min/max odds stats, avg/sum perspectives, `between` op, hypothesis dep.

Nothing below reopens these. The summary's "still open (phase 2+)" list maps 1:1 onto items 4–8 below (CLI filters=4, Kelly=5, weekly snapshots=6, CLV=7, gamePlayerStat=8).

---

## Ranked items

### 1. Complete + align data coverage (2020–2024 backbone)

- **Goal:** Every registry feature has data for every season that has betting lines (2020–2024), so backtests run on ~5 seasons instead of effectively one.
- **Why first:** Cheapest item on the list and it multiplies the value of everything already built — today a filter on ppa/weather/rankings silently fail-closes to near-zero matches outside 2023 (coverage % already exposes this). Also the stated unblock condition for the held gamePlayerStat pull.
- **Scope:** No new code expected. Run `scrape --season 2020 2021 2022 2024` (resume-by-default skips what exists), rerun `build` + `enrich` across seasons, spot-check coverage % per season in the web UI. Possible small fix if an endpoint 400s for old seasons (registry already tolerates per-endpoint errors).
- **Done when:** For each 2020–2024 season, key pregame features (weather temp, ppa running, pregame win prob) show **≥80% coverage** in the UI, and `features.json` `_meta.game_count` matches `games.csv` row count. Any season/feature below the 80% floor is excluded from downstream items (2, 6, 8) rather than silently included — record the exclusion in this doc before moving on.
- **Deps/blockers:** CFBD rate limits (delay + resume make this a long-running but hands-off pull). API tier for any Patreon-gated endpoints (already handled as recorded errors). Unblocks item 2's holdout mode and items 6/7/8. After the build/enrich rerun, run the full test suite before calling this item done.

### 2. System validation: signal vs. noise — ✅ code complete (2026-07-16)

- **Status:** All three parts shipped and merged to master (per-season breakdown/sign-consistency, permutation p-value, holdout `split_holdout` + CLI `--holdout-season` + web toggle), plan: `docs/superpowers/plans/2026-07-16-system-validation-signal-vs-noise.md`. Synthetic-data done-when criteria verified. **Reconciliation checkpoint below still open** — not closeable until item 1 lands.
- **Goal:** Answer "is this system a real edge or a data-mining artifact?" — out-of-sample and noise-robustness checks layered on the existing in-sample `SystemStats` (Wilson CI and z/p vs break-even already shipped; they can't detect overfitting).
- **Why #2:** The tool's core failure mode is manufacturing overfit systems that look significant in-sample. This gives every system a trust verdict. Two of three parts are buildable before item 1 finishes.
- **Scope (three parts, one plan):**
  - **Per-season breakdown:** split `BacktestResult.bet_details` by season, report record/ROI per season + a sign-consistency line ("profitable in 4/5 seasons"). Reuses existing grading, display-only.
  - **Permutation test:** Monte Carlo p-value — resample bet outcomes at the break-even win probability (N=1000, stdlib `random` with fixed seed for reproducibility), report where the observed ROI falls in the noise distribution.
  - **Holdout evaluation:** evaluate a saved system restricted to seasons excluded during discovery (CLI `--holdout-season`, web toggle; `/compare` shows in-sample vs holdout columns side by side).
- **Done when:** Synthetic-data tests prove **both directions**: an injected-edge dataset passes (low permutation p, consistent season signs, holdout ROI within CI of in-sample) and a pure-noise dataset is flagged (high p, flipping seasons, holdout collapse). Web stats panel shows per-season table + permutation p; low_sample styling reused for warnings.
- **Deps:** Item 1 for holdout/per-season to mean anything (one enriched season = no out-of-sample). Permutation test and the code for all three parts are data-independent — plan and build now, validate against real multi-season data after item 1. **Reconciliation checkpoint (blocking):** once item 1 lands, rerun per-season/holdout/permutation against real item-1 output before marking item 2 done; a mismatch vs. the synthetic-data behavior blocks completion, not an implicit follow-on.
- **Out of scope until asked:** multiple-comparisons correction across the many filter combos a user tries (garden of forking paths). Real issue; a caveat line in the UI copy at most, own item if ever.

### 3. As-of-week poll rank features

- **Goal:** Filter on AP/Coaches rank entering the game — `home_rank`, `away_rank`, ranked/unranked — with all four spread perspectives ("unranked bet-side vs top-10 opponent").
- **Why #3:** Classic, high-signal system dimension; genuinely pregame so it passes the no-lookahead rule via a `(season, week, team)` join with zero new compute layer; data is already local (`rankings_{season}.json` REST + `poll`/`pollRank` GraphQL).
- **Scope:** New source kind `raw_rankings` + small nested index builder in `enrich.py` (rankings file nests weeks → polls → ranks), 2–3 registry rows (`team_scoped=True`, group `pregame`). One perspective-aware enrich test with a synthetic rankings file.
- **Done when:** Enrich test proves week-N game uses the week-N poll (published pregame) and unranked teams resolve `None` (fail closed); filter usable in web UI.
- **Deps:** Item 1 for multi-season rankings files (feature works on 2023 alone, so can start before item 1 finishes).

### 4. CLI dynamic feature filters (open item)

- **Goal:** Parity with the web UI: repeatable `backtest --feature KEY:PERSPECTIVE:OP:VALUE` flag mapping straight to `FeatureFilter`, enabling scripted parameter sweeps.
- **Scope:** `cli.py` arg parsing + validation against `FEATURE_BY_KEY` (unknown key/op → argparse error), pass-through to existing `SystemFilter.feature_filters`. CLI smoke test over sample data.
- **Done when:** `python -m cfb_system_maker backtest --feature venue_dome::eq:true …` matches what the web UI returns for the same filter.
- **Deps:** None.

### 5. Kelly staking readout (open item)

- **Goal:** Display-only Kelly fraction on `SystemStats` (from hit rate + American odds; clamp to 0 when edge ≤ 0), shown in CLI `print_result` and the web stats panel.
- **Scope:** One formula + field with default in `models.SystemStats`, computation in `compute_system_stats`, two output lines. Pure stdlib. Unit tests incl. negative-edge → 0.0 and the low_sample flag caveat (Kelly on 20 bets is noise — label it).
- **Done when:** Tests pass; stats panel shows "Kelly %" with low-sample warning styling reused.
- **Deps:** None. Deliberately excludes bet-sizing simulation (YAGNI until asked). Pairs naturally with item 2 — Kelly output should carry the same trust caveats validation produces.

### 6. Weekly season-snapshot ratings (open item: Elo as-of-week)

- **Goal:** Unlock the deferred season-snapshot family from locked decision 1 as entering-week values, honoring the no-lookahead rule. Elo first (weekly API param confirmed-ish, verify); SP+/FPI only if weekly variants exist; adjustedTeamMetrics likely stays season-final → remains fenced. Season records/ATS/PPA are already superseded by the running-stats layer — no snapshot needed.
- **Scope:** Scraper change — Elo endpoint accepts `week`, so pull `elo_{season}_wk{n}` snapshots (pattern exists: `season_week` mode). Enrich join `(team, season, week)` where a game in week N reads the snapshot **entering** week N. Registry rows in `season_to_date` group.
- **Done when:** No-lookahead test: a week-5 game's Elo equals the post-week-4 snapshot, never the season-final value.
- **Deps:** Item 1 (same scraping session ideally). Verify snapshot semantics against real data before trusting (spike step inside the plan).

### 7. CLV — spike first (open item)

- **Goal:** Decide whether closing-line-value is computable from available data before committing to a metric.
- **Scope (spike only):** Inspect `lines_*.json` + `gameLines` GraphQL for opening vs closing spreads per book and any timestamps. Output: one-page findings + go/no-go. If go: CLV proxy = bet line vs consensus close, added to `BetDetail`/`SystemStats` in a follow-up plan.
- **Done when:** Findings doc exists with a recommendation.
- **Deps:** None, but pointless before item 1 broadens line data.

### 8. gamePlayerStat GraphQL pull + player features (held)

- **Goal:** Heavy player-stat table pull (already built, per memory), then player-derived features (e.g., returning QB production).
- **Unblock criterion:** Item 1 complete ("base data downloaded" — the recorded hold condition).
- **Scope:** Run the existing pull; feature design gets its own brainstorm+plan (player→team aggregation is a real design question, don't improvise it).
- **Done when:** Table pulled for target seasons; separate plan written for features.
- **Deps:** Item 1, Patreon Tier 3 quota, disk (largest table).

### 9. Postgres JSONB staging layer (documented intent — deferred)

- **Goal:** CLAUDE.md names `scrapers.py` as the future load source for a Postgres staging layer.
- **Trigger to activate:** enrich becomes slow or memory-bound on multi-season data, or joins get too awkward in JSON. Until then, flat files keep winning (no dependency, no server). Re-rank after item 1 shows real multi-season enrich times.

---

## Recommended next action

**Item 1.** Single long-running `scrape` invocation for 2020–2022 + 2024, then `build`/`enrich` rebuild — no new code, unblocks the holdout half of item 2 plus items 6/7/8, and every existing feature immediately gets ~5x the sample. Start it, and write the item-2 (validation) implementation plan while it downloads — permutation test and per-season breakdown don't need the new data.

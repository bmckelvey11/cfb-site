# Master TODO — repo-wide

*Rebuilt 2026-09-10 — ported from `golf-master`'s TODO.md system (see
[`docs/methodology/todo-system.md`](docs/methodology/todo-system.md)).
Previous content (a 5-line `Fixes` list + a folded-in `Totals model`
changelog) is migrated below, not discarded.*

*Item format (see `docs/methodology/todo-system.md`): `- [ ] \`#slug\`
**Title** <!-- id: slug --> — what; why/done-when; where`. **Point to items
with \`#slug\`**, **to sections with \`#sec-*\`** (e.g. `#sec-totals`, not
`§3`). Expand stubs before they land. Index: `python scripts/todo_sweep.py
refs`.*

*No-lookahead gate (root `CLAUDE.md`): pre-game features use only
information available before kickoff; a result-informed feature is tagged
`result_lookahead` and quarantined in UI.*

---

## 0. NOW — this week, in order `#sec-now` <!-- section: sec-now -->

*(empty — pull the next sitting-sized item from a unit section when ready.
Soft cap ~8 open items here; `todo_sweep.py check` warns past that.)*

---

## 1. System maker — CLI, Flask UI, backtest engine (`cfb_system_maker/`) `#sec-system-maker` <!-- section: sec-system-maker -->

- [ ] `#system-maker-delete-saved-systems` **Let saved systems be deleted from the web UI** <!-- id: system-maker-delete-saved-systems --> <!-- plan: needed --> — currently `SavedSystem` JSON can be created and listed but not removed; add a delete action (UI button + route) that removes a saved system's JSON and updates the list view. **Done when** a saved system can be deleted from `/system` without editing files by hand. **Where:** `web.py` (`create_app`, `/system` route), wherever `SavedSystem` JSON is persisted. Migrated 2026-09-10 from the old `TODO.md` "Fixes" list.
  - Original note also said "better management of the systems" beyond just delete — that half was never specified. If there's more to it (rename, duplicate, bulk-clear), say so and this item can be split or expanded; don't infer scope here.

---

## 2. Data — warehouse, ingestion, scrapers `#sec-data` <!-- section: sec-data -->

*Cross-cutting: PFF, Action Network, odds, GraphQL, DuckDB — not owned by one unit.*

*Source-rationalization items below are the numbered steps of
[`docs/superpowers/plans/2026-09-08-warehouse-rationalization-master.md`](docs/superpowers/plans/2026-09-08-warehouse-rationalization-master.md)
§8 and run **in order** — each is gated on the one above. Step 0 (preflight)
is green: `python scripts/verify_warehouse_plan.py` exits 0. `#gql-relation-keys`
landed 2026-09-10, so the chain is open at the top and
`#warehouse-remeasure-containment` is now the gate on everything below it.*

### Source rationalization — the gated chain

- [x] ~~`#gql-relation-keys` **Give `coachSeason` and `teamTalent` relation keys, then re-scrape**~~ <!-- id: gql-relation-keys --> — done 2026-09-10 (`7d1751a`): added both to `GQL_RELATION_KEYS` (`coach` → id/firstName/lastName, `team` → teamId/school/conference; the GraphQL types are `CoachSeason`/`TeamTalent`, not the root field names) and re-scraped on the rotated key. `stg_gql.coach_season` now carries `coach_id`/`team_teamId`, `stg_gql.team_talent` carries `team_teamId` — both joinable. **Row counts unchanged** (12,564 / 2,413), so the old dumps were not short after all; the defect was joinability, not completeness. 252 coach_season and 8 team_talent rows have no team in `currentTeams` — real, not a mapping failure. Write-up: [`docs/gql-relation-keys-2026-09-10.md`](docs/gql-relation-keys-2026-09-10.md), which also records that `duckdb --only` rebuilds rather than adds. Unblocks the chain.
- [x] ~~`#warehouse-remeasure-containment` **Re-measure containment and record the buckets**~~ <!-- id: warehouse-remeasure-containment --> — done 2026-09-10: both repaired pairs re-measured against the new pull; **both stay in Bucket B**, so no drop list changes. Two substantive moves: `coach_season` now merges by **clean join** — `coach_id` became shared and `(coach_id, team_id, year)` is unique on both sides, matching 1,961/1,961 REST rows, zero unmatched — and `team_talent`'s column direction **reversed** (GraphQL holds the FK, REST only a school name), yet REST is still not droppable because 17 REST school-seasons have no GraphQL twin (Jacksonville, St. Francis (PA)). New reusable tool `scripts/audit_pair_columns.py` makes §3's hand-measured tables reproducible. Write-up: [`docs/warehouse-containment-remeasure-2026-09-10.md`](docs/warehouse-containment-remeasure-2026-09-10.md); §3 Bucket B restated in the plan. Verifier 0 failed, 875 passed.
- [x] ~~`#core-merge-bucket-c` **Merge the complementary pairs into `core`**~~ <!-- id: core-merge-bucket-c --> <!-- plan: docs/superpowers/plans/2026-09-08-warehouse-rationalization-master.md --> — done 2026-09-10: all 9 actionable pairs, in two passes. **Pass 1 (5 new tables):** full outer joins on the key, all guarded and key-unique — `core.dim_coach` 1,842 + `coach_name_conflicts` 2, `dim_draft_pick` 13,080, `dim_recruit` 93,363, `fact_team_talent` 2,430, `fact_coach_season` 12,564 + `coach_season_unmatched` 0. **Pass 2 (4 merges into existing tables)** — [`docs/core-merge-bucket-c-2026-09-10.md`](docs/core-merge-bucket-c-2026-09-10.md), `python scripts/audit_core_merges.py`: `conference` added `division` (256/256 match; `srName` fills 1/256, not carried); `game` repaired 3,714 home / 3,985 away conference ids that a non-injective name lookup had picked arbitrarily among 44 duplicate `dim_conference` names, and sent its 78,030 pre-2012 surplus to the new `core.fact_game_historical` per ADR-0001; `calendar` is a **measured no-op** (0 in-span gaps; taking its 2002–2011 rows would expand `fact_game` through `dim_week`'s bound). Every pre-existing `core` row count is unchanged, validated on a scratch copy first. Pinned by `tests/test_core_merges.py` (16). `lines` split out to `#core-fact-game-line-repoint` — it is not a merge — and closed the same day: §7's full-game match-count gate **was** exercised, rejected a repoint, and the tape landed as a union (`core.fact_game_line` 39,006 → 47,581). All 9 actionable pairs are done. `recruiting_team` stays deferred (no id↔name bridge; see `#core-dim-team`).
- [x] ~~`#core-fact-game-line-repoint` **Repoint `core.fact_game_line` at `stg_gql.game_lines`**~~ <!-- id: core-fact-game-line-repoint --> — done 2026-09-10, **as a union rather than a repoint**. §7's gate was run in both directions first and rejected the repoint: it drops 278 REST offers `game_lines` has no row for (all 2026, on `draft kings`/`bovada`/`draftkings`) and overwrites ~700 values where both sides are populated and differ. Built instead as a full outer on `(game_id, provider_key)` with `coalesce(rest, gql)` — REST wins a conflict because that is what `core` already held, so **no existing value changes** and the merge is purely additive. `core.fact_game_line` 39,006 → 47,581 (38,728 both / 8,575 gql / 278 rest), five new books (circa, fanduel, betmgm, bet365, pinnacle), `core.dim_lines_provider` 12 → 17, and the 700 conflicts preserved in `core.fact_game_line_conflicts` rather than discarded. **`game_lines` spells a missing number NaN, not NULL** — the first build coalesced 3,414 NaNs into REST NULLs and the slow suite caught it; nulled out before the join and pinned by `test_no_nan_reached_the_line_table`. `has_line` stays REST-defined, so 90 line rows on 16 games now sit under `has_line = false` (was 0) — documented, not hidden. [`docs/core-merge-bucket-c-2026-09-10.md`](docs/core-merge-bucket-c-2026-09-10.md).
- [ ] `#lines-provider-key-split` **`draft kings` and `draftkings` are one book under two keys** <!-- id: lines-provider-key-split --> — found 2026-09-10 during `#core-fact-game-line-repoint`. Both keys exist on both tapes with different counts (REST 235 / 2,693; `stg_gql.game_lines` 76 / 2,931), and the full outer on `(game_id, provider_key)` preserves the split rather than fixing it — correct for that merge, but a consumer filtering `provider_key = 'draftkings'` silently misses the other ~300. Same class as the AN book-id label fix in `duckdb_load.py`. Shape: normalize in `_provider_key` (`cfb_system_maker/duckdb_core.py`) so both collapse to one key, and check the other 16 `stg_gql.lines_provider` names for the same problem (`Caesars` / `Caesars Sportsbook (Colorado)` / `Caesars (Pennsylvania)` are the obvious next candidates — though those may be genuinely different books). Done when `core.dim_lines_provider` has one row per book and `scripts/audit_core_merges.py --merge lines` reports no core-only rows attributable to a key alias. P2
- [ ] `#lines-spread-sign-convention` **The 8,575 ActionNetwork line rows are unvalidated on spread sign** <!-- id: lines-spread-sign-convention --> — disclosed 2026-09-10 in [`docs/core-merge-bucket-c-2026-09-10.md`](docs/core-merge-bucket-c-2026-09-10.md) but not tracked. `core.fact_game_line.spread_close` is **home-relative**, matching `GameRecord` and `_build_fact_game`'s `selected_spread`. The union carried circa, fanduel, betmgm, bet365 and pinnacle in from `stg_gql.game_lines` without checking that they follow it, and `formatted_spread` is NULL on every one so the usual sanity read is unavailable. Harmless today because `eval_version_b.py` filters to specific providers, and an inverted spread on a book nobody queries is inert — it stops being inert the moment that filter widens. Shape: for each new book, compare its `spread_close` sign against the `consensus` row on the same `game_id` and against `home_points - away_points` on completed games; a book whose sign is inverted gets negated at the view in `_merge_game_lines`, not patched downstream. Done when a test in `tests/test_core_merges.py` pins the sign for all 17 providers. P2
- [ ] `#refresh-rebuilds-games-csv` **`refresh_cfbd.py` never rebuilds `games.csv`** <!-- id: refresh-rebuilds-games-csv --> — pipeline gap found 2026-09-10 while baselining the slow suite. `refresh_cfbd.py` runs scrape → flattens → `build_duckdb` → `build_core`, and nothing in that chain regenerates `data/games.csv`. It is currently 2026-09-08 01:05 against `raw/games_2026.json` at 2026-09-10 05:00, which is the sole cause of the two standing `-m slow tests/test_core_agreement.py` failures (`coverage drift: csv_only=[] sql_only=[...] (0/39)` and `assert -57.5 == -55.5`). Those two have been mistaken for regressions twice. Shape: add the CSV rebuild to `refresh_cfbd.py` after `build_duckdb`, in the same place the AN tick flatten runs. Done when a fresh `refresh_cfbd.py` pass leaves `-m slow tests/test_core_agreement.py` green. P2
- [ ] `#warehouse-drop-superseded` **Drop Bucket A's REST sides and the 7 dead columns** <!-- id: warehouse-drop-superseded --> — REST `draft_positions`, `draft_teams`, `predicted_points`, plus §5's 7-column drop list. Proof-gated by R6: the survivor must hold every populated column **and** at least as many distinct keys. No Bucket B table is dropped. Re-run the verifier before and after. P1
- [ ] `#stg-gql-collapse` **Collapse `stg_gql` into `stg`, in one commit** <!-- id: stg-gql-collapse --> <!-- plan: docs/superpowers/plans/2026-09-08-warehouse-rationalization-master.md --> — by this point the three colliders are non-duplicate so **zero suffixes are needed**. `tests/test_catalog_resolution.py` scans every `<schema>.<table>` literal in the repo, so the rename, all ~50 `stg_gql.*` literals and the test's own `ALLOW` entry move together or the suite goes red between them. Also snake-cases `stg.gameMedia` → `game_media` and `stg.gamePlayerStat` → `game_player_stat` (ADR-0003 committed to this and never assigned it). **Trap:** both names also exist as the GraphQL entity, as `raw."gamePlayerStat"`, and in dump stems — all out of scope; a blanket find-and-replace breaks the scraper. Re-count both literal sets first. P1
- [ ] `#scraper-entry-cleanup` **Remove scraper entries for dropped sources** <!-- id: scraper-entry-cleanup --> — config only, and only for sources actually dropped under R6 (R7). Done when the REST registry no longer pulls what `#warehouse-drop-superseded` deleted. P2

### PFF ingest — `docs/pff-ingest-plan.md` owns this

- [x] ~~`#pff-s5-commit` **Ship the PFF S5 loader wiring**~~ <!-- id: pff-s5-commit --> — done 2026-09-10: three commits — `94f7864` (FBS-only franchise coverage test), `6bbdd58` (S5 wiring: `cfb_system_maker/pff_schema.py`, loader jobs, `refresh_cfbd.py` reflatten, `scripts/check_pff_pin.py`, S5 worklog entry), `d80bc0d` (`jersey_number` carry-forward, 32.2% populated). 846 passed from a clean worktree at `d80bc0d`; `python scripts/check_pff_pin.py` exits 0 (21/21 tables, types ok, join ok).
- [x] ~~`#pff-s7-trim-pull` **Finish trimming the PFF pull plan against 2025**~~ <!-- id: pff-s7-trim-pull --> — done 2026-09-10: all three cuts applied, then corrected the same day in `scripts/pull_pff_modeling.py` (all 19 team reports dropped — 12 leaderboard re-cuts, `run-blocking` which `pass-blocking` dominates on 19,206 cells, and the last 6 by gate-3 decision, `team-rushing-direction` pulled once, `facet-passing-detail` pinned out); `audit_pff_pull.py` moved in lockstep. Planner delta measured at exactly −2,720 reads (3,997 → 1,277; 79 → 49 min a season, backfill 14.5 h → 9.0 h); `audit_pff_pull.py --season 2025` byte-identical to baseline, exit 0. Cost restated and the tier decision (all 19 dropped; `TEAM_REPORTS` empty not deleted, so restoring one is a one-line change) recorded in `docs/pff-ingest-plan.md`. Pinned by `tests/test_pff_audit.py`; 849 passed.
- [ ] `#pff-s6-backfill` **Backfill PFF 2014–2024 and finish 2026** <!-- id: pff-s6-backfill --> — S6. **All three gates are met as of 2026-09-10** — S3+S5 landed, S7 landed, and gate 3 (which team reports a backfill needs) is answered: **none**. The whole per-team report tier is dropped because nothing consumes it — no loader reads a `team_report_*` file and every target table in `docs/pff-warehouse-schema.md` comes from a leaderboard export. **Cost is now 9.0 h of metered calls, down from the 14.5 h originally recorded** (49 min a season × 11; 3,997 → 1,277 reads). Reversible: `TEAM_REPORTS` is an empty tuple, so restoring e.g. `pass-rush` for its `lhs_*`/`rhs_*` splits is one line plus 136 reads a season. **Held by decision 2026-09-10** — user said hold off; do not start without an explicit go. Also still blocked on `#rotate-secrets-after-compromise`: `PFF_API` was **not** part of the 2026-09-10 rotation, so nine hours of metered calls would run on a credential assumed disclosed. Done when `python scripts/audit_pff_pull.py` reports every backfilled season clean. P2 @needs-data
- [x] ~~`#pff-s8-player-tier` **Decide the PFF player tier**~~ <!-- id: pff-s8-player-tier --> — done 2026-09-10: deleted the 22-file stub (`data/raw/pff/player/`, one id, 102 K). Nothing read it — the flattener registry is leaderboard exports only and `audit_pff_pull.py` counts the tier without requiring it; the 2025 audit is unchanged apart from the tier leaving the census (4,657 → 4,637 files, 0 defects, exit 0). Re-pullable in ~15 s via `python scripts/pull_pff_modeling.py --seasons 2025 --player-ids 198077`. Recorded in `docs/pff-ingest-plan.md` S8.

### Deferred by decision — not blocking the chain

- [ ] `#core-dim-team` **Collapse the four vendor team-name maps onto one alias surface** <!-- id: core-dim-team --> — **restated 2026-09-10 against measurement** ([`docs/team-name-mapping-2026-09-10.md`](docs/team-name-mapping-2026-09-10.md), `python scripts/audit_team_name_maps.py --list`). The original premise does not hold: `core.dim_team` already exists (`cfb_system_maker/duckdb_core.py:135`), and all four consumers resolve **zero real gaps** — massey 137/137, pff 266/267, recruiting 262/268, coaches 137/137, where every residual is a school CFBD carries no team for (Chicago State, Albany, UTRGV...). `core.coach_season_unmatched` does not exist yet and is an artifact of `#core-merge-bucket-c`; the 118 multi-coach school-seasons are a grain problem, not a name one. So this is a **refactor for maintenance cost, not a data fix**: four rule sets each at 100% still cost four maintenances and a fifth vendor starts from scratch. Scope if picked up: one alias surface (CFBD `alternateNames` is collision-prone — see S4 — so it needs a rule, not a blind index) that `massey_teams`, `pff_franchise` and `OA_ALIASES` all resolve through. Done when a new vendor map is written against it without new normalize code. P3
- [x] ~~`#oddsapi-warehouse-wiring` **Wire the-odds-api snapshots into the warehouse**~~ <!-- id: oddsapi-warehouse-wiring --> — done 2026-09-10: `scripts/oddsapi_flatten.py` + `cfb_system_maker/oddsapi_schema.py` (pinned types, one name rule) → `stg.oa_odds_tick` (18,776 rows) and `stg.oa_snapshot`, resolved onto `game_id` in `core.fact_game_odds` — 98 events → 98 games, **zero NULL `game_id`**, no row multiplication. Resolution sits in `core` because `refresh_cfbd.py` flattens before it rebuilds; `_flatten_oddsapi()` added there. Design and evidence: [`docs/oddsapi-game-join-2026-09-10.md`](docs/oddsapi-game-join-2026-09-10.md) (pair first, kickoff only to split) and [`docs/oddsapi-team-name-join-2026-09-10.md`](docs/oddsapi-team-name-join-2026-09-10.md). `tests/test_oddsapi_flatten.py` pins the spreads sign convention; 873 passed.
- [ ] `#stg-camelcase-children` **Snake-case the 12 camelCase explode-child tables** <!-- id: stg-camelcase-children --> — `games__awayLineScores`, `teams__alternateNames`, `advanced_box_score__teams_cumulativePpa`, `stg_gql.game_team__lineScores` and friends; list them with `python scripts/verify_warehouse_plan.py --camel`. Requires changing how `explode_payloads` derives child names, so it is a rename touching every consumer — its own project, explicitly out of scope for the rationalization plan. The two *root* camelCase tables are not here: they ride `#stg-gql-collapse`. P2

---

## 3. Totals model (`models/totals/`) `#sec-totals` <!-- section: sec-totals -->

*Main command: `python -m models.totals backtest --line ou_open --permute`.
Cite opening totals from `ou_open`, 2022-2025 prior-season folds, `|edge| >= 0`.
Never cite leaked-era 57% / +8.82% ROI.*

### Closed (changelog — folded in from `cfb-totals-model/TODO.md` on 2026-08-28; items were already done in the source repo, migrated here 2026-09-10)

- [x] ~~Drop leaked features (havoc, attendance, contaminated winProb)~~ `#totals-drop-leaked-features` <!-- id: totals-drop-leaked-features --> — done 2026-08-28 (per source repo; no commit hash carried over)
- [x] ~~Re-grade walk-forward on the clean feature set~~ `#totals-regrade-walkforward-clean` <!-- id: totals-regrade-walkforward-clean --> — done 2026-08-28
- [x] ~~Proper score vs the line, paired, with clustered CI + MDE~~ `#totals-proper-score-paired-mde` <!-- id: totals-proper-score-paired-mde --> — done 2026-08-28
- [x] ~~Paired open-vs-close test and CLV on this model's bets~~ `#totals-open-close-clv` <!-- id: totals-open-close-clv --> — done 2026-08-28
- [x] ~~Report 2021 week-expanding separately from 2022+ prior-season folds~~ `#totals-report-2021-separate` <!-- id: totals-report-2021-separate --> — done 2026-08-28
- [x] ~~Freeze one edge threshold for the ship/no-ship number~~ `#totals-freeze-edge-threshold` <!-- id: totals-freeze-edge-threshold --> — done 2026-08-28

**Later / out of scope** (carried over verbatim, not a queue): Bovada
takeability, prices other than −110, GBM tuning, a real P(under) model,
spread model, early-week strategy, swapping in `pregame_home_win_prob`.

---

## 4. Over-zero — Arscott, saturation, floor-bias (`models/over_zero/`) `#sec-over-zero` <!-- section: sec-over-zero -->

*(empty — no dedicated pytest suite for this unit; verify changed scripts
end-to-end against local data. See `models/over_zero/CLAUDE.md`.)*

---

## 5. Spread research — closing-line prediction (`research/spread/`) `#sec-spread` <!-- section: sec-spread -->

*Preregistration order is binding — `prereg-line-movement.md` and its
amendments. See `research/spread/CLAUDE.md` and `docs/plan-2026-09-08-master.md`.*

*(empty — nothing captured yet. `docs/superpowers/plans/2026-09-08-spread-next-steps.md`
is a recent plan doc in this area; consider `/todo-from-doc` against it.)*

---

## 6. Ops / infra `#sec-ops` <!-- section: sec-ops -->

*(`.planning/` (GSD) is cross-referenced only, not merged here — see
"What stays separate" in `docs/methodology/todo-system.md`.)*

- [ ] `#rotate-secrets-after-compromise` **Rotate the five credentials still on the old keys** <!-- id: rotate-secrets-after-compromise --> — confirmed admin-level malware ran ~6 h on this machine on 2026-09-09, so every secret readable from disk or environment is assumed disclosed. **CFBD rotated 2026-09-10** (verified: `find_cfbd_token()` resolves and the GraphQL re-scrape ran on it). **Still on the old keys: MotherDuck (`md:cfb`), Backblaze B2, pCloud, `PFF_API`, `ODDS_API`.** Rotate at each provider, update `env.env` and any scheduled-task environment, then re-run one pull per source to confirm. `PFF_API` gates `#pff-s6-backfill`; `ODDS_API` feeds the 6-hourly snapshots that now load to `stg.oa_odds_tick`. Until each lands, treat an auth failure on that source as suspected rotation, not a code bug. User-run: needs provider logins. P1 @needs-user

---

## 7. Housekeeping `#sec-housekeeping` <!-- section: sec-housekeeping -->

*(empty.)*

---

## Recently completed ✓ (context) `#sec-recent` <!-- section: sec-recent -->

*(nothing graduated here yet since the port — the totals-model changelog
above stays in its home section per the graduation rule; this section is
for closed items that don't fit any unit section.)*

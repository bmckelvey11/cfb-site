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
is green: `python scripts/verify_warehouse_plan.py` exits 0. Everything from
`#gql-relation-keys` down is blocked until that one item lands.*

### Source rationalization — the gated chain

- [ ] `#gql-relation-keys` **Give `coachSeason` and `teamTalent` relation keys, then re-scrape** <!-- id: gql-relation-keys --> <!-- plan: docs/superpowers/plans/2026-09-08-warehouse-rationalization-master.md --> — add entries to `GQL_RELATION_KEYS` (`cfb_system_maker/graphql_client.py:70`, today it holds only `pollRank`) so both entities materialize their FK columns and sort on a total order; then re-scrape both to new versioned paths. Today `stg_gql.coach_season` is 12,564 rows with no coach and no team and `stg_gql.team_talent` is 2,413 rows with no team — both unjoinable, and both sort on scalars alone (`teamTalent` on `(year, talent)`), so the existing row counts may already be short. **This is the only gate on the whole chain.** User-run: hits the live CFBD GraphQL API and needs a token — rotate the CFBD key first, see `#sec-ops` (machine compromise 2026-09-09, rotation pending). P1 @needs-data <!-- verify: python -c "import sys; sys.path.insert(0,'.'); from cfb_system_maker.graphql_client import GQL_RELATION_KEYS as k; raise SystemExit(0 if {'coachSeason','teamTalent'} <= set(k) else 1)" -->
- [ ] `#warehouse-remeasure-containment` **Re-measure containment and record the buckets** <!-- id: warehouse-remeasure-containment --> — after `#gql-relation-keys`, recompute the bucket assignments for the two repaired entities from re-scraped data; `python scripts/verify_warehouse_plan.py --coverage` plus `python scripts/audit_canonical_sources.py`. Done when §3's tables are restated against the new pull and the verdicts are written into the plan. Gates every drop (R4). P1 @needs-data
- [ ] `#core-merge-bucket-c` **Merge the complementary pairs into `core`** <!-- id: core-merge-bucket-c --> <!-- plan: docs/superpowers/plans/2026-09-08-warehouse-rationalization-master.md --> — 8 Bucket C pairs plus Bucket B's 2 (neither side droppable — GraphQL carries 12–126 more seasons). **Full outer unions with R5's `_source`, never left joins**: GraphQL out-rows REST on every pair measured. Must also build `core.coach_season_unmatched` (118 school-seasons have 2–3 coaches, so the REST bridge is one-directional) and gate on the full-game line match count per §7. P1
- [ ] `#warehouse-drop-superseded` **Drop Bucket A's REST sides and the 7 dead columns** <!-- id: warehouse-drop-superseded --> — REST `draft_positions`, `draft_teams`, `predicted_points`, plus §5's 7-column drop list. Proof-gated by R6: the survivor must hold every populated column **and** at least as many distinct keys. No Bucket B table is dropped. Re-run the verifier before and after. P1
- [ ] `#stg-gql-collapse` **Collapse `stg_gql` into `stg`, in one commit** <!-- id: stg-gql-collapse --> <!-- plan: docs/superpowers/plans/2026-09-08-warehouse-rationalization-master.md --> — by this point the three colliders are non-duplicate so **zero suffixes are needed**. `tests/test_catalog_resolution.py` scans every `<schema>.<table>` literal in the repo, so the rename, all ~50 `stg_gql.*` literals and the test's own `ALLOW` entry move together or the suite goes red between them. Also snake-cases `stg.gameMedia` → `game_media` and `stg.gamePlayerStat` → `game_player_stat` (ADR-0003 committed to this and never assigned it). **Trap:** both names also exist as the GraphQL entity, as `raw."gamePlayerStat"`, and in dump stems — all out of scope; a blanket find-and-replace breaks the scraper. Re-count both literal sets first. P1
- [ ] `#scraper-entry-cleanup` **Remove scraper entries for dropped sources** <!-- id: scraper-entry-cleanup --> — config only, and only for sources actually dropped under R6 (R7). Done when the REST registry no longer pulls what `#warehouse-drop-superseded` deleted. P2

### PFF ingest — `docs/pff-ingest-plan.md` owns this

- [x] ~~`#pff-s5-commit` **Ship the PFF S5 loader wiring**~~ <!-- id: pff-s5-commit --> — done 2026-09-10: three commits — `94f7864` (FBS-only franchise coverage test), `6bbdd58` (S5 wiring: `cfb_system_maker/pff_schema.py`, loader jobs, `refresh_cfbd.py` reflatten, `scripts/check_pff_pin.py`, S5 worklog entry), `d80bc0d` (`jersey_number` carry-forward, 32.2% populated). 846 passed from a clean worktree at `d80bc0d`; `python scripts/check_pff_pin.py` exits 0 (21/21 tables, types ok, join ok).
- [x] ~~`#pff-s7-trim-pull` **Finish trimming the PFF pull plan against 2025**~~ <!-- id: pff-s7-trim-pull --> — done 2026-09-10: all three cuts applied in `scripts/pull_pff_modeling.py` (11 leaderboard-covered team reports dropped, `team-rushing-direction` pulled once, `facet-passing-detail` pinned out); `audit_pff_pull.py` moved in lockstep. Planner delta measured at exactly −1,632 reads (3,997 → 2,365; 79 → 61 min a season, backfill 14.5 h → 11.2 h); `audit_pff_pull.py --season 2025` byte-identical to baseline, exit 0. Cost restated and the tier decision (11 dropped, 8 retained pending S6 gate 3) recorded in `docs/pff-ingest-plan.md`. Pinned by `tests/test_pff_audit.py`; 849 passed.
- [ ] `#pff-s6-backfill` **Backfill PFF 2014–2024 and finish 2026** <!-- id: pff-s6-backfill --> — S6, **held deliberately**: ~14.5h of metered calls, and every unfixed inefficiency is paid eleven times. Gate is all three of S3, S5 and S7 landing. Done when `python scripts/audit_pff_pull.py` reports every backfilled season clean. P2 @needs-data
- [ ] `#pff-s8-player-tier` **Decide the PFF player tier: finish it or delete the smoke test** <!-- id: pff-s8-player-tier --> — S8, open. Either wire the player-tier pull properly or remove the stub so it stops implying coverage that does not exist. P2

### Deferred by decision — not blocking the chain

- [ ] `#core-dim-team` **Build `core.dim_team` once and collapse four consumers onto it** <!-- id: core-dim-team --> — `recruiting_team`/`recruiting_teams` is deferred purely for want of it; `stg.massey_teams` and `stg.pff_franchise` (266 of 363 mapped) each hand-maintain the same mapping; and `stg.coaches__seasons`' `seasons_school` → `teamId` is what routes rows into `core.coach_season_unmatched`. Out of scope for the rationalization plan (§12) — but it unblocks a merge and shrinks the unmatched table. P2
- [ ] `#oddsapi-warehouse-wiring` **Wire the-odds-api snapshots into the warehouse** <!-- id: oddsapi-warehouse-wiring --> — pulling on a schedule into `data/ingest/oddsapi/`, which `cfb_paths` deliberately does not glob; flatten + loader entries are deferred by choice. See `docs/oddsapi-ingest.md` *Before this loads*. Done when the snapshots land in `stg` under pinned types like PFF's do. P2
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

*(empty. `.planning/` (GSD) is cross-referenced only, not merged here — see
"What stays separate" in `docs/methodology/todo-system.md`.)*

---

## 7. Housekeeping `#sec-housekeeping` <!-- section: sec-housekeeping -->

*(empty.)*

---

## Recently completed ✓ (context) `#sec-recent` <!-- section: sec-recent -->

*(nothing graduated here yet since the port — the totals-model changelog
above stays in its home section per the graduation rule; this section is
for closed items that don't fit any unit section.)*

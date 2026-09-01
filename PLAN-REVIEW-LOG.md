# Plan Review Log: Warehouse source rationalization

Phases 0-1 (recon + interrogation) complete — plan locked with the user. MAX_ROUNDS=5.

## Phase 0 — Recon

Brownfield. Codebase reconned across the session: bidirectional pair containment measured,
scraper relation-key defect located, scaffolding-column root cause traced, and the `core`
layer's locked DDL contract plus agreement gates found. Research tier: `web` — two passes
(Hasura offset-pagination stability; DuckDB transactional DDL). `CONTEXT.md` present, so
docs-aware mode was on. No ADRs existed. Reviewer model: gpt-5.6-terra
(`~/.codex/config.toml`), codex-cli 0.151.0.

Assumptions ledger: 12 entries, confirmed in one pass.

## Phase 1 — Interrogation

Three load-bearing decisions asked one at a time; six cosmetic decisions batched.

- **D1** — merged tables land in `core`, `stg` sources stay.
- **D2** — `fact_game` gains columns, not rows; pre-1992 goes to `core.fact_game_historical`.
- **D3** — coach conforms on `coachId`; the 2 name collisions are quarantined.

Two questions were answered by measurement mid-interrogation rather than asked, per the
skill's rule that anything the data can settle should not consume a question:

- `recruitingTeam` mergeability — 3,901 of its ids are absent from `core.dim_team` (701 rows),
  so no bridge exists. Not mergeable; deferred.
- The 2.1× `stg.game` / `stg.games` row gap — history depth (1869 vs 1992), not duplication.
  Modern seasons match exactly, which is what made D2 answerable.

Docs-aware mode caught one collision the interrogation had to resolve on the spot: D1's answer
(merge into `core`) landed on an existing locked DDL contract whose recorded default is
`fact_game` = all REST `games` rows. That forced D2, which resolved it without amending the
row-count contract.

## Round 1 — Codex

Material problems remain:

- **Step 8 contradicts D1 and ADR 0001.** Plan says `stg` sources stay; step 8 says drop superseded sources. Fix: state exact objects eligible for drop; keep every `stg` source table.
- **Relation-key gate is too weak.** “Selectable” does not prove relation is singular, non-null, unique, or valid for ordering. Fix: require cardinality, null-rate, uniqueness, and stable-order tests before using relation keys.
- **`currentTeams` versus `team` is inconsistent.** Plan names both paths; one may be a list and cannot create a total row order. Fix: introspect exact field path and reject any to-many relation for identity/sort.
- **Season row counts do not prove game-level joins.** Equal counts can still hide missing, duplicate, or mismatched `gameId`s. Fix: require bidirectional `gameId` coverage, uniqueness, and value-conflict reports before widening `fact_game`.
- **“Pre-1992” is not safe join logic.** Individual modern GraphQL rows can be unmatched or duplicated. Fix: route rows by anti-join on validated `gameId`, not year boundary.
- **No rule for conflicting populated values.** `_provenance` cannot explain which source won each conflicting field. Fix: define per-column authority, conflict quarantine, and source/extract metadata.
- **GraphQL columns can leak future-informed classification into models.** Historical warning does not protect overlapping `fact_game` rows. Fix: allowlist safe fields; quarantine retroactive/result-informed fields from model inputs.
- **Coach matching is under-specified.** Exact-name collision count says nothing about aliases, blank names, unmatched REST rows, or duplicate season records. Fix: publish match-rate and unmatched reports; preserve unresolved rows with source keys and block source removal.
- **Containment gate has no formal definition.** Null handling, type normalization, duplicate keys, tolerances, and freshness are unspecified. Fix: make proof query definitions versioned and require zero unexplained differences.
- **“12 dead payload columns” are unnamed.** Review cannot verify scope or dependencies. Fix: commit approved table/column manifest plus dependent-view check before any drop.
- **Pruning is not shown as durable.** Rebuilding `stg` from raw will restore columns unless loader behavior changes. Fix: add tested loader-level pruning rule and prove second rebuild remains pruned.
- **No recovery boundary for destructive work.** DuckDB transaction does not roll back API pulls, rebuilds, or scraper removal. Fix: create versioned database backup and source manifest; retain until post-run validation succeeds.
- **No concurrency protection.** Parallel scrape/build jobs can mix raw versions or replace tables under readers. Fix: use exclusive warehouse lock and build into versioned tables before atomic swap.
- **No way to separate pagination repair from upstream change.** Row count alone is inadequate. Fix: record API schema hash, pull timestamps, identity-set diffs, duplicates, and changed-row samples.
- **Naming-plan dependency is not pinned.** This plan can run against wrong table names or partial rename state. Fix: make naming migration version an explicit preflight requirement.

VERDICT: REVISE

### Claude's response

**Accepted (13).** Rewrote the Approach around them and added four new sections.

- *Step 8 contradicted D1/ADR 0001* — the sharpest finding. The plan said `stg` sources stay and
  then said drop superseded sources. Added "What may be dropped", which scopes D1 to pairs being
  conformed into `core` and limits drops to sides with zero populated exclusive columns.
- *Result-informed columns leaking into `fact_game`* — the most serious. Verified against the
  warehouse: of the ten GraphQL-only columns, six are post-kickoff (`homeEndElo`, `awayEndElo`,
  `homePostgameWinProb`, `awayPostgameWinProb`, `excitement`, `status`). Widening `fact_game`
  with them untagged would breach the repo's no-lookahead rule. Added an explicit allowlist; the
  six are tagged `result_lookahead` per the existing mechanism at `features.py:15`.
- *Relation-key gate too weak* + *`currentTeams` vs `team` inconsistent* — merged into step 1,
  which now requires the relation be to-one and rejects to-many outright.
- *Season counts do not prove game-level joins* — correct; equal counts hide id mismatches. Added
  step 6, bidirectional key coverage and a value-conflict report, gating conformance.
- *"Pre-1992" is not safe join logic* — step 7 now routes by anti-join on validated `gameId`.
- *No conflicting-value rule* — step 6 requires per-column authority before conforming.
- *Coach matching under-specified* — step 7 publishes match-rate and unmatched-rows reports.
- *Containment gate undefined* — added the formal gate (normalization, populated-only, zero
  tolerance, freshness).
- *12 dead columns unnamed* — manifest inlined, with the 2026 exclusions stated.
- *No recovery boundary* — step 0 snapshots the DB and dump manifest, retained through step 9.
- *Pagination repair indistinguishable from upstream change* — step 3 now uses identity-set
  diffs with schema hash and pull timestamps.
- *Naming dependency not pinned* — step 0 asserts a complete rename and aborts on partial state.

**Partially accepted (1).** *Pruning not durable* — the mechanism was already loader-level
(`prune_null_scaffolding` inside `_finish_stg_table`), so a rebuild re-prunes by construction;
Codex missed that. Took the useful half: step 4 now rebuilds twice and asserts the pruned set is
identical.

**Rejected (1).** *No concurrency protection — exclusive lock, versioned tables, atomic swap.*
This is a single-user local DuckDB file on one workstation, and DuckDB already enforces
single-writer access. Lock management and atomic-swap machinery is warehouse-scale tooling for a
problem this deployment does not have. Recorded as a stated constraint instead.

## Round 2 — Codex

Prior gaps fixed: rename preflight, source-retention rule, durable pruning, named payload drops, join/conflict checks, snapshots, anti-join history routing.

Material gaps remain:

- **Containment gate checks columns, not rows.** Strict column subset can still lose unmatched entity rows. Fix: require candidate key-set coverage and aligned per-key value equality before drop.
- **No full pair inventory.** Plan never names 13 pairs, join keys, target `core` tables, Bucket C membership, or per-column authority. Fix: add executable pair manifest; each pair gets source names, grain, identity, target, authority, disposition.
- **Relation test does not prove root-row ordering.** Relation key unique “within relation” does not prove combined `orderBy` tuple unique across root rows. Fix: test root-level composite sort tuple for non-null uniqueness before pagination.
- **“Tagged” `fact_game` columns have no enforcement path.** Existing `result_lookahead` grouping applies to feature registry, not arbitrary warehouse columns. Fix: add warehouse-column metadata and block tagged columns from every model-building query.
- **Raw GraphQL evidence is not backed up.** Manifest records changed files but cannot restore overwritten re-scrapes. Fix: copy/hash-address old JSON files, or write repaired pulls to new versioned paths until validation passes.
- **Step 3 assumes additions-without-removals proves pagination repair.** Offset pagination against changing upstream data cannot establish that from two live pulls. Fix: retain page-level key logs and rerun same pull; require stable repeated identity set before proceeding.
- **Plan still mixes post-rename and pre-rename names.** Preflight requires `gql_` table names, but dead-column list and decisions use `stg.gameWeather`, `stg.coachSeason`, and `stg.game`. Fix: replace every source reference with post-migration canonical names.

VERDICT: REVISE

### Claude's response

**All seven accepted.** One taken further than proposed.

- *Containment gate checks columns, not rows* — correct and material. A strict column subset can
  still hold entity rows its partner lacks. The gate now has four conditions, not one: column
  coverage, **key coverage by anti-join**, value agreement, and freshness. Checked the concrete
  case while fixing it: `gql_draft_position` (31) vs `draft_positions` (29) have identical `name`
  sets in both directions, so that delta is duplicate rows rather than missing coverage — added
  as assumption 12 so the next reader does not re-derive it.
- *No full pair inventory* — added the 13-row pair manifest with source names, join key, target
  `core` table, and prior disposition. Marked the two whose disposition steps 1-3 are expected to
  change, so nobody carries the stale verdict forward.
- *Relation test does not prove root-row ordering* — right, and the distinction matters:
  uniqueness within the relation says nothing about two root rows sharing a coach, team, and
  season. Step 1 now requires the full root-level `orderBy` tuple be non-null and unique.
- *Tagged `fact_game` columns have no enforcement path* — the sharpest finding of this round, and
  verified: `result_lookahead` is a `FeatureDef` group in the feature registry, with
  `pregame_win_prob` already registered there as contaminated. It is not warehouse metadata, so a
  tag on a `core` column is inert against `SELECT *`. **Went further than the proposed fix**:
  rather than adding a metadata layer and blocking queries against it, the six post-kickoff
  columns are physically separated into `core.fact_game_postgame`. Physical separation cannot be
  forgotten by a future query author; metadata can.
- *Raw GraphQL evidence not backed up* — a manifest records what changed but cannot restore an
  overwritten pull. Step 0 now content-hashes the existing dumps and step 3 writes re-scrapes to
  new versioned paths.
- *Step 3 cannot prove pagination repair from two live pulls* — correct. Added a repeat-pull
  stability check: the same pull must produce an identical identity set before any diff against
  the old pull is interpreted.
- *Plan mixes post-rename and pre-rename names* — a real internal inconsistency, since step 0
  demands a completed rename. Every `stg` reference is now post-migration, including the dead-
  column manifest (`stg.gql_game_weather.windGust`, `stg.gql_recruit.overallRank`,
  `stg.gql_poll_type.abbreviation`); REST-sourced names such as `stg.plays` and `stg.team_stats`
  are unchanged by the rename and stay as they were. The Assumptions section is explicitly
  labelled as measured under pre-rename names, since that is when the measurements were taken.

## Round 3 — Codex

Prior blockers addressed: naming consistent; raw pull backup added; root sort uniqueness added; pair manifest added; postgame data physically separated; row coverage added.

Material flaws:

- **`lines` join rule impossible.** Manifest says `gameId` one-to-many; step 6 requires key uniqueness on both sides. Fix: define line-grain composite key, likely `gameId` plus provider/timestamp/market fields, then test uniqueness there.
- **Coach merge loses grain.** REST has 1,936 rows but only 405 names; mapping names to `coachId` cannot make it fit `dim_coach` without collapsing records. Fix: define REST row grain and create separate coach-season/history target, or keep REST outside merge.
- **Drop gate ignores duplicate multiplicity.** Draft-position rows differ 31 vs 29 while name sets match; key-set checks can still delete distinct duplicate records. Fix: compare normalized full-row multisets with `EXCEPT ALL`, or explicitly deduplicate under documented business rule.
- **Postgame isolation has no proof.** “Never joined by feature-building code” is assertion, not gate. Fix: add test scanning feature-build SQL/code and prove output never contains `_postgame` fields.
- **Conflict authority lacks value-preservation rule.** Declaring source authority can silently discard disagreeing populated values. Fix: retain non-authoritative conflicting value in source-specific audit table with key, both values, authority reason.

VERDICT: REVISE

### Claude's response

**All five accepted.** Two changed the plan's shape rather than its wording.

- *`lines` join rule impossible* — a genuine internal contradiction: the manifest declared
  one-to-many while step 6 demanded uniqueness on both sides. Measured the real grains:
  `gql_game_lines` is unique on `(gameId, linesProviderId, period)` (63,293 of 63,293, across
  13,743 games); `lines` is unique on `gameId` (15,384 of 15,384) with per-book offers nested.
  Step 6 now checks uniqueness at each side's own grain, never at a shared one.
- *Coach merge loses grain* — correct, and it refines a decision the user had already locked.
  `coaches` is unique on `(firstName, lastName, season)` — 1,935 of 1,936 — so it is coach-season
  grain and would have collapsed ~4.8 rows per coach into `dim_coach`. D3's ruling is untouched
  (`coachId` is identity; the 2 collisions are quarantined); its *target* moved. `gql_coach`
  alone builds `core.dim_coach`; `coaches` conforms with `gql_coach_season` and `coach_seasons`
  into `core.fact_coach_season`. Flagged for the user at Resolution because it touches a locked
  decision.
- *Drop gate ignores duplicate multiplicity* — right that a distinct-key anti-join passes when
  one side holds duplicate records the other lacks. Gate now uses `EXCEPT ALL` over normalized
  shared columns. Ran it on the concrete case: `draft_positions EXCEPT ALL gql_draft_position`
  returns 0 and the reverse returns 2, so REST is a strict multiset subset and the drop is safe —
  which the weaker check could not have established.
- *Postgame isolation has no proof* — "never joined" was an assertion. It now ships with a test
  that scans the feature-building modules for `fact_game_postgame` and the six column names and
  asserts the built feature frame contains none, with registered `result_lookahead` features
  allowed by exception.
- *Conflict authority lacks value preservation* — declaring authority now writes the losing value
  to `core.value_conflicts` with the key, both values, both source tables, and the reason. A
  silently overwritten value is indistinguishable from a bug later.

## Round 4 — Codex

Prior blockers addressed: lines grain recognized; coach dimension split; duplicate-safe drop proof added; conflict audit table added; postgame isolation gate added.

Material gaps remain:

- **Lines cannot merge at separate grains.** `gql_game_lines` rows and nested REST `lines` offers need one shared exploded shape before `core.fact_game_line` can exist. “Own grain” proves uniqueness, not correspondence. Fix: define REST-list explode, shared composite key, unmatched-offer handling, per-column authority.
- **Coach-season key regressed.** Prior plan used `(coachId, teamId, season)`; latest manifest drops `teamId` despite step 1 repairing it. A coach can have multiple team assignments in one season. Fix: retain `teamId` in coach-season grain, prove composite uniqueness, quarantine duplicate assignments.
- **Known REST coach duplicate has no handling.** `coaches` is only 1,935/1,936 unique at stated season grain, so step 6 fails before merge. Fix: identify duplicate pair; require byte-identical deduplication or preserve both in conflict/quarantine table.
- **Postgame test can miss derived leakage.** Static reference scan misses a helper/view that derives renamed pregame output from postgame data. Fix: add mutation test: alter only `_postgame` values, rebuild features, require byte-identical pregame feature output.
- **Versioned pull loading unspecified.** Plan writes new raw paths but does not state loader manifest/path selection or promotion transaction. Fix: make loader consume explicit version manifest; promote version only after all gates pass.

VERDICT: REVISE

### Claude's response

**All five accepted.** Two were resolved by finding the answer already existed in the warehouse.

- *Lines cannot merge at separate grains* — correct that "own grain" proves uniqueness, not
  correspondence. The explode Codex asked for already exists: `stg.lines__lines`, produced by
  `explode_stg_lists()`, 38,689 rows unique on `(gameId, lines_provider)`. Added a Lines
  correspondence section: REST offers come from that child table, the id↔name mismatch bridges
  through `core.dim_lines_provider`, the shared key is `(gameId, provider_key, period)` with REST
  treated as full-game, and unmatched offers are retained with single-source `_provenance` rather
  than dropped.
- *Coach-season key regressed* — right that dropping `teamId` was a regression, and right for a
  reason worth stating: `coach_seasons` contains a genuine coach-season spanning two distinct
  `team_id`s, so `(coachId, season)` would silently collapse a real mid-season team change.
  `teamId` restored to the key.
- *Known REST coach duplicate has no handling* — identified it: **Blake Anderson, 2021, two
  byte-identical rows** (same `hireDate`, same `_source_file`). It deduplicates with `DISTINCT`
  and needs no quarantine. Documented as verified rather than assumed — a non-identical pair
  would route to `core.value_conflicts` instead. Note this is a separate issue from the `teamId`
  finding above, which they resembled but were not.
- *Postgame test can miss derived leakage* — the strongest suggestion of the round. A static
  reference scan cannot catch a helper that derives a renamed pregame column from postgame data.
  Added a mutation gate: perturb only `_postgame` values, rebuild features, require byte-identical
  pregame output. Leakage of any shape changes the output, so the test catches it by construction
  rather than by enumeration.
- *Versioned pull loading unspecified* — the loader now reads an explicit version manifest naming
  which dump each entity loads from, never globbing a directory holding two generations. The new
  version is promoted only after steps 5-7 pass, so a failed run leaves the prior version
  selected and the warehouse rebuildable from it.

## Round 5 — Codex

Prior blockers addressed: shared line correspondence defined; coach-season `teamId` restored; duplicate coach row resolved; version manifest added; postgame mutation test added.

Material gaps remain:

- **Coach-season merge still lacks team bridge.** `coaches` has name+season grain; target needs `coachId+teamId+season`. Real mid-season team change means one REST row can match multiple GraphQL rows. Fix: define team resolution from REST payload, or preserve unmatched/ambiguous REST row outside merged fact.
- **Line period normalization missing.** REST offers have no period; GraphQL period encoding may be `NULL`, `0`, enum, or string. Wrong mapping creates false unmatched rows and duplicates. Fix: define canonical full-game period value, normalize both sides, and gate on expected matched full-game offer count.
- **New raw version promoted too early.** Manifest promotes after steps 5–7, before drops, agreement gates, and final validation in step 9. A step-8/9 failure leaves new source active. Fix: stage new manifest through all steps; atomically promote only after every validation passes.
- **Coach target omits `coach_seasons` source grain.** Three-source merge names `coaches` and `coach_seasons`, but only describes deduplication for `coaches`; no grain, authority, or key proof for second REST table. Fix: add each source’s exact grain, bridge, conflict policy, and row-preservation gate.

VERDICT: REVISE

### Claude's response

**All four accepted and applied.** Two dissolved once the warehouse was checked.

- *Coach-season merge lacks team bridge* — the bridge already exists in the REST payload.
  `stg.coaches__seasons` holds 1,937 rows carrying `seasons_school` beside `seasons_year`, so a
  REST coach-season resolves to a team without inference. Replaced the flat `coaches` with
  `coaches__seasons` as the merge source; `coaches` contributes only `hireDate` at coach grain,
  and its lack of a team is precisely why the Blake Anderson row looked duplicated. Added a
  three-source grain table and `core.coach_season_unmatched` for rows that resolve ambiguously.
- *Line period normalization missing* — checked the encoding rather than defending against every
  possibility: `gql_game_lines.period` is `VARCHAR` with exactly three values and no NULLs —
  `game` (46,765), `firsthalf` (8,274), `firstquarter` (8,254). Canonical full-game value is
  `game`; REST normalizes to it; step 6 gates on the expected match count.
- *New raw version promoted too early* — correct and I had it wrong. Promotion moved from "after
  steps 5-7" to "after step 9 validates in full", so a failure in the drops or the agreement
  gates cannot leave a new source active.
- *Coach target omits `coach_seasons` grain* — added: `(coach_id, team_id, season)`, 1,961 rows,
  72 columns, bridging directly.

## Resolution — MAX_ROUNDS reached without APPROVED

The loop terminated at its cap. Codex never returned `VERDICT: APPROVED`, so this is recorded as
a deadlock rather than a convergence, per the skill's rule against faking one.

Honest reading of the trajectory: round 1 returned 15 findings including a hard-rule violation
(untagged result-informed columns entering `fact_game`) and a self-contradiction between step 8
and D1. Round 5 returned 4, of which 2 were answered by tables that already existed. Findings
narrowed from structural to specificational across the five rounds, and 30 of 31 total findings
were accepted — one rejected with reason (concurrency machinery for a single-writer local file).

Round 5's fixes are **applied but not re-reviewed**. That is the one genuinely open item.

## Act 3 — Build

Spec: `docs/superpowers/plans/2026-08-31-warehouse-naming-rationalization.md` (the naming plan,
built first because the source-rationalization plan's step 0 preflight blocks on it). Scope:
Tasks 1-4 and 6. Tasks 5, 7, 8 are human-run and out of scope. Builder: Codex, model
gpt-5.6-terra, codex-cli 0.151.0, launched by the user after the auto-mode classifier declined
`codex exec --yolo` from this session.

### Round 1 — Codex build

Files changed: `cfb_system_maker/graphql_client.py`, `cfb_system_maker/duckdb_load.py`,
`tests/test_graphql.py`, `tests/test_duckdb_load.py` (modified); `scripts/migrate_gql_stg_names.py`,
`scripts/audit_canonical_sources.py`, `tests/test_migrate_gql_stg_names.py`,
`tests/test_audit_canonical_sources.py` (new). Reported 695 passed, 6 deselected.

### Claude's verdict — accepted with one addition

Verified independently rather than taking the report on trust:

- **Scope clean.** 4 modified + 4 new, all in-scope. Nothing under `data/`, nothing in
  `cfbd-python/`, no git operations, no network calls.
- **The API contract survived.** `GQL_DEFAULT_TABLES` is untouched — the diff shows only context
  around it. Every remaining camelCase string in live code is either a GraphQL entity name, a
  `_BARE_ID_RENAME` key, or a migration-test fixture, and each is correct in place. This was the
  build's single largest risk and Codex did not trip it.
- **Proof re-run by Claude:** 695 passed, 6 deselected, 120s. Matches the report. Baseline was
  679, so +16 — exactly the count the spec's five task sections call for.
- **Dry-run against the live warehouse (read-only):** 38 renames — 34 parents plus the 4 child
  tables — matching the count independently derived during planning. `calendar_gql -> gql_calendar`
  resolved correctly and REST `calendar` was left alone. No REST table appears on the left side.
- **Audit script degrades correctly** pre-migration, reporting `MISSING` per pair rather than
  raising.

**Codex found a spec gap and fixed it correctly.** `_BARE_ID_RENAME` is keyed by GraphQL *entity*
name (`"game": "gameId"`), so once destinations became `gql_*`, `stg_id_renames("gql_game")` would
have missed the table and left a bare `id` column instead of `gameId`. The spec never mentioned
this. Codex added a reverse lookup from destination back to entity. Verified across `gql_game`,
`gql_coach`, `gql_lines_provider`, `gql_historical_team`, and confirmed REST names still resolve.

**Claude's addition:** `test_stg_id_renames_resolves_gql_destinations_back_to_their_entity`. The
reverse lookup was only indirectly covered — reverting it fails `test_explode_payloads_writes_stg_columns`
with a confusing column-list mismatch, but nothing named the actual cause. Confirmed the new test
guards it by patching the reverse lookup out and watching it fail, then restoring. Added directly
rather than through a Codex fix round: a four-line test is trivia, and the skill warns against
ping-ponging trivia through delegation. Final suite: 696 passed.

### Incident — reviewer error, recovered

While proving the new test guards the regression, Claude patched the reverse lookup out and then
ran `git checkout cfb_system_maker/duckdb_load.py` to restore it. That restores from HEAD, and
Codex's changes were uncommitted, so the file was reverted and Codex's work on it was lost. The
other seven files were unaffected.

Recovered by reconstructing all 19 hunks from the diff captured earlier in the review, each
applied under an assertion that it matched exactly once. `git diff --stat` returned 65 changed
lines, identical to Codex's original stat, and the suite passed at 696. No Codex re-run was
needed.

Lesson recorded because it will recur: **never `git checkout` a file while an unreviewed,
uncommitted build sits in the working tree.** The correct move is to snapshot the file first
(`cp`) and restore from the snapshot, or to stash. The clean-tree gate protects the tree before
the build; it does nothing for the tree during review.

Rounds used: 0 of MAX_FIX_ROUNDS=2. No fix round was needed.

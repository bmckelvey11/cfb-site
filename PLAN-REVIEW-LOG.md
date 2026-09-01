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

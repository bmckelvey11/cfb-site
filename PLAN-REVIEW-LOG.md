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

---
status: accepted
---

# Cross-source merges land in `core`, and `fact_game` gains columns rather than rows

`stg` carries 13 concept pairs where the same subject arrives from both the CFBD REST API and
the CFBD GraphQL API under different names and different column sets. Measurement showed the
two sources are complementary rather than redundant — 10 of 13 pairs have populated columns the
other side lacks — so the pairs need conforming, not deduplicating. We decided the conformed
result belongs in `core` while both `stg` sources stay in place: `stg` remains a faithful
per-source shred of `raw`, `core` remains the conformed layer, and provenance stays recoverable
without a re-scrape. We further decided that `core.fact_game` gains the GraphQL-only columns for
the span the two sources share, and does **not** gain GraphQL's extra rows; those go to
`core.fact_game_historical`.

## Alternatives

Merging inside `stg` was rejected: it yields three tables per concept and worsens the ambiguity
the exercise set out to remove. Dropping the `stg` sources after merging was rejected because
provenance then survives only in code, and recovering it costs a full re-scrape of both APIs.

## Consequences

The row-count split is the non-obvious part. GraphQL `stg.game` spans 1869–2026 (112,672 rows);
REST `stg.games` spans 1992–2026 (54,264). The modern seasons match exactly — 2024 is 3,801 on
both sides, 2025 is 3,831, 2026 is 3,676 — so the entire 2.1× surplus is pre-1992 history, not
duplicate coverage. Folding it into `fact_game` would more than double the modeled game
population with games that have no lines, no Elo, and present-day classifications applied
retroactively (GraphQL labels 79,787 rows `fbs` against REST's 26,827). It would also invalidate
the agreement gates in `tests/test_core_agreement.py`, including the bowl-lookahead tripwire,
which were written against a 54,264-row fact. Keeping the spine fixed means those gates keep
meaning what they meant, and deep history cannot enter model training by accident.
`core.fact_game_historical` is therefore not classification-accurate for its own era and must
not be treated as such.

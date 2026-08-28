---
task: graphql-coverage-audit
date: 2026-08-28
mode: quick
status: complete
---

# Quick Task 260828-t8p — Summary

`scripts/audit_endpoints.py` now audits **both** CFBD APIs against their live schemas.

```
spec paths: 74 | verbs: GET | client methods: 74 | registry: 73
73 registered + 1 client-only + 0 no-client = 74 of 74 spec paths

GRAPHQL: 38 root field(s) with scalars - 1 wrapper(s) ['athleteByPk'] = 37 table(s)
  35 in defaults + 2 excluded = 37 of 37 introspected tables
```

Every defaulted table has a file on disk; zero unaccounted, zero on-disk-not-in-schema.

## What changed

- **Universe is introspection, not the hand-kept list.** `audit_coverage.py` compared
  `data/graphql/` against `GQL_DEFAULT_TABLES` — exactly the flaw the REST audit exists to
  fix. The wrapper filter now prints what it dropped (`['athleteByPk']`), so a Hasura schema
  shape change surfaces as a diff instead of a quietly different denominator.
- **`GQL_DEFAULT_TABLES` 24 → 35.** Eleven lookup tables (`draftPosition`, `draftTeam`,
  `hometown`, `linesProvider`, `playerStatCategory`, `playerStatType`, `pollType`,
  `position`, `recruitPosition`, `recruitSchool`, `weatherCondition`) were already on disk
  but reachable only via `--tables`, so a fresh pull would have missed them. All tiny
  (2.5 KB - 2.2 MB).
- **`GQL_EXCLUDED`** holds the two deliberate omissions *with reasons*, beside the list it
  modifies. The audit reads both rather than keeping its own copy — same shape as
  `DELIBERATE` on the REST side.
- **Per-season shards fold into their base table**, so `gamePlayerStat`'s 15 files count as
  one table rather than 15 phantom tables.

## Tier 3 is not a prerequisite

An unreachable schema (no token, no Tier 3, offline) prints
`GRAPHQL: schema not reached (...)` and contributes nothing to the exit code. The REST half
runs offline from a saved `--spec`, and holding it hostage to a paid tier would make the
script useless as a CI gate. `--no-graphql` skips the section outright. Only a table that is
*reached* and is neither defaulted nor documented exits 1.

## Tests

Two network-free additions with a fake schema: one asserts the partition, the shard folding,
the printed wrapper names, and that a novel table lands in `UNACCOUNTED`; the other asserts
the unreachable-schema path degrades to a note. Suite: 564 passed, 1 skipped.

`audit_coverage.py` re-run after the default-list change reads `35/35 default tables on
disk`, with `gamePlayerStat` correctly the lone "extra" and its 14 shards listed as shards —
not misreported as extra tables.

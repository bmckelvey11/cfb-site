---
task: cfbd-endpoint-completeness-audit
date: 2026-08-28
mode: quick
status: complete
---

# Quick Task 260828-q7t — Summary

`scripts/audit_endpoints.py` makes the spec-vs-code endpoint diff re-runnable. It reads
the live CFBD REST spec (`https://api.collegefootballdata.com/api-docs.json`, 74 paths,
all GET), `ast`-parses the vendored client for its `call_api('/path', 'GET', ...)`
literals, and diffs both against `scrapers.ENDPOINTS`.

## Result on first run — the partition closes

```
spec paths: 74 | verbs: GET | client methods: 64 | registry: 63
63 registered + 1 client-only + 10 no-client = 74 of 74 spec paths
```

Zero unclassified paths, zero registry drift, zero duplicate path→method hits. The
client-only path is `/info/usage` (deliberate) and the 10 no-client paths are exactly the
list `docs/data-coverage.md` records as blocked on a `cfbd-python` bump. The hand-audited
74/63/10/1 breakdown is confirmed, not merely reproduced by construction.

## Details

- **Paths are read from the call site, never inferred from the class name** — `TeamsApi`
  serves `/roster` and `/talent`, and the literal only appears inside each
  `*_with_http_info` variant, so the suffix is stripped to recover the registry-facing
  method name.
- **Fourth bucket for code→spec drift**: a registry entry whose `(api, method)` is absent
  from the client, or whose resolved path is absent from the spec. Empty today; it is the
  only thing that would catch a typo'd entry or an endpoint CFBD retires.
- **Exit 1 on drift or an unclosed partition**, so this can gate CI later. `--spec` takes
  a local `api-docs.json` for offline runs; the fetch sends a non-default `User-Agent`
  because Cloudflare 403s urllib's own.
- **Verbs are counted, not assumed** — the header prints the verb set, so if CFBD ever adds
  a non-GET operation the 74-path denominator stops being silently wrong.
- `tests/test_audit_endpoints.py` — two network-free checks: the ast mapping resolves the
  class-name-mismatched TeamsApi paths and is one-to-one, and a stub spec exercises the
  no-client bucket plus the drift exit code.

## Docs

`docs/data-coverage.md` and root `CLAUDE.md` now name both scripts and say which question
each answers (`audit_endpoints.py` = spec vs registry; `audit_coverage.py` = registry vs
disk).

Full suite: 557 passed, 1 skipped.

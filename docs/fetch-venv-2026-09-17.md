# The CFBD fetch venv (`.venv-cfbd`)

**Date:** 2026-09-17

## The question

Why did `python -m cfb_system_maker upcoming` stop working under the repo's `.venv`,
and what is the smallest fix that does not break the other units?

## What broke

Any code path that imports the vendored CFBD client fails at import:

```
pydantic.errors.PydanticUserError: `const` is removed, use `Literal` instead
  cfbd-python/cfbd/models/team_stat_stat_value.py:42
```

That covers both network-fetch entry points:

- `python -m cfb_system_maker upcoming` (writes `processed/upcoming*.{csv,json}`)
- `scripts/refresh_cfbd.py` (the daily warehouse refresh)

## Why

A dependency conflict that pip resolved silently, in the repo's favour and against
the vendored client:

| Package | Requires |
| --- | --- |
| `cfbd-python/requirements.txt` | `pydantic >=1.10.5, <2` |
| `anthropic==0.111.0`, `pydantic-ai-slim`, `pydantic-graph` | `pydantic >=2` |

`requirements.txt` pulls in both (line 1 is `-r cfbd-python/requirements.txt`), so the
resolver installed **pydantic 2.13.5** and the `<2` pin was silently violated. No pypi
`cfbd` package is installed, so the vendored pydantic-1 client is the only one on the
path. The breakage postdates the last successful refresh: the pydantic-2 packages
landed in `.venv` afterwards.

Note for future auth failures: the CFBD token was **not** the problem. It lives in
`env.env` as `CFBD-API ` — with a trailing space before the `=`. `find_cfbd_token`
calls `.strip()` on the key, so it resolves; a naive `grep '^CFBD-API='` does not
match it.

## The fix

A second interpreter, `.venv-cfbd`, used only for the network fetches. The shared
`.venv` is left alone, so `anthropic` and everything built on pydantic 2 keeps working.

Rejected alternatives:

- **Downgrade pydantic in `.venv`** — breaks `anthropic` for every other unit.
- **Bump the vendored client to a pydantic-2 release** — plausible (precedent: `f17d66f`),
  but `cfbd-python/` is vendored upstream and CLAUDE.md says not to edit it.
- **Drop `anthropic` from `.venv`** — costs the library to fix an unrelated path.

## How to use it

```
scripts\make_fetch_venv.cmd      rebuild .venv-cfbd from requirements-fetch.txt
scripts\refresh_upcoming.cmd     refresh this week's games + lines + features
scripts\refresh_cfbd.cmd         daily warehouse refresh (now defaults to .venv-cfbd)
```

`refresh_cfbd.cmd` falls back to `.venv` when `.venv-cfbd` is absent, so an un-built
fetch venv degrades to the old behaviour instead of hard-failing. `PYTHON=` still
overrides both. `.venv-cfbd/` is gitignored.

`requirements-fetch.txt` holds only what the two fetch paths actually import — the
cfbd pin plus `numpy`, `scipy`, `duckdb`, `pytz`, `tzdata`. It is deliberately not a
second copy of `requirements.txt`: the fetch venv cannot serve the Flask app (`waitress`)
or run narration (`anthropic`), and is not meant to. Use `.venv` for those.

## Verified

Rebuilt from scratch via `make_fetch_venv.cmd`, then:

- `scripts\refresh_upcoming.cmd` → `Resolved 2026 regular week 3 (73 game(s))`, exit 0
- `scripts\refresh_cfbd.py --help` → imports clean, exit 0

The refresh itself moved `processed/upcoming.csv` from 2026 week 1 (99 rows, stamped
2026-08-27) to 2026 week 3 (73 rows). `upcoming_features.json` rewrote alongside it and
covers all 73 game ids.

## What this does not support

This does not fix `requirements.txt`; the conflict is still latent there, and a
`pip install -r requirements.txt` into `.venv` will still produce a venv that cannot
fetch. It only routes the fetch paths around it. It also says nothing about whether a
newer upstream `cfbd-python` would remove the conflict outright — that remains the
cleaner long-term fix if someone wants to take it.

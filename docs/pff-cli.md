# PFF Developer API CLI — install, use, and where it fits here

**Installed 2026-09-08.** Restish 2.3.0 at `C:\Users\mckel\restish\restish.exe`, connected to
`https://api.pff.com` as the API named `pff`.

PFF ships no binary of its own. It publishes an OpenAPI document at
`https://api.pff.com/openapi.json` (public, no credential), and the open-source
[Restish](https://github.com/rest-sh/restish) CLI turns that document into commands —
`restish pff passing`, `restish pff players`, and 68 others, each with its own `--help`.
Upstream guide: <https://developer.pff.com/guide/>.

Everything past `--help` needs **a paid PFF Pro subscription**. PFF+, free, and Pro-*trial*
accounts can sign in but every data command answers 403. This machine is authenticated by API key
through the `ci` profile and returns live data; the interactive browser sign-in is still unused.
See [Status](#status) at the bottom.

---

## What is installed, and where

| Thing | Path on this machine |
| --- | --- |
| Binary | `C:\Users\mckel\restish\restish.exe` |
| Config (connected APIs, profiles) | `C:\Users\mckel\AppData\Roaming\restish\restish.json` |
| Cached sign-in tokens | `C:\Users\mckel\AppData\Roaming\restish\tokens.cbor` |
| HTTP cache | `C:\Users\mckel\AppData\Local\restish` |
| Cached OpenAPI specs | `C:\Users\mckel\AppData\Local\restish\specs` |
| Plugins | `C:\Users\mckel\AppData\Roaming\restish\plugins` (none) |

Verified with `restish doctor` — the upstream docs only list the macOS/Linux `~/.config/restish/`
paths, which do not apply here. Windows cannot check config file permissions (`permission check
unsupported on this platform`); the token cache is fine, but treat `restish.json` as sensitive
anyway.

### PATH

`C:\Users\mckel\restish` was appended to the **user** PATH on 2026-09-08, so `restish` resolves in
any new terminal. Terminals open before that still need the absolute path.

To redo it on another machine, in PowerShell:

```powershell
[Environment]::SetEnvironmentVariable('Path', [Environment]::GetEnvironmentVariable('Path','User').TrimEnd(';') + ";$HOME\restish", 'User')
```

Do **not** use `setx PATH` — it truncates at ~1024 characters. The user PATH here was already 1901
characters across 32 entries, so `setx` would have silently destroyed most of it. The pre-change
value is backed up at `C:\Users\mckel\path-backup-2026-09-08.txt`.

### How it was installed (reproduce on another machine)

No Homebrew/scoop/Go on this box, so it came from the release archive:

```bash
curl -sL -O https://github.com/rest-sh/restish/releases/download/v2.3.0/restish-2.3.0-windows-amd64.zip
curl -sL -O https://github.com/rest-sh/restish/releases/download/v2.3.0/checksums.txt
sha256sum -c --ignore-missing checksums.txt   # 8d9f4689…4225b
```

```powershell
Expand-Archive restish-2.3.0-windows-amd64.zip -DestinationPath $HOME\restish
& "$HOME\restish\restish.exe" --version        # restish version 2.3.0
```

Other platforms: `brew install restish`, `mise use -g restish@latest`, or
`go install github.com/rest-sh/restish/v2/cmd/restish@latest`.

Pin **2.3.0**. PFF develops and tests against it. Restish 1.x uses different commands
(`api configure` instead of `api connect`) and will just error.

### Connecting (already done — repeat only after a reinstall)

```powershell
restish api connect pff https://api.pff.com
```

Use the **bare origin**. `https://api.pff.com/v1` fails discovery with
`spec discovery failed: … 401 Unauthorized`, because everything under `/v1/` needs a credential.

The connect output ends with `callable: 0/68 secured operations` and
`unresolved: pffOAuth (OAuth access token not cached)`. **That is success, not an error** — it
just means nobody has signed in yet.

When PFF adds endpoints, pick them up with `restish api sync pff`. Sign-in is untouched.

### Shell completion

`restish shell setup zsh|bash|fish` installs completion and stops the shell expanding `[]` in
filters. PowerShell is not in that list, so **quote every filter containing brackets**:
`-f 'body.players[0]'`. Git Bash users should run `restish shell setup bash`.

---

## Signing in

Two credentials, both `Authorization: Bearer …`, both requiring PFF Pro.

**Browser (interactive, default profile).** The first data command opens a browser; sign in and
approve `pff-pro`. Tokens are cached and refreshed silently.

```powershell
restish pff whoami
```

`whoami` costs nothing against the rate budget and is the right first call. Read `entitled` and
`entitlement_reason`:

| `entitlement_reason` | Means |
| --- | --- |
| `null` with `entitled: true` | Good — every data command will work |
| `subscription_required` | Account is PFF+ or free. Upgrade at <https://www.pff.com/subscribe> |
| `trial` | Pro trial — the CLI is *not* included, unlocks on conversion to paid |
| `unlinked_account` | Pro but no subscriber record. Email support@pff.com with the `request_id` |

`installations.max` caps how many devices one account can use the CLI from (2 on a standard Pro
account). Worth knowing before installing this on a second box.

No browser (SSH, headless): add `--rsh-no-browser` and paste the code from another device.

**The browser flow needs a real terminal.** Restish checks whether stdout is a TTY and refuses
otherwise — from an agent shell, a script or CI you get
`has no cached access token; rerun from an interactive terminal to complete OAuth authorization`
before any request is sent. `--rsh-no-browser` doesn't help; it still wants to read a pasted code
from stdin. Sign in once from a real terminal, or use an API-key profile.

**API key (scripts, CI, notebooks, curl).** Create at <https://www.pff.com/account/api-keys>.
Shown once. PFF documents the prefix as `ak_live_`, but the working key here does not match that —
don't validate a key on its prefix, call `whoami` instead. Put it in the environment — never on a
command line, never in a tracked file:

```powershell
restish api set pff 'profiles.ci.credentials.pffApiKey.auth.type: bearer'
restish api set pff 'profiles.ci.credentials.pffApiKey.auth.params.token: env:PFF_API'
restish pff whoami -p ci        # credential: api_key
```

`env:PFF_API` is resolved at request time, so the key never lands in `restish.json` or shell
history. The default (browser) profile keeps working alongside it — pick the key with `-p ci` per
command.

### The `ci` profile on this machine

**Set up 2026-09-08 and verified** — `whoami -p ci` returns `tier: pro`, `entitled: true`,
`credential: api_key`. Data commands work through it.

The key lives in `env.env` at the repo root as **`PFF_API`** (not `PFF_API_KEY` — PFF's docs use
that name, this repo doesn't). `env.env` is gitignored. Nothing but the literal string
`env:PFF_API` is stored in `restish.json`.

Nothing loads `env.env` into your shell automatically, so export it before running `-p ci`:

```powershell
$env:PFF_API = ((Select-String -Path env.env -Pattern '^PFF_API=').Line -split '=',2)[1].Trim()
restish pff leagues -p ci
```

```bash
export PFF_API=$(grep -E '^PFF_API=' env.env | cut -d= -f2- | tr -d '\r')
restish pff leagues -p ci
```

Making it permanent (a user env var) would put the key in the registry for every process on the
box — a deliberate tradeoff, not a default. Left per-shell.

An API key reports `installations.max: null` — the device cap applies to browser sign-ins, not keys.

Revocation from the same page takes up to ~60s to bite (the API caches a successful key check).

**Signing out.** `restish pff logout` ends the API session; `restish api auth logout pff` deletes
the cached tokens. Run both. On its own the first one leaves a refresh token behind, so `whoami`
will quietly work again a moment later.

---

## Command shape

```
restish pff <command> <required positionals> [--flags]
```

Positionals in the order `--help` lists them; everything else is a flag; `--help` on any command
prints the full argument schema, the response schema, and the error envelope. `restish pff --help`
lists all 70 commands grouped by family:

| Family | What it returns | Examples |
| --- | --- | --- |
| `ref` | Reference data | `ref-leagues`, `ref-games`, `ref-players` |
| `facet` | League-wide leaderboards, one row per player (27 commands) | `facet-passing-summary`, `facet-defense-coverage` |
| `player` | One player's reports (21 commands) | `player-passing-summary`, `player-position-pivot` |
| `team` | Team lists and PFF's own team-page tables (10 commands) | `team-directory`, `team-report`, `team-roster` |
| `signature` | PFF signature stats (4 commands) | `signature-passing-time-in-pocket` |
| `auth` | `whoami`, `logout` | |
| `meta` | `openapi-json`, `openapi-yaml` | |

Every operation, its positionals, flags, wire names, enums and CSV flag is tabulated in
[`docs/pff-endpoint-reference.md`](pff-endpoint-reference.md), generated from the OpenAPI
document by [`scripts/gen_pff_endpoint_reference.py`](../scripts/gen_pff_endpoint_reference.py).

Ten commands have short aliases: `passing` = `facet-passing-summary`, `players` = `ref-players`,
`games` = `ref-games`, `leagues` = `ref-leagues`, and so on. Same command either way.

### Two surfaces under one CLI

`/v1` is the long-standing Premium Stats API: snake_case JSON, one top-level key holding the rows
(`{"passing_summary": [...]}`), CSV via `--export true`. That is every `ref-`, `player-`, `facet-`
and `signature-` command plus `teams`/`team-overview`/`team-summary`.

`/v2` is PFF's newer contract over the team page: camelCase, a `{columns, rows, updatedAt}` table
object, CSV via `--format csv`. That is the other `team-*` commands. Ranked values arrive as
`<key>` plus `<key>Rank`.

You never type a path — but the two halves take different CSV flags and different key casing, which
matters the moment you parse the output.

---

## College football specifics

This repo is FBS college football, and PFF's own examples are all NFL. What actually differs:

- **`--league ncaa`** (or `ncaa` as the positional on non-facet commands). Valid league slugs are
  `nfl`, `ncaa`, `hs`, `aaf`, `ufl` — but only `nfl`/`ncaa`/`aaf`/`ufl` appear in `ref-leagues`,
  so `hs` is accepted with no discoverable metadata.
- **`--division` is NCAA-only and facet-only.** Comma-separated, each element `fbs`, `fcs` or
  `lower`. `fbs` covers FBS plus the all-star group; `lower` covers D2 and D3. Silently ignored for
  every other league, and any other value fails `502 upstream_error` (the failure happens
  downstream of this API, so the message is unhelpful). Divisions fan out in parallel, so a
  multi-division request is materially slower than one division.
- **Always pin `--division` on an NCAA facet export.** Measured 2026-09-08 on
  `passing --league ncaa --season 2025 --export true`: with `--division fbs` it returned in
  **5.5 seconds**; with no `--division` it had produced nothing after **16 minutes** and was killed.
  This is not "materially slower" — an unpinned NCAA export sweeps every division down to D3 and is
  effectively unusable. If you genuinely want the lower divisions, ask for them one at a time.
- **`team-report ncaa <slug> <report>`** works the same as NFL. A programme with no rows for a
  report section returns an empty table, not an error.
- **Seasons turn over 1 March.** January and February belong to the *previous* year's season when
  `--season` is omitted. Always pass it explicitly for anything reproducible.
- **`ref-leagues` is the source of truth for weeks.** Don't guess postseason week numbers.

```powershell
restish pff leagues                                     # seasons + week groups per league
restish pff players ncaa --name "Ewers"                 # find player ids
restish pff passing --league ncaa --season 2025 --division fbs
restish pff team-directory ncaa --season 2025           # franchise ids, slugs, colours
restish pff team-report ncaa alabama-crimson-tide passing --season 2025
```

Two gotchas in the row schemas: `height` is packed as `feet × 100 + inches` (`601` = 6′1″), and
`jersey_number` is a **string** — `"09"` and `"00"` are meaningful.

### Partial entitlement

A view-only league returns `200` with fields *removed* and a `restricted` array naming the withheld
columns — not a `403`. Check for `restricted` before concluding a column doesn't exist.

---

## Output and export

| Flag | Effect |
| --- | --- |
| `-o json` | Plain JSON — use when piping or redirecting |
| `-o table --rsh-columns a,b,c` | Table with chosen columns; `--rsh-sort-by` to sort |
| `-o lines` | One value per line |
| `-f '…'` | Filter — Restish shorthand or jq, auto-detected |
| `--rsh-print b` | Body only, no headers, no pretty-printing |
| `-v` | Also print request/response headers |

```powershell
restish pff passing --league ncaa --season 2025 -f 'body.passing_summary[0]' -o json
restish pff passing --league ncaa --season 2025 -f body.passing_summary -o table --rsh-columns player,team,yards,touchdowns
restish pff leagues -f 'body.leagues[].slug' -o lines
```

**CSV.** `/v1` commands (33 of them — every `facet-*`, every `signature-*`, plus
`player-position-pivot`) take `--export true`. `/v2` `team-*` commands take `--format csv`
instead. Both need `--rsh-print b`, or `-o json` wraps the whole file in one escaped JSON string:

```powershell
restish pff passing --league ncaa --season 2025 --export true --rsh-print b > passing-2025.csv
restish pff team-directory ncaa --season 2025 --format csv --rsh-print b > teams-2025.csv
```

`team-rushing-direction` carries two tables; `--table totals` exports the second.

An export with **no rows and no header line** means the account isn't entitled to that league or
report. Re-run without `--export` to see `restricted`. (An entitled export with no matching records
still has its header line.)

### Exports that lie — verified 2026-09-08, NCAA 2026

That entitlement explanation is PFF's, and it is not the only cause of an empty export. Pulling all
28 NCAA facet leaderboards turned up three separate failures, none of which set a non-zero exit
status. **Restish exits 0 on all of them**, so a script that trusts the exit code writes garbage.

**1. Blank CSV, working JSON.** `facet-offense-summary`, `facet-passing-detail` and
`facet-rushing-direction` answer `--export true` with the *correct number of lines and nothing on
any of them* — 7,624 bytes of bare CRLF for offense-summary, one blank line per JSON row. The same
query without `--export` returns full data (3,811 × 25, 251 × 908, 898 × 11). Entitlement is fine;
the CSV writer is broken. Take the JSON.

**2. Upstream 500.** `facet-receiving-coverage` and `facet-defense-coverage-matchup` fail for NCAA
2026 in every format, after two internal retries:

```json
{"error":{"code":"upstream_error","details":{"upstream_status":500},"message":"The upstream failed with status 500","request_id":"…"}}
```

The error envelope is written to **stdout**, so with `--rsh-print b > file.csv` it lands *in the CSV*
and stderr carries only restish's retry chatter. Parse the body for `error.code`; don't read stderr.

**3. Reports that never answer.** `facet-offense-summary` hung for 15 minutes at zero bytes and had
to be killed — the same command that had returned (blank) five minutes earlier, with
`x-ratelimit-remaining: 99`, so not throttling. Intermittent, server-side. Always set a timeout on a
bulk run.

What a caller has to check, in order: non-zero exit; then `error.code` in the body; then that the
first non-blank line actually contains a comma. [`scripts/pull_pff_facet.py`](../scripts/pull_pff_facet.py)
does all three, falls back to JSON on a blank CSV, and takes `--timeout` (default 180s).

### Where exports go in this repo

`data/` is gitignored and `CFB_DATA_ROOT` resolves through root `cfb_paths.py`. Land PFF pulls
under `data/` — e.g. `data/raw/pff/` — never in `docs/` or anywhere tracked. Per the repo standing
rule, anything reproducible gets a script, not a one-off command in shell history.

---

## Rate limits

**Measured 2026-09-08 against this account** — the OpenAPI document deliberately refuses to name the
numbers ("so many reads a minute, so many exports a minute"), so read them off the headers rather
than trusting any doc, this one included.

| Budget | Limit | Spent by |
| --- | --- | --- |
| read (`scope: api`) | **100 / minute** | every operation, including a refused one |
| export (`scope: export`) | **20 / minute** | `--export true` on `/v1`, `--format csv` on `/v2` |

Both are **per account**, shared across every credential it holds — a CI key and your laptop draw
on the same budget. `whoami` is genuinely free: it comes back with no `x-ratelimit-*` headers at all.

The window is **fixed, aligned to the wall-clock minute** — `x-ratelimit-reset` is always an epoch
second divisible by 60, and both budgets reset on the same tick. So a burst straddling a boundary
gets 40 exports in a few seconds, and a run that starts at `:59` stalls almost immediately.

An export **spends its quota whether or not it succeeds**, and restish retries twice by default —
so one failing export can burn three credits. `--rsh-retry 0` (or `RSH_RETRY=0`) turns that off when
you would rather see the failure than pay for it three times.

Over budget is `429` with `error.code: rate_limited`, `error.details.scope` naming which budget, and
a `Retry-After`. A `429` with `error.details.upstream_status: 429` is a different thing — PFF's own
data source metering you, not this API.

Every counted response carries `x-ratelimit-limit`, `x-ratelimit-remaining` and `x-ratelimit-reset`
(epoch seconds), so a client can slow down before it is told to.

```powershell
restish pff passing --league ncaa --season 2025 --rsh-headers | Select-String -Pattern ratelimit
```

`--rsh-headers` is shorthand for `-f headers` — it swaps the body out of the output, it does not
skip the request, so checking your budget this way still spends a read.

Download once, work from the file. Don't loop an export. Seasons and weeks take comma-separated
lists (`--season 2023,2024,2025`, `--week 1,2,3`) — often that replaces a loop entirely. An export
spanning too many weeks or seasons is refused with `422`.

---

## Errors

One shape everywhere:

```json
{"error": {"code": "…", "message": "…", "request_id": "…", "details": {…}}}
```

Branch on `error.code` and `error.details.reason`. **Never on `message`** — PFF states it is
deliberately not part of the contract. Quote `request_id` (also the `x-request-id` header) to
support.

`code` is one of `invalid_parameter`, `not_found`, `unauthorized`, `forbidden`, `rate_limited`,
`session_provisioning`, `upstream_error`, `upstream_timeout`, `internal_error`.

| Status / reason | Meaning | Fix |
| --- | --- | --- |
| 401 `missing` / `malformed` | No/bad `Authorization` header | Send `Authorization: Bearer <key>` |
| 401 `invalid_signature` | Typo'd, deleted, or wrong-environment key | Re-copy or create a new key |
| 401 `revoked` | Key or sign-in revoked | New key, or sign in again |
| 401 `expired` | OAuth token couldn't refresh | `restish api auth logout pff`, run any command |
| 401 `wrong_token_type` | A pff.com browser session cookie was sent | Use an API key or the Restish sign-in |
| 403 `subscription_required` | Valid credential, PFF+/free account | Upgrade |
| 403 `trial` | Pro trial — CLI unlocks on conversion | Nothing to fix |
| 403 `unlinked_account` | Pro, no subscriber record | Email support@pff.com with `request_id` |
| 429 `rate_limited` | Read/export budget spent | Wait for `Retry-After` |
| 429 `verify_ip` | Too many unknown keys from one address | Fix the key, don't retry |
| 502/503 `upstream_error` | Data service or identity provider down | Retry; check <https://status.pff.com> |
| 503 "Preparing your session…" | Session initialising | Auto-retried; don't fire parallel commands right after sign-in |

Setup-time errors: `api configure was a Restish v1 command` → use `api connect`. `unknown command`
→ `restish api sync pff`. `no matches found: body.leagues[]` → quote the filter.

Diagnostics:

```powershell
restish pff whoami                 # identity + entitlement
restish doctor                     # paths, version, config parse
restish api inspect pff            # stored config, secrets masked
restish api list                   # every connected API
restish pff <command> -v           # request/response headers
restish pff openapi-json -o json > pff-openapi.json
```

---

## Calling it without Restish

The credential and paths are plain HTTP, so any client works:

```bash
export PFF_API=$(grep -E '^PFF_API=' env.env | cut -d= -f2- | tr -d '\r')
curl -s https://api.pff.com/v1/auth/whoami -H "Authorization: Bearer $PFF_API"
curl -s 'https://api.pff.com/v1/facet/passing/summary?league=ncaa&season=2025&division=fbs' \
  -H "Authorization: Bearer $PFF_API"
curl -s 'https://api.pff.com/v2/ncaa/teams/alabama-crimson-tide/reports/passing?season=2025&weekGroup=REG' \
  -H "Authorization: Bearer $PFF_API"
```

**Restish flag names are not wire names.** `--franchise` → `franchise_id`, `--game` → `game_id`,
`--name` (on `ref-players`) → `q`; `/v2` uses camelCase (`weekGroup`, `weekTo`). The OpenAPI
document is the source of truth and needs no credential — fetch it and read it, don't infer from
the flags. CSV is `export=true` on `/v1` and `format=csv` on `/v2`.

---

## Status

**What is verified here vs. transcribed.** The install, the paths, the command surface and every
argument/flag description were read off this machine (`restish doctor`, `restish api list`,
`--help` — none of which need a credential). Authentication and one live read are now verified too:
`whoami -p ci` returns `tier: pro`, `entitled: true`, `credential: api_key`, and `ref-leagues`
returns `nfl`, `ncaa`, `aaf`, `ufl` — exactly the four PFF documents.

Still **unverified**, transcribed from developer.pff.com: the failure-side `entitlement_reason`
values (`subscription_required`, `trial`, `unlinked_account`), the
error `details.reason` table, and the ~60s key-revocation cache. One contradiction found already —
PFF says API keys start with `ak_live_` and the working key here does not — so treat the rest as
claims, not facts.

| Step | State |
| --- | --- |
| Restish 2.3.0 downloaded, checksum verified, extracted | done (2026-09-08) |
| `restish api connect pff` — 70 operations discovered | done (2026-09-08) |
| `restish.exe` on PATH | done (2026-09-08) — user PATH, old value backed up |
| `ci` API-key profile created and verified | done (2026-09-08) — `whoami -p ci`: pro, entitled |
| Browser sign-in (`default` profile) | **not done** — needs an interactive terminal; the `ci` profile covers scripted use |
| Live data read | done (2026-09-08) — `ref-leagues` only, as a smoke test |
| Any CFB data pulled into `data/` | done (2026-09-08) — `scripts/pull_pff_modeling.py` covers every operation by tier; `scripts/pull_pff_facet.py` the leaderboard exports. Schema: `docs/pff-warehouse-schema.md` |

NCAA seasons the API reports: 2008, then 2010–2026 — no 2009.

## Links

- Endpoint reference generated from the spec: [`docs/pff-endpoint-reference.md`](pff-endpoint-reference.md)
- Guide: <https://developer.pff.com/guide/>
- API reference: <https://developer.pff.com/reference/>
- Troubleshooting: <https://developer.pff.com/guide/troubleshooting/>
- Restish releases: <https://github.com/rest-sh/restish/releases>
- API keys: <https://www.pff.com/account/api-keys>
- Status: <https://status.pff.com>

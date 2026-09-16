# oddspapi.io integration: security check — 2026-09-16

**Question.** Is the oddspapi key handled safely, and did it leak anywhere on this
machine or in the repo? Context: the key was added 2026-09-09, the same day as the
confirmed malware run on this laptop (see memory `machine-compromise-2026-09-09`).

**Method.** Read `scripts/pull_oddspapi.py`, `scripts/pull_oddspapi.cmd`, and the
oddspapi section of `docs/oddsapi-ingest.md`. Read the key from `env.env` in memory
and searched for its value (never printed) in: full git history (`git log -S`, all
refs), tracked files (`git grep`), every file in `data/logs/`, all 8 saved snapshots
in `data/ingest/oddspapi/`. Checked `env.env` ACL, ignore status, mtime, and whether
the key also lives in a persisted environment variable. Fetched the vendor's
authentication doc.

## Findings

**Clean:**

- Key not in git history, not in any tracked file, not in any log, not in any
  snapshot. `env.env` has never been tracked and is gitignored.
- Not in a persisted user environment variable (only read from `env.env` at run time).
- Transport is HTTPS to `api.oddspapi.io`. Response parsed with `json.loads`, written
  to a timestamped file, never executed or templated. 90 s timeout.
- On an HTTP error the script masks the key in the echoed body before raising, so a
  failed run cannot write the key into `oddspapi_pull.log`. Success output prints only
  tournament id, bookmaker and fixture count. Checked the log: no key.
- Scope is minimal: one read-only request per run, ~30/month against a 250 cap, from a
  scheduled task that runs only this script.

**Exposure to fix (2 items):**

1. **`env.env` is readable and writable by the sandbox accounts.** ACL carries inherited
   `Modify` for `CodexSandboxUsers` and two SIDs from a different machine domain
   (`S-1-5-21-861815947-…`, `S-1-5-21-1684622982-…`), entries the repo directory itself
   does not have, so the file was created or copied with a foreign ACL. Every key in the
   file (CFBD, MotherDuck, PFF, both odds APIs) is readable by anything running as a
   Codex or Perplexity sandbox user. Fix, run as yourself:

   ```powershell
   icacls C:\Users\mckel\dev\cfb\env.env /inheritance:r /grant:r "mckel:F" "SYSTEM:F" "Administrators:F"
   ```

2. **Key timing vs the compromise.** The key was obtained 2026-09-09; the malware ran
   09:34–15:34 EDT that day with Chrome's credential store reachable. `env.env` was last
   written 2026-09-10 14:03. If the key was created or pasted anywhere during that window,
   or if the oddspapi dashboard was logged into from Chrome that day, rotate it. The
   vendor doc says nothing about rotation, so it is a dashboard or support request
   (contact@55-tech.com). Cost of rotating is one line in `env.env`; cost of not
   rotating a stolen key is someone burning the 250-request quota.

**Accepted by design (note, no action):**

- The vendor authenticates only by `apiKey` **query parameter** (documented; no header
  alternative exists). Query strings land in the vendor's and any intermediary's access
  logs. Nothing to change on our side; it bounds the value of the key at "someone can
  read Pinnacle odds on our quota".
- `/v4/account` echoes the key in its body. The puller never calls it. Keep it that way.

## What this does not cover

Whether the key was actually exfiltrated on 09-09 (no process auditing was on), the
vendor's own security, and the other keys in `env.env`, which share finding 1.

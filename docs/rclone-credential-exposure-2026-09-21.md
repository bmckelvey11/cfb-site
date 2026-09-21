# rclone credentials: exposure check — 2026-09-21

**Question.** `rclone.conf` is unencrypted by default and rclone's own docs say the
obscuring it applies is not encryption. Does this machine's config expose working
cloud credentials, and is it sitting inside a synced folder — i.e. have the
credentials already been uploaded to the cloud they unlock?

Context: the confirmed admin-level malware run of 2026-09-09 (memory
`machine-compromise-2026-09-09`, ~6 hours, secrets rotation recorded as pending).

**Method.** Located every `rclone.conf`-shaped file under `C:\Users\mckel` (maxdepth 6,
`-iname "*rclone*" -type f`, Temp excluded). Read the config's first line to test for the
encrypted-file header, and extracted section names and key *names* only — no value was
ever printed or passed to a tool. Compared the config's path against the profile's sync
roots. Grepped the three synced markdown files that discuss rclone setup for
credential-shaped strings (`access_token`, `refresh_token`, `"token"`, `account =`,
`key = <12+ alnum>`). Checked the repo and `schtasks` for callers, and read the rclone
section of [`autostart-audit-2026-09-15.md`](autostart-audit-2026-09-15.md). Confirmed
the password flags against `rclone help flags`.

## Findings

**The config is unencrypted.** `C:\Users\mckel\AppData\Roaming\rclone\rclone.conf`,
970 bytes, mtime **2026-09-02 23:59**. First line is `[gdrive]` — an encrypted config
opens with rclone's `# Encrypted rclone configuration File` header, so this one is
plaintext.

**Four remotes, all with live credentials:**

| Remote | Credential type |
| --- | --- |
| `gdrive` | OAuth `token` (+ `scope`, `team_drive`) |
| `pcloud` | OAuth `token` (+ `hostname`) |
| `b2` | `account` + `key` |
| `allclouds` | union over the above (`upstreams`, policies) — no credential of its own |

There is **no OneDrive remote**, contrary to the advice that prompted this check.

**Not in a synced folder — the second worry is confirmed absent:**

- The config is at rclone's default path. Sync roots on this profile are
  `C:\Users\mckel\OneDrive` and `C:\Users\mckel\OneDrive - 150 Out`; the config is under
  neither, and pCloud mounts as a drive letter rather than a profile folder.
- Exactly one `rclone.conf` exists on the machine. The widened search found no `.bak`,
  no renamed copy, no second config.
- Three synced files discuss rclone setup (two Claude session transcripts under
  `OneDrive\Claude_vault\Sessions\`, one prompt file in `~\sort\`). All three return
  **zero** matches for every credential pattern tested.

**The exposure that did fire is the 2026-09-09 malware run.** The config predates it by
a week and was plaintext throughout. Four sets of working cloud credentials were
readable by an admin-level process for roughly six hours. They must be treated as
harvested until rotated.

**Encrypting the config would not have prevented that, and breaks the B2 mount.**
Config encryption defends against casual disk exposure — the risk this check just ruled
out. Against admin-level code on the same box it is near-worthless: the password can be
keylogged, the decrypted config read from process memory, or the already-mounted `X:`
used directly. And `--ask-password` defaults to `true`, so encrypting the config makes
the startup `mount-b2.cmd` (`X:`, `--no-console`) and the `rclone-b2-mount` task block
on a prompt with no console attached — the mount would silently stop appearing at boot.
Encryption needs `--password-command` on both callers to remain viable.

## What this does *not* support

- It does not show the credentials were exfiltrated. The malware had the access; no
  evidence either way about what it took. Rotation is the correct response to that
  uncertainty, not a finding that theft occurred.
- It does not clear the four cloud accounts. Nothing here inspects account-side activity
  logs, sessions, or app grants at Google / pCloud / Backblaze.
- It says nothing about credentials outside `rclone.conf` — `env.env`, browser-stored
  sessions, and other tokens on this machine were not in scope. (`env.env` was checked
  separately for the oddspapi key on 2026-09-16; see
  [`oddspapi-security-check-2026-09-16.md`](oddspapi-security-check-2026-09-16.md).)
- The transcript grep tests for credential *shapes*. A credential pasted in an unusual
  format would not match.

## Action

Rotation first; encryption is optional and third.

1. **Backblaze B2** — App Keys console. If the key predates 2026-09-09, delete it,
   create a new one, re-run `rclone config` for `b2`. Restart the `X:` mount after.
2. **Google Drive** — account Security → Third-party access → revoke rclone's grant,
   then `rclone config reconnect gdrive:`.
3. **pCloud** — Settings → Security → revoke the rclone/API token, then
   `rclone config reconnect pcloud:`.
4. *(Optional)* Encrypt: `rclone config` → `s`. Only after 1–3, and only with
   `--password-command` added to `mount-b2.cmd` and the `rclone-b2-mount` task, or the
   boot mount breaks.

Supersedes nothing. [`autostart-audit-2026-09-15.md`](autostart-audit-2026-09-15.md)
remains the record of what autostarts on this machine; it notes the rclone mount but
does not examine the config's contents.

## Reproduce

```bash
# 1. encrypted?  plaintext config starts with a section header, not rclone's header
head -1 "$APPDATA/rclone/rclone.conf"

# 2. what credentials, without printing any value
grep -E '^\[' "$APPDATA/rclone/rclone.conf"
grep -oE '^[a-z_]+ *=' "$APPDATA/rclone/rclone.conf" | sort -u

# 3. stray copies anywhere in the profile
find /c/Users/mckel -maxdepth 6 -iname "*rclone*" -type f \
  -not -path "*/AppData/Local/Temp/*"

# 4. is any copy under a sync root
ls -d /c/Users/mckel/OneDrive* /c/Users/mckel/Dropbox* 2>/dev/null

# 5. callers that would break on encryption
grep -rIl "rclone" --exclude-dir=.git .
schtasks /query /fo csv | grep -i rclone
```

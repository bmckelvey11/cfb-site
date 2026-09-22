# Rebuild runbook — LAPTOP-4PLJH17D, 2026-09-22

**Read this from GitHub on another device.** The machine it describes gets wiped.

**Why.** Admin-level execution for six hours on 2026-09-09, origin never recovered,
active anti-forensics (Defender exclusion written 13s before the staging folder;
prefetch records deleted). Nothing available on the host can establish it is clean —
today's Malwarebytes pass can't either (Threat Scan, rootkits disabled, trial licence).
Confirmed downstream use of the stolen credentials is recorded in
[credential-use-confirmed-2026-09-22.md](credential-use-confirmed-2026-09-22.md).

---

## Phase 0 — Do now, independent of the rebuild

**Six API keys in `env.env` were never rotated.** The 2026-09-17 list covered
`CFBD-API` and `MOTHERDUCK_TOKEN`. The file holds eight keys. It is plaintext, 14
lines, and sat on the box throughout the six-hour window.

Unrotated as of this writing:

- [ ] `ANTHROPIC_API` — **billable, rotate first**
- [ ] `OPENAI_API` — **billable, rotate first**
- [ ] `ODDS_API`
- [ ] `ODDSPAPI_API`
- [ ] `PFF_API`
- [ ] `PFF_WEB_COOKIE` — a session cookie; invalidate by signing out of PFF everywhere,
      a password change alone will not do it

Check billing/usage dashboards on the two paid APIs before rotating — unexpected spend
since 9/9 is evidence the keys were used, and belongs in the record.

This is the same failure as Steam and Amazon: the rotation list was scoped to what
someone enumerated, not to what the attacker could read.

---

## Phase 1 — Preserve (the part with a deadline)

Everything here is lost on wipe and exists nowhere else.

### 1.1 Unpushed git commits

```bash
cd ~/dev/cfb
git push -u origin chore/land-september-backlog    # 16 commits, no upstream
git push -u origin worktree-agent-af40be9cf478151a6 # 3 commits, no worktree checked out
```

The second has no working directory pointing at it — it is the least visible item here
and the easiest to lose. Verify nothing else is stranded:

```bash
for b in $(git for-each-ref --format='%(refname:short)' refs/heads/); do
  n=$(git rev-list --count $b --not --remotes); [ "$n" != "0" ] && echo "$b -> $n"
done
```

Expect empty output when done.

### 1.2 Stashes — `git push` does not see these

Three exist. Export each as a patch:

```bash
cd ~/dev/cfb
git stash list
for i in 0 1 2; do git stash show -p "stash@{$i}" > ~/stash-$i.patch; done
```

Then get the patches off the machine (see 1.5). Re-apply after with `git apply`.

### 1.3 Orphaned worktree directories

Registered worktrees and directories on disk disagree. Registered: `heuristic-jepsen-d3a03a`,
`trusting-shamir-a1b69b`, `vibrant-dewdney-95a26f`. On disk additionally:
`agent-abdd7df49ccb3077b`, `ship-phase3-polish`.

```bash
git worktree list
ls -d .claude/worktrees/*/
```

Reconcile the two. An unregistered directory holding real commits is the classic thing a
rebuild eats silently — check each unregistered one for its own `.git` and commits before
accepting the loss.

### 1.4 The Obsidian vault — highest-value item, currently unbacked

`C:\Users\mckel\Documents\Obsidian\obsidian-master`, **2.9 GB**. Verified on 2026-09-22:
no `.git`, no `.obsidian/sync.json`, and not under either OneDrive sync root. It holds
`permanent/malware-origin-trace-2026-09-17.md` and the three forensic tools
(`srum_app_network.py`, `collect_exec_artifacts.ps1`, `chrome_history_window.py`) —
the entire record of this incident, irreplaceable.

- [ ] Copy the whole vault to external media before anything else

### 1.5 Other local-only state

- [ ] `.remember/` (7 MB) — session history, gitignored
- [ ] `.claude/settings.local.json` — local config and permission rules
- [ ] `~/stash-*.patch` from 1.2

**Copy to external media, not to cloud storage.** The cloud credentials were exposed and
their rotation is unverified; do not use those accounts as the transfer path.

### 1.6 `env.env` — copy the key NAMES, never the file

The values are burned. Copying the file forward re-lands compromised credentials on the
clean box — the identical mistake as carrying `rclone.conf` across (see
[rclone-credential-exposure-2026-09-21.md](rclone-credential-exposure-2026-09-21.md)).

```bash
grep -oE '^[A-Za-z_][A-Za-z0-9_-]*[ ]*=' env.env | sed 's/[ ]*=$//' | sort -u
```

Keep only that list, to know what to refill.

### 1.7 What needs no backup

- Anything pushed to `origin/master`
- `data/` (17 GB) — rebuilds from source via `refresh_cfbd.py`. Slow, not lost.
- `.venv/`, `.venv-cfbd/` — rebuild from requirements

---

## Phase 2 — Wipe

- [ ] Full clean install from Microsoft's own media, downloaded on a **different** machine.
      Not "Reset this PC" — that preserves partitions and, potentially, persistence.
- [ ] Delete and recreate all partitions during setup

---

## Phase 3 — Rebuild, in this order

**Before restoring anything:**

- [ ] **Enable Event 4688 process-creation auditing.** Carried forward unresolved since
      2026-09-17. It is a Group Policy checkbox and it is the only durable fix for the
      dead end that made this incident's origin unrecoverable. Do it while the box is empty.
- [ ] Confirm Defender is on with no path exclusions — the 9/9 payload wrote one
- [ ] Sort out AV: Malwarebytes is on a trial licence

**Then:**

- [ ] `git clone` the repo fresh. Do not restore the old working directory.
- [ ] Recreate `env.env` by hand from the 1.6 name list, with newly issued keys
- [ ] `rclone config` each of the four remotes by hand — `gdrive`, `pcloud`, `b2`,
      `allclouds`. Never copy the old `rclone.conf`.
- [ ] Rebuild the B2 mount (`mount-b2.cmd`, `rclone-b2-mount` task)
- [ ] Rebuild `.venv` and `.venv-cfbd` from requirements — pydantic versions differ
      between them, that split is deliberate
- [ ] `refresh_cfbd.py` to rebuild `data/`. Do not call `build_duckdb` directly; it skips
      the AN tick flatten.
- [ ] Copy the Obsidian vault back, and this time give it a backup — git remote or
      Obsidian Sync
- [ ] Re-apply stash patches with `git apply`

---

## What must NOT be restored

Nothing executable or configuration-bearing dated after 2026-09-09:

- Browser profiles (this is how the cookies would return)
- `AppData` trees, in whole or in part
- `env.env`, `rclone.conf`, or any credential file
- "Settings backup" images of any kind
- Installers cached on the old disk — re-download everything from source

Data files and git repos are fine. The trap is configuration and profile restore.

---

## What this rebuild does *not* fix

**The vector is still unknown.** Whatever ran at 09:34 on 9/9 arrived somehow, and the
9/17 investigation could not recover it — BAM aged out, prefetch deleted, Amcache empty,
4688 off. A clean install with the same habits and the same download paths is re-exposed
on day one. Treat "how did this get in" as open after the rebuild, not closed by it.

Also unaffected: the full `chrome://password-manager/passwords` sweep still needs doing,
two steps per account — rotate the password, then revoke sessions. The second is what
evicts a stolen cookie, and a rebuild does nothing about a cookie already in someone
else's browser.

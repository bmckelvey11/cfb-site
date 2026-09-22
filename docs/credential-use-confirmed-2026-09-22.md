# Exfiltrated credentials were used, not just taken — 2026-09-22

**Question.** The 2026-09-09 malware run is a confirmed exfiltration of 267.9 MB
(memory `machine-compromise-2026-09-09`; full forensics in
`Obsidian/obsidian-master/permanent/malware-origin-trace-2026-09-17.md`). That
investigation could bound the *volume* that left but stated plainly that it had
"no evidence either way about what it took" — SRUM records bytes per application,
never payloads or destinations. Did the stolen data actually get used?

**Method.** Not host forensics. The 9/17 investigation exhausted that avenue: BAM
had aged out, prefetch records were deleted, Amcache never held the binary, and
process-creation auditing (Event 4688) was off. This record instead uses
**downstream account compromise dates** as a second, independent clock, reported
by the account holder on 2026-09-22 during an unrelated Malwarebytes triage:

- which accounts were compromised, and on what date
- whether each account's password was stored in Chrome's credential store
- whether each account appeared on the 2026-09-17 rotation list

No account-side logs (Amazon sign-in history, Steam login records) were pulled;
these are holder reports, not vendor data.

## Findings

**Two accounts were compromised, neither on the rotation list.** The 9/17 writeup
enumerated ten credentials to rotate: Google, Meta, Discord, `CFBD_API_KEY`,
MotherDuck, GitHub/`sites`, B2, pCloud, Drive, MEGA. All ten were rotated on
2026-09-22. Neither compromised account was among them.

| Account | Compromised | Password in Chrome | On rotation list |
| --- | --- | --- | --- |
| Amazon | **2026-09-14** | Yes | No |
| Steam | date not established | not established | No |

**The Amazon chain closes end to end.** Three links, each established independently
and before this record:

1. Chrome's credential store was readable by an admin-level process from 09:34 to
   15:34 EDT on 9/9 (9/17 forensics).
2. 267.9 MB left the machine at 09:45 on 9/9, against 1.4 MB inbound — a 200:1
   outbound ratio, eleven minutes after launch, with `7za.exe` staged alongside
   (9/17 SRUM analysis).
3. The Amazon password was stored in that credential store, and the account was
   compromised on 9/14 — five days later, while the credential was still live and
   eight days before rotation.

A five-day gap between theft and use is the ordinary stealer-log economics: dumped,
sold or traded on a marketplace, then worked by a buyer. It is not evidence against
the chain.

**The enumeration, not the rotation, was the failure.** The ten-item list was
assembled from dev and cloud secrets — the things visible from a repo and a shell
profile. But the exposed set was *every password saved in Chrome*. Both accounts
that were actually hit held resellable value (Steam inventory; Amazon stored payment
and gift-card balance), which is what an operator converts first. Scoping a rotation
by what someone enumerated, rather than by what the attacker could read, left the
highest-value targets untouched for thirteen days.

**Session cookies were in the same blast radius and are not addressed by rotation.**
A process reading Chrome's credential store reads its cookie jar in the same pass.
Rotating a password does not invalidate a stolen session cookie; that requires an
explicit sign-out-all-devices or session-revoke per service. Any account protected
by 2FA that was still compromised is consistent with cookie replay rather than
password reuse, so this is part of the mechanism, not an alternative to it.

## What this does *not* support

- **It does not exclude credential stuffing for Amazon.** If that password was
  reused on a site with its own breach, a 9/14 compromise has a second explanation
  independent of 9/9. `chrome://password-manager/checkup` flags both reuse and
  appearance in known third-party breaches; it had not been run against that entry
  when this record was written. A unique, unflagged password would leave the 9/9
  exfil as the only remaining explanation.
- **It says nothing about Steam.** The date and the Chrome-storage question were both
  unestablished. Steam corroborates the pattern; the Amazon chain does not depend on it.
- **It does not identify what else was taken.** Two confirmed uses out of an unknown
  set. Absence of reports from other accounts is not evidence they were untouched.
- **It does not name a destination or an operator.** SRUM records volume per app and
  never remote addresses; that limit from 9/17 still stands.
- **These are holder reports.** No vendor-side sign-in logs were retrieved for either
  account.

## What this revises

The 9/17 writeup's "no evidence either way about what it took" was accurate when
written and is now superseded on that one point: there is evidence, and it points to
use. That doc is a dated record and is **not** edited — this record supersedes that
sentence only, and nothing else in it.

## Action

1. Revoke Amazon's active sessions and audit **Archived Orders** — the unauthorized-purchase
   reporting window for a 9/14 order is open but closing.
2. Run `chrome://password-manager/checkup` against the Amazon entry to settle the reuse
   alternative above.
3. Sweep every entry in `chrome://password-manager/passwords`, prioritised by blast radius
   (stored payment method; recovery address for another account; convertible balance).
   **Two steps per account: rotate the password, then revoke sessions.** The second is what
   evicts a stolen cookie.
4. Enable Event 4688 auditing. Carried forward unresolved from 9/17; it remains the only
   durable fix for the class of dead end that made the origin unrecoverable.

## Reproduce

There is no script. The method is a question set applied to each newly-discovered
compromised account:

```
1. Date the compromise was noticed, and the last known-good date.
2. Was the password stored in Chrome's credential store on 2026-09-09?
3. Was the account on the 2026-09-17 rotation list?
4. Was a link clicked / a phishing vector present? (rules the chain in or out)
5. chrome://password-manager/checkup — reused, or seen in a third-party breach?
```

Record 1–5 per account. A compromise dated after 2026-09-09, with the password in
Chrome, no phishing vector, and a unique unbreached password, is another closed chain.

---
task: total-filter-semantics-fixes
date: 2026-08-26
status: complete
---

# Summary: Total-system filter semantics fixes (audit findings 1-3)

Three commits on `fix/web-app-review-2026-08-26`, all 432 tests green:

1. **d9c93e4** — `matches_system` team/conference filters on total systems now
   match either side of the game (spread systems unchanged: bet-side only).
   Modal buckets each game under both teams for totals; core:team /
   core:conference descriptions state the split semantics.
2. **5040b31** — bet_side/opponent perspectives on totals: strict API parsing
   rejects them (`invalid_perspective`, extending a1e6e19 to /api/backtest);
   form parsing and storage loads collapse them to "either" via new
   `features.effective_perspective`, so legacy saves resolve deterministically
   and describe() discloses the applied perspective.
3. **249b541** — modal Save clears numeric feature bounds sitting at the
   observed domain edges (mirrors core ranges) and `draftQuery` applies the
   same rule so live preview chips match the commit. Browser-verified:
   full-domain weather_temperature draft previews and commits the full
   6292-6428-233 record with no committed filter.

Also committed separately first: 3a6e247 (pre-existing uncommitted chart-axis
work in filter_modal.js, isolated so the fix diffs stay clean).

New tests: either-side matching, modal tuple buckets, /api/backtest 400s,
form/storage perspective normalization, JS contract for edge-bound clearing.

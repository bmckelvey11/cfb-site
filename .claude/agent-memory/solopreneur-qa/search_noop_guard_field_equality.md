---
name: search-noop-guard-field-equality
description: In cfb_system_maker/search.py candidate generation, the no-op guard compares SystemFilter field equality, not behavioral equality against matches_system — this misses dimension-consuming children that select the exact same games as their parent.
metadata:
  type: project
---

Found in MVP-002 QA (2026-07-23): `expand_candidates`' no-op guard (`child == parent`)
rejects only children that are *field-identical* to the parent. It does not check
whether the child actually changes which games `matches_system` selects.

**Concrete case**: for a `bet_type="total"` parent, `matches_system` only reads
`favorite`/`underdog` inside the spread branch and `home`/`away` bite only when
paired with a team/conference filter. So `expand_candidates` on a `bet_type="total"`
parent still emits `favorite=True`, `underdog=True`, `home=True`, `away=True`
children — each of which matches the identical game set as the parent (verified
empirically: all four produced the same `matched_ids` as the untouched parent).
These pass the literal no-op guard but are behaviorally no-ops: they burn a
dimension slot in MVP-003's beam search and can seed duplicate-performing
candidates.

**Why this matters**: MVP-003's beam search consumes `expand_candidates` output
directly. Phantom dimensions reduce effective search diversity within the
dimension cap (default 4) without the caller being able to tell from the
`SystemFilter` alone — you'd need to cross-check against `matches_system` output
to notice.

**How to apply**: When reviewing MVP-003 (beam search/evaluation) or any future
search.py changes, check whether `expand_candidates` is scoped by `bet_type`
consistently — `spread_range` is already correctly gated on
`parent.bet_type == "spread"` (see `_DIM_SPREAD_RANGE not in active and
parent.bet_type == "spread"` in search.py), but `favorite_underdog` and
`home_away` are not gated on bet_type at all. If this surfaces again in a
different form, the fix pattern is likely: gate `favorite_underdog` to
`bet_type == "spread"` unconditionally (matches_system never reads those flags
for totals), and gate `home_away` production to only fire when it's paired with
something that makes it selective for totals (or just also restrict to spread
bets, since Bet Labs total systems aren't typically home/away scoped either).
Rated Warning, not Critical — this is a search-space quality issue, not a
data-leakage or stats-correctness bug, because `run_backtest` still grades each
surfaced candidate honestly against real results.

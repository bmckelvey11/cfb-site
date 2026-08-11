---
name: search-season-guard-label-vs-membership
description: cli.py _search's zero-in-sample/holdout guard checks season-label set membership, not actual filtered game-list length — a season label with zero real games (e.g. a typo'd --season) passes the guard and silently runs a search on an empty in-sample set.
metadata:
  type: project
---

Found in MVP-005 QA (2026-07-30): `_search` in `cfb_system_maker/cli.py` guards against an
empty in-sample/holdout split like this:

```python
scoped_seasons = set(args.season) if args.season else available_seasons
holdout_seasons = {args.holdout_season} & scoped_seasons
in_sample_seasons = scoped_seasons - holdout_seasons

if not in_sample_seasons:
    ...error=empty_in_sample...
if not holdout_seasons:
    ...error=empty_holdout...
```

This checks whether the **season label set** is non-empty, not whether the resulting
**game list** (`[g for g in games if g.season in in_sample_seasons]`) is non-empty. A
season value that isn't in `available_seasons` (e.g. `--season 1999 --season 2024` when
the data only has 2023/2024) still leaves a non-empty label set (`{1999}`), so the guard
passes — but zero actual games have that season. Confirmed empirically: `search
--holdout-season 2024 --season 1999 --season 2024` exits **0** with
`finalists_graded=0` and no error, having beam-searched over zero in-sample games (only
the 4 games-independent dimension children — favorite/underdog/home/away — get
generated, then all pruned on `decided=0`).

**Why this matters**: this is the same failure class AC #5 (empty-in-sample refusal)
exists to prevent, just relocated one level above `split_holdout` — `_search` computes
its own season split manually instead of delegating to `split_holdout`, and its guard
checks the wrong thing (labels, not membership). A user who fat-fingers a `--season`
value gets a silent "successful" empty search instead of a clear error.

**How to apply**: when reviewing changes to `_search`'s season-scoping guard (or any
future rewrite that computes `in_sample_games`/`holdout_games` from season sets), check
that the emptiness guard is on the **filtered game list**, not the **season label set**.
Correct fix is `if not in_sample_games: ...error...` / `if not holdout_games: ...error...`
computed after building `in_sample_games`/`holdout_games`, not before. Also worth
rejecting `--season` values absent from `available_seasons` outright (mirrors the
existing `unknown_holdout_season` check), rather than only catching the resulting
zero-games symptom. Rated Warning in MVP-005 review (exits 0, wrong-but-not-crashing,
narrow trigger condition — not a holdout-leakage bug, no data crosses the in-sample/
holdout boundary, just an empty in-sample set slips through silently).

Related: [[search_noop_guard_field_equality]] — another case in the same file where a
guard checks the wrong level of abstraction (field equality vs behavioral equality;
season labels vs season membership).

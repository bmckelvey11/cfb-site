# Memory Index

- [Stats test discrimination](stats_test_discrimination.md) — check test vectors actually fail on plausible buggy BH/p-value implementations, not just pass on the correct one
- [search.py no-op guard is field-equality only](search_noop_guard_field_equality.md) — favorite/underdog/home/away children on bet_type=total parents are behaviorally no-ops but pass the literal guard
- [_search season guard checks labels not membership](search_season_guard_label_vs_membership.md) — bogus/typo'd --season value passes empty-in-sample guard, silently runs search on zero games, exits 0

# Phase 9: Pre-Season Calendar Dry Run — Result

**Run:** 2026-08-27
**Criterion:** Success criterion 1 of Phase 9 (Live In-Season Verification) — the only criterion with no date gate.

> "A pre-season dry run against a live-but-past CFBD calendar date confirms whether `GamesApi.get_calendar()` returns `startDate`/`endDate` as `str` or `datetime` in production, and the live-calendar branch handles whichever shape is returned (closes the untested-path risk before it's exercised for real)."

## Result: PASSED

Ran the real `GamesApi.get_calendar(year=2025)` call against the live CFBD API (not fixtures, not mocks) and then `upcoming.resolve_target_week()` end-to-end against a live-but-past date.

### Raw field types

```python
{'season': 2025, 'week': 1, 'seasonType': <SeasonType.REGULAR: 'regular'>,
 'startDate': datetime.datetime(2025, 8, 23, 7, 0, tzinfo=timezone.utc),
 'endDate': datetime.datetime(2025, 9, 2, 6, 59, tzinfo=timezone.utc), ...}
```

`startDate`/`endDate` are real timezone-aware `datetime` objects, **not `str`**. This matches what `tests/test_upcoming.py`'s fixtures already inject — the type-mismatch risk PITFALLS.md (Pitfall 5) flagged does not materialize in production.

### End-to-end resolution

```python
now = datetime(2025, 9, 20, 12, 0, 0, tzinfo=timezone.utc)
resolve_target_week(now)
# -> WeekResolution(season=2025, week=4, season_type='regular', is_fallback=False)
```

The live-calendar primary branch fired (`is_fallback=False`, not the offseason fallback), the `start <= now <= end` comparison worked correctly against real `datetime` objects, and the correct week (4, for a date in the third full week of the season) was resolved. No `TypeError`, no exception, no silent mismatch.

### Environment note (unrelated to this criterion, worth flagging)

Running this required the project's `.venv` (pydantic 1.10.26, matching `requirements.lock`) rather than the system Python 3.14 install (pydantic 2.13.4) — the latter fails to import the vendored `cfbd-python` client at all (`PydanticUserError: 'const' is removed, use 'Literal' instead`). This was discovered while running this dry run, not caused by it. Also found: `.venv` is missing `waitress` (2 failing tests in `tests/test_cli.py`, unrelated to Phase 9 — added by the concurrent `ship-phase3-polish` deployment work). Neither issue blocks this criterion; both are recorded here for whoever next runs the full suite or Phase 9's remaining criteria.

## Remaining Phase 9 criteria (not run — genuinely calendar-gated)

- **Criterion 2**: Current Matches shows real posted-line games — needs the 2026 season underway (~2026-08-29).
- **Criterion 3**: Season-to-date feature filters correctly match upcoming games — needs week 3+ specifically (week 1-2 `games_played=0` fails closed by design, not a bug).

Resume with `/gsd-plan-phase 9` or `/gsd-autonomous --from 9` after those dates pass.

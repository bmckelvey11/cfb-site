# Spec: New System type catalog

Status: draft — waiting on human review
Intent: [docs/intent/new-system-type-catalog.md](../../intent/new-system-type-catalog.md)

## Assumptions (correct these before implementation)

1. This is a change to the existing Flask editor at `/system` in this repo (`cfb_system_maker`), not a new app in `over-zero-dashboard`.
2. Dashboard **New system** already opens `/system` with a **Spread / Over/Under** dropdown and a separate Over/Under control. That page/dropdown is kept. The gap is the team-pair chips: totals currently collapse to **Either**, not **Home / Away**.
3. `SystemFilter.home` / `SystemFilter.away` (situation flags: only home games / only away games) are **not** this feature. Totals home/away means the two teams’ stats in the game.
4. Changing Spread ↔ Total remaps in-place on `/system` (same route, query updates). No second wizard URL.
5. Remap on type change: `bet_side` ↔ `home`, `opponent` ↔ `away`. Shared stat filters keep their values.
6. Saved totals that already use `either` stay valid and still grade. The new UI does not offer **Either** as the pair. No bulk rewrite of saved systems.
7. Favorite / underdog stay spread-only (already greyed on totals). Core team/conference include filters stay “game involves this team,” not a home/away chip pair.
8. CLI, search, compare, warehouse, and `games.csv` are unchanged.

→ Correct these or the spec is wrong.

## Objective

One editor. Type dropdown swaps the team-pair chips so you can build a spread system and a totals system without the wrong labels.

- Spread: team-scoped stats keep **Bet-side / Opponent**.
- Total: that same dual-chip row relabels to **Home / Away**. Perspectives stored as `home` / `away` (already valid in `resolve_storage_key`). Over/Under stays the existing `total_side` control.
- Stats stay one catalog. No second editor.

## Tech Stack

Existing Flask + Jinja + vanilla JS. Engine: `SystemFilter.bet_type`, `FeatureFilter.perspective`, `resolve_storage_key`. No new dependencies.

## Commands

```
pip install -r requirements.lock
python -m pytest tests/test_filter_modal.py tests/test_web.py tests/test_web_features.py tests/test_describe.py tests/test_features.py
python -m pytest
python -m cfb_system_maker web --data-dir data --port 5000
```

(`--data-dir` still wins; canonical dir is `CFB_DATA_ROOT`.)

## Project Structure

```
docs/intent/new-system-type-catalog.md          → confirmed intent
docs/superpowers/specs/2026-09-01-new-system-type-catalog.md  → this spec
cfb_system_maker/templates/index.html          → dual chips + labels
cfb_system_maker/static/filter_modal.js          → default perspective, fieldset sync
cfb_system_maker/web.py                         → default_perspective, parse, filter-detail
cfb_system_maker/features.py                    → effective_perspective (do not map home/away to either)
cfb_system_maker/describe.py                    → Home / Away sentences (already have prefixes)
cfb_system_maker/templates/dashboard.html         → New system → /system (already)
tests/test_filter_modal.py                      → perspective + UI contract
tests/test_web.py / test_web_features.py
```

Do not add a new route or template for “new system.”

## Code Style

Match the existing dual-chip row. Totals should take the same branch, with labels and `data-perspective` swapped:

```html
{% set primary_p = 'bet_side' if form.bet_type == 'spread' else 'home' %}
{% set secondary_p = 'opponent' if form.bet_type == 'spread' else 'away' %}
```

Buttons: `Bet-side` / `Opponent` on spread; `Home` / `Away` on total. Same `stat-row` markup, not a single launcher.

`effective_perspective` must **not** turn `home`/`away` into `either`. Keep collapsing **only** legacy `bet_side`/`opponent` on loaded total systems (old saves), so they do not misresolve against `SystemFilter.side`.

## Testing Strategy

Pytest. Default `python -m pytest` is `-m "not slow"`. Construct `SystemFilter` / parse form dicts; assert on HTML and parse results. No new browser suite unless `/system` chip labels need a Playwright check (then `-m slow`).

Must cover:

- `/system?bet_type=total` renders Home / Away launchers on a team-scoped numeric, not a single Either button.
- `/system?bet_type=spread` still renders Bet-side / Opponent.
- New totals filter defaults to `home`, not `either`.
- Form parse accepts `home`/`away` on `bet_type=total` and does not coerce them to `either`.
- `filter-detail` for `perspective=home` on a total system: `overlapping_rows` is false (one value per game).
- `describe()` says “Home …” / “Away …”, not “Either team's …” for those filters.
- Existing totals with `either` still load and backtest.

Update tests that currently encode the old contract (`test_default_perspective_spread_bet_side_total_either`, `test_form_parse_normalizes_bet_side_to_either_on_totals`, HTML that expects a single totals launcher).

## Boundaries

- **Always:** Keep one `/system` editor. Persist perspectives as `home`/`away`/`bet_side`/`opponent`. Run the listed pytest files before calling this done. Grey favorite/underdog on totals.
- **Ask first:** Delete `either` from the engine; auto-migrate saved `either` filters to home+away; change CLI `--side` for totals; add a new route; change dashboard beyond the existing New system link.
- **Never:** Two editors or two stat menus. Treat home/away as “only home games.” Fold Over/Under into the team-pair chips. Edit `cfbd-python/`. Add `games.csv` columns. Write MotherDuck.

## Success Criteria

- From dashboard, **New system** opens `/system` (blank). Type dropdown is at the top.
- On Spread: team-scoped stats show Bet-side and Opponent.
- On Over/Under: that row shows Home and Away; Over/Under remains its own control.
- You can set home SP+ and away SP+ independently on a totals system and backtest it.
- Switching the dropdown on a filled form remaps `bet_side`→`home` and `opponent`→`away` (and the reverse) without going to a different path.
- Stat search/list is the same set for both types.
- Compare, search, CLI, and saved `either` totals still work.

## Open Questions

1. Type-change remap total → spread: `home` → `bet_side` and `away` → `opponent` — yes?
2. If a loaded totals system has `either` filters, show them as a third chip, as read-only sentence text, or leave them only in the sentence list until edited?
3. On type change, should the form auto-submit (reload `/system` with new query) or should JS rewrite chip labels without a reload?

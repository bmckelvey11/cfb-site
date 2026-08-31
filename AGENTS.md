## Learned User Preferences

- Prefer local `$CFB_DATA_ROOT/cfb.duckdb` (`C:\Users\mckel\data\cfb`) for warehouse catalogs, explode, and schema work; MotherDuck `md:cfb` lags and is a manual mirror — do not treat it as the working copy.
- Warehouse catalogs should describe tables, exploded columns, and named box/play stats — not Bet Labs `FEATURE_REGISTRY` or app features.
- New stats (tempo, seconds between plays, etc.) belong in the feature registry, not new `games.csv` columns or a new table; compute from `stg.drives` (`elapsed`/`plays`) or `stg.plays`.

## Learned Workspace Facts

- `stg.plays` is exploded in the local warehouse. Rebuild with `python -m cfb_system_maker duckdb --explode-only --only plays`; infer JSON shape from a sample (`json_group_structure` over all of `raw.plays` OOMs). Filename `season`/`week`/`season_type` plus flattened `clock_minutes`/`clock_seconds`.
- `stg` browse column order is identity → time → home/offense → away/defense → leftover → `_source_file` last.
- `stg` PK `id` columns are renamed to the FK they join on (`gameId`, `playId`, `driveId`, `teamId`, `athleteId`, `conferenceId`, `venueId`, …); explode/`--rename-ids` reapplies this.
- Action Network staging is special-cased: `stg.actionnetwork_history` is one row per offering (event × book × period × market × side); `stg.actionnetwork_scoreboard` is one row per game. Generic explode pivots book ids / week blobs and is wrong. Use history for 1H/1Q prices; scoreboard for matchup/scores (`markets` still JSON).
- Local warehouse HTML catalog is `docs/cfb-warehouse-catalog.html` (local file is fuller than `md:cfb` and includes `core`). GraphQL dumps load into `raw`, not a `graphql` schema.

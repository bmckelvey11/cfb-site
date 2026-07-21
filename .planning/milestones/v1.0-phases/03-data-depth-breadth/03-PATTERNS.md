# Phase 03: Data Depth & Breadth - Pattern Map

**Mapped:** 2026-07-17
**Files analyzed:** 6 modules + 3 test files (backend/data phase, NO UI files)
**Analogs found:** 6 / 6 (every new construct replicates an existing in-repo instance)

> This phase invents no new mechanism. Every deliverable is a *replication* of one
> representative existing instance: PPA to-date → advanced to-date; existing `FeatureDef`
> rows → new rows; existing `ppa` enrich index → new `adv` index; existing `--season nargs`
> fetch loop → bounded probe. The analogs below are the exact copy-from sources.

## File Classification

| New/Modified File | Role | Data Flow | Closest Analog | Match Quality |
|-------------------|------|-----------|----------------|---------------|
| `cfb_system_maker/running_stats.py` (MODIFY: add `adv` kwarg + accumulation) | compute/service | transform (strictly-prior accumulation) | itself — existing `ppa` arg path | exact (self, same-file pattern) |
| `cfb_system_maker/enrich.py` (MODIFY: build `adv` index in `_build_running_index`) | service (index/join) | batch/transform | itself — existing `ppa` dict at `enrich.py:120-132` | exact |
| `cfb_system_maker/features.py` (MODIFY: add `FeatureDef` rows) | model/config (registry) | CRUD (declarative rows) | existing `running_ppa_off/def` rows `features.py:150-151` | exact |
| `tests/test_running_stats.py` (MODIFY: add adv no-lookahead cases) | test | request-response (construct + assert) | `test_running_ppa_is_average_of_prior_games_only` `:99-118` | exact |
| `tests/test_features.py` (MODIFY: registry row + version assertions) | test | construct + assert | existing group/`RUNNING_KEYS` checks | role-match |
| `tests/test_normalize.py` (MODIFY: empty-`lines` → 0 rows) | test | construct + assert | existing `_select_line` tests | role-match |
| DATA-01 live probe script (NEW, throwaway) | utility/script | request-response (network) | `cfbd_client.fetch_games_and_lines` `:9-31` | role-match |
| `cfb_system_maker/cli.py` (optional MODIFY: floor guard/doc) | controller (arg dispatch) | request-response | existing `_fetch`/`_build` `:56-73` | exact |

**Not modified (verified sufficient as-is):**
- `enrich._lookup` `computed_running` branch (`enrich.py:215-219`) — already returns `(home_stats.get(field), away_stats.get(field))` for *any* field. New D-03 fields need **no new `_lookup` branch**.
- `normalize._select_line` (`normalize.py:46-56`) — D-02 "require a usable line" behavior is already correct; do not touch, only add a test asserting it.
- `features.SourceKind` Literal (`features.py:10-27`) — D-03 reuses `"computed_running"`; **no new SourceKind** unless D-05 is built.

## Pattern Assignments

### `cfb_system_maker/running_stats.py` (compute, transform) — D-03 to-date advanced stats

**Analog:** itself — the existing `ppa` accumulation path is the exact template.

**Signature to extend** (`running_stats.py:8-15`) — add an `adv` dict kwarg mirroring `ppa`:
```python
def compute_running_stats(
    games: list[GameRecord],
    *,
    ppa: dict[tuple[int, str], tuple[float | None, float | None]] | None = None,
    # NEW: adv: dict[tuple[int, str], dict[str, float | None]] | None = None,
    start_dates: dict[int, str] | None = None,
) -> dict[tuple[int, str], dict[str, Any]]:
    ppa = ppa or {}
    # NEW: adv = adv or {}
```

**Per-team-season init** (`running_stats.py:26-29`) — add running sums/counts per new field beside the PPA ones:
```python
        played = wins = losses = 0
        ats_wins = ats_losses = 0
        ppa_off_sum = ppa_def_sum = 0.0
        ppa_off_count = ppa_def_count = 0
        # NEW: adv_success_off_sum = 0.0; adv_success_off_count = 0  (per registered field)
```

**CRITICAL ordering — write entering stats BEFORE folding current game** (`running_stats.py:31-40`):
```python
        for _sort_key, game_id, game, side in entries:
            ...
            stats[(game_id, team)] = {
                "games_played": played,
                "win_pct": round(wins / decided, 4) if decided else None,
                "ats_pct": round(ats_wins / ats_decided, 4) if ats_decided else None,
                "ppa_off": round(ppa_off_sum / ppa_off_count, 4) if ppa_off_count else None,
                "ppa_def": round(ppa_def_sum / ppa_def_count, 4) if ppa_def_count else None,
                # NEW: "adv_success_off": round(adv_success_off_sum / adv_success_off_count, 4)
                #                          if adv_success_off_count else None,
            }
            # ... points/wins/ats accumulation ...
```

**Fold-in AFTER the write** — mirror the PPA fold (`running_stats.py:59-67`), reading from `adv` not `ppa`:
```python
            game_ppa = ppa.get((game_id, team))
            if game_ppa:
                off_value, def_value = game_ppa
                if off_value is not None:
                    ppa_off_sum += float(off_value); ppa_off_count += 1
                ...
            # NEW: game_adv = adv.get((game_id, team))
            #      if game_adv and game_adv.get("success_off") is not None:
            #          adv_success_off_sum += float(game_adv["success_off"]); adv_success_off_count += 1
```

**Methodology decision (Claude's discretion A2 — name it, don't silently pick):** accumulate as
**game-average** (parity with PPA path, matches the `9.99`-leak test) vs **play-weighted**
(`advanced_game_stats` carries `plays`/`drives`). Recommend game-average for parity/testability.

---

### `cfb_system_maker/enrich.py` (service, batch) — build the `adv` index

**Analog:** the existing `ppa` dict in `_build_running_index` (`enrich.py:120-140`).

**Existing ppa index (copy this shape)** (`enrich.py:120-132`):
```python
    ppa: dict[tuple[int, str], tuple[float | None, float | None]] = {}
    for season in seasons:
        path = data_dir / "raw" / f"ppa_games_{season}.json"
        if not path.exists():
            continue
        for row in json.loads(path.read_text(encoding="utf-8")):
            game_id = row.get("gameId") if row.get("gameId") is not None else row.get("game_id")
            team = row.get("team")
            if game_id is None or team is None:
                continue
            offense = row.get("offense") or {}
            defense = row.get("defense") or {}
            ppa[(int(game_id), str(team))] = (offense.get("overall"), defense.get("overall"))
```

**New adv index — same loop over `advanced_game_stats_{season}.json`**, then pass into
`compute_running_stats(games, ppa=ppa, adv=adv, start_dates=start_dates)` at `enrich.py:140`.

**CORRECTION to RESEARCH code example (verified on disk):** the research example (03-RESEARCH.md
lines 288-292) accesses `(off.get("successRate") or {}).get("total")`. That is **wrong for this
data**. In `advanced_game_stats_{season}.json`, `offense.successRate` is a **direct float**, not a
nested object. Verified structure (`advanced_game_stats_2015.json[0]`):
```
row keys: ['defense', 'gameId', 'offense', 'opponent', 'season', 'seasonType', 'team', 'week']
row['team'] = 'Alabama'
row['offense']['successRate'] = 0.4696969696969697   # float, NOT {'total': ...}
row['offense']['explosiveness'], row['offense']['ppa']  # also direct floats
row['offense']['passingDowns'|'standardDowns'|'rushingPlays'|'passingPlays']  # these ARE nested {successRate, ppa, explosiveness}
```
So the correct index build is:
```python
    adv: dict[tuple[int, str], dict[str, float | None]] = {}
    for season in seasons:
        path = data_dir / "raw" / f"advanced_game_stats_{season}.json"
        if not path.exists():
            continue
        for row in json.loads(path.read_text(encoding="utf-8")):
            gid, team = row.get("gameId"), row.get("team")
            if gid is None or team is None:
                continue
            off, deff = row.get("offense") or {}, row.get("defense") or {}
            adv[(int(gid), str(team))] = {
                "success_off": off.get("successRate"),          # direct float
                "explosiveness_off": off.get("explosiveness"),
                "success_def": deff.get("successRate"),
                # nested splits use the sub-dict: (off.get("passingDowns") or {}).get("successRate")
            }
```
Key spelling is `gameId` / `team` (camelCase; no snake fallback needed here, but the existing ppa
loop's dual-spelling guard is the safer pattern to copy). Empty files are skipped (`if not path.exists`)
and `advanced_game_stats_2012.json` exists but 2012 has no built games, so it never joins.

**No `_lookup` change** (`enrich.py:215-219`) — `computed_running` already returns any `field`:
```python
    if feature.source_kind == "computed_running":
        running = indexes["computed_running"]
        home_stats = running.get((game.game_id, game.home_team)) or {}
        away_stats = running.get((game.game_id, game.away_team)) or {}
        return (home_stats.get(feature.field), away_stats.get(feature.field))
```

---

### `cfb_system_maker/features.py` (registry) — new `FeatureDef` rows

**Analog:** existing to-date rows (`features.py:147-151`). Copy exactly, changing key/label/field:
```python
    FeatureDef("running_ppa_off", "Off PPA (to date)", "season_to_date", "computed_running", "ppa_off", "game_id", "numeric", team_scoped=True),
    FeatureDef("running_ppa_def", "Def PPA (to date)", "season_to_date", "computed_running", "ppa_def", "game_id", "numeric", team_scoped=True),
    # NEW (one per accumulated field; `field` must match the key written in compute_running_stats):
    # FeatureDef("running_success_off", "Off Success Rate (to date)", "season_to_date", "computed_running", "adv_success_off", "game_id", "numeric", team_scoped=True),
```
Field order in `FeatureDef` is positional: `key, label, group, source_kind, field, join, control`,
then keyword `team_scoped=True`. `field` MUST equal the dict key written in `compute_running_stats`
(e.g. `"adv_success_off"`). `group="season_to_date"`, `source_kind="computed_running"`.

**D-04 note (mostly already wired):** `team_talent`, `recruiting_rank`, `recruiting_points`,
`returning_ppa`, `returning_usage` already exist (`features.py:79-133`) as `raw_team_season` rows
with `source_file=`. Any *optional* new preseason rating reuses `_index_team_season_file` +
`_lookup_team_scoped`'s `raw_team_season` branch with a new `source_file` — no new mechanism.

**D-06 quarantine pattern:** if any full-season aggregate is wired at all, tag `group="result_lookahead"`
exactly like the `havoc_*`/`attendance` rows (`features.py:153-173`).

**registry_version contract (D-07):** `registry_version()` (`features.py:183-185`) hashes sorted
keys → adding rows changes the 12-char hash → web stale-sidecar warning until `enrich` rebuild.

---

### `tests/test_running_stats.py` (test) — no-lookahead per new field

**Analog:** `test_running_ppa_is_average_of_prior_games_only` (`:99-118`) — the `9.99` leak sentinel.
Copy it per new adv field. The construct-and-assert convention:
```python
    ppa = {
        (1, "Alpha"): (0.40, -0.10),
        (2, "Alpha"): (0.60, -0.30),
        (3, "Alpha"): (9.99, 9.99),  # current game's value must NEVER leak into its own entering stats
    }
    stats = compute_running_stats(games, ppa=ppa)
    assert stats[(1, "Alpha")]["ppa_off"] is None      # first game: None
    assert stats[(2, "Alpha")]["ppa_off"] == 0.40      # only prior game
    assert stats[(3, "Alpha")]["ppa_off"] == 0.50      # avg of priors, 9.99 excluded
```
Also replicate for new fields: `test_first_game_of_season_has_zero_history` (`:22-26`),
`test_seasons_reset` (`:78-84`), `test_start_dates_override_week_order` (`:87-96`). The `_game`
helper (`:5-19`) constructs `GameRecord`s directly — extend the assertion dicts at `:25-26`/`:84` to
include the new field keys (they currently assert the exact dict, so new keys will break them —
update those literal dicts).

---

## Shared Patterns

### No-lookahead: write-before-accumulate (the single biggest correctness risk this phase)
**Source:** `running_stats.py:31-67`
**Apply to:** every D-03 field, D-05 (prior-season only).
The entering-stats write (`:34`) MUST precede folding the current game's values (`:59-67`). The
`9.99` sentinel test proves it. Warning sign (Pitfall 1): a feature identical across all a team's
games in a season = it's a season aggregate (lookahead), not entering-game.

### None-safe untrusted-JSON access (ASVS V5)
**Source:** `normalize._first` (`normalize.py:64-68`), `enrich._field_value` (`enrich.py:263-268`),
`features.get_nested` (`features.py:188-194`).
**Apply to:** all new enrich index building. Treat every CFBD field as optional; `.get(...) or {}`
before nested access; never assume casing (`gameId` vs `game_id` — copy the dual-spelling guard at
`enrich.py:126`). Empty/2-byte files (`talent_2012-14`, `adjusted_player_*_2012`) yield null features
that fail closed (`feature_ok` returns False on None, `features.py:263-264`) — expected, not an error.

### Season backfill (DATA-01) — reuse `fetch`, not `scrapers.py`
**Source:** `cfbd_client.fetch_games_and_lines` (`:9-31`, loops `for season in seasons`), driven by
`cli._fetch` (`:56-62`) with `--season nargs="+"`. `_build` (`:65-73`) consumes `games_{season}.json`
+ `lines_{season}.json`. `scrapers.py` writes files `build` ignores — do NOT use it for backfill.
**Live probe prerequisite:** vendored `cfbd-python/` clone is EMPTY — must `git clone` before any
network call; `_load_cfbd_module` (`cfbd_client.py:51-58`) path-injects it. Token via
`find_cfbd_token` (`:34-48`); never log/commit `env.env`.
**Line-floor gate (D-02):** `normalize._select_line` (`normalize.py:46-56`) drops games whose `lines`
have no usable spread/total → line-less 2012 contributes 0 rows. Add a `test_normalize.py` case
asserting an empty-`lines` game yields 0 `GameRecord`s.

## Source → Feature file map (which raw file each feature reads)

| Feature work | Reads on disk | Index/lookup |
|--------------|--------------|--------------|
| D-03 to-date advanced (success/explosiveness/EPA splits) | `data/raw/advanced_game_stats_{season}.json` (2012–2025, ~4MB/yr, keys `gameId`+`team`) | NEW `adv` index in `_build_running_index`; existing `computed_running` `_lookup` |
| D-04 talent (already wired) | `data/raw/talent_{season}.json` (2012–14 EMPTY 2B) | `_index_team_season_file` + `raw_team_season` |
| D-04 recruiting (already wired) | `data/raw/recruiting_teams_{season}.json` | `_index_team_season_file` + `raw_team_season` |
| D-04 returning (already wired) | `data/raw/returning_production_{season}.json` | `_index_team_season_file` + `raw_team_season` |
| D-05 player agg (if built, PRIOR season) | `data/raw/adjusted_player_{passing,rushing}_{season}.json` (season-total per player: `athleteId, team, plays, wepa, year`; 2012 EMPTY) | NEW index aggregating prior-season → `(team, season)` |
| D-03 anti-source (DO NOT USE pregame) | `data/raw/adjusted_team_season_*`, `sp_*` (season-level, 1 row/team-yr) | lookahead — `result_lookahead` only |

## No Analog Found

None. Every construct has an existing representative instance.

The DATA-01 **live probe script** has no in-repo analog as a standalone script, but its network call
pattern is `fetch_games_and_lines` (`cfbd_client.py:9-31`) — copy its `Configuration`/`ApiClient`/
`BettingApi.get_lines` usage. It is a throwaway verification script, not a pipeline module.

## Metadata

**Analog search scope:** `cfb_system_maker/` (running_stats, enrich, features, cfbd_client, cli,
normalize), `tests/`, `data/raw/` (source-file inventory + structure probe).
**Files scanned:** 6 source modules read in full, 3 test files, on-disk JSON structure verified for
`advanced_game_stats_2015.json`.
**Pattern extraction date:** 2026-07-17

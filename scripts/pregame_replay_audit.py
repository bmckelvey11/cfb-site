"""Replay one historical week pre-kickoff and write a manifest someone else can re-run.

Decision mode is pre_kickoff, per game: game G is decided at its own kickoff
(`startDate` in `raw/games_<season>.json`; `games.csv` has no kickoff column), and
the only other rows it may see are games whose kickoff is strictly earlier.
Same-week games that have not kicked off -- including ones tied at G's kickoff --
are future data. `snapshot()` is that rule; `tests/test_pregame_replay.py` pins it.

Market number: one provider's `overUnderOpen` from `raw/lines_<season>.json`,
labeled `vendor_open_label`. No fallback to another provider, no close, no
imputation. The manifest records whether any line field carries a capture time.

Two descriptive forecasts of the game's points total, scored by MAE with a
game-level percentile bootstrap: the vendor open label, and the mean points
total of every games.csv game that kicked off before the week's first kickoff.
Neither is a bet; the run grades no wagers.

Usage:
    python -m scripts.pregame_replay_audit --season 2024 --week 6

See docs/pregame-replay-2026-09-22.md.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import re
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
import pandas as pd

BOOTSTRAP_SEED = 20240606
BOOTSTRAP_RESAMPLES = 10_000
DEFAULT_PROVIDER = "ESPN Bet"
_TIME_LIKE = re.compile(r"(?i:time|date|updated|captured|_at$)|At$")


def snapshot(pool: pd.DataFrame, decision_time: pd.Timestamp) -> pd.DataFrame:
    """Rows visible at `decision_time`: kickoff strictly earlier. NaT never passes."""
    return pool[pool["kickoff"] < decision_time]


def _sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def _read_json(path: Path, sources: list[Path]):
    sources.append(path)
    return json.loads(path.read_text(encoding="utf-8"))


def load_pool(root: Path, season: int, sources: list[Path]) -> pd.DataFrame:
    """games.csv through `season`, with kickoff from raw games JSON.

    `total` in games.csv is a closing line, so it becomes `close_total`; the
    forecast target is `points_total`. A later season's file cannot hold an
    earlier kickoff, so seasons after `season` are not read.
    """
    path = root / "processed" / "games.csv"
    sources.append(path)
    games = pd.read_csv(path)
    games = games[games["season"] <= season].rename(columns={"total": "close_total"})

    kick = []
    for s in sorted(games["season"].unique()):
        raw = root / "raw" / f"games_{s}.json"
        if not raw.exists():
            continue
        for r in _read_json(raw, sources):
            kick.append({
                "game_id": r.get("id"),
                "kickoff": r.get("startDate") or r.get("start_date"),
                "kickoff_tbd": bool(r.get("startTimeTBD")),
            })
    kick = pd.DataFrame(kick).drop_duplicates("game_id")
    kick["kickoff"] = pd.to_datetime(kick["kickoff"], errors="coerce", utc=True)

    pool = games.merge(kick, on="game_id", how="left")
    pool["points_total"] = pool["home_points"] + pool["away_points"]
    return pool


def load_vendor_open(root: Path, season: int, provider: str, game_ids,
                     sources: list[Path]) -> tuple[pd.Series, dict, list[str]]:
    """One provider's `overUnderOpen` per game. First row per game wins, as in core.

    Also returns per-provider open counts on these games and every line-dict key
    seen, which is the evidence for the line clock.
    """
    ids = set(game_ids)
    opens: dict[int, float | None] = {}
    by_provider: dict[str, int] = {}
    keys: set[str] = set()
    for g in _read_json(root / "raw" / f"lines_{season}.json", sources):
        if g.get("id") not in ids:
            continue
        for ln in g.get("lines") or []:
            keys.update(ln)
            p = ln.get("provider")
            if ln.get("overUnderOpen") is not None:
                by_provider[p] = by_provider.get(p, 0) + 1
            if p == provider and g["id"] not in opens:
                opens[g["id"]] = ln.get("overUnderOpen")
    return pd.Series(opens, dtype="float64"), by_provider, sorted(keys)


def probe_warehouse(db_path: Path, window: tuple[pd.Timestamp, pd.Timestamp]) -> dict:
    """Read-only look for a per-quote clock. Evidence only; never feeds the replay."""
    out: dict = {"path": str(db_path)}
    try:
        import duckdb

        con = duckdb.connect(str(db_path), read_only=True)
        try:
            def cols(schema: str, table: str) -> list[str]:
                return [r[0] for r in con.execute(
                    "SELECT column_name FROM information_schema.columns"
                    " WHERE table_schema = ? AND table_name = ? ORDER BY ordinal_position",
                    [schema, table]).fetchall()]

            out["core.fact_game_line"] = {"columns": cols("core", "fact_game_line")}
            tick = out["stg.an_history_tick"] = {"columns": cols("stg", "an_history_tick")}
            if "updated_at" in tick["columns"]:
                lo, hi, n, n_window = con.execute(
                    "SELECT min(updated_at), max(updated_at), count(*),"
                    " count(*) FILTER (WHERE updated_at BETWEEN ? AND ?)"
                    " FROM stg.an_history_tick",
                    [window[0].to_pydatetime(), window[1].to_pydatetime()]).fetchone()
                tick["updated_at"] = {
                    "min": str(lo), "max": str(hi), "rows": n,
                    "rows_in_replay_window": n_window,
                    "replay_window": [str(window[0]), str(window[1])],
                }
        finally:
            con.close()
    except Exception as exc:  # locked by a writer, or absent: record, don't guess
        out["error"] = f"{type(exc).__name__}: {exc}"
    return out


def mae_interval(forecast: pd.Series, actual: pd.Series, seed: int) -> dict:
    """MAE with a game-level percentile bootstrap 95% interval (one row per game)."""
    err = (forecast - actual).abs().dropna().to_numpy()
    if len(err) == 0:
        return {"n": 0, "mae": None, "ci95": None}
    rng = np.random.default_rng(seed)
    boots = rng.choice(err, size=(BOOTSTRAP_RESAMPLES, len(err))).mean(axis=1)
    lo, hi = np.percentile(boots, [2.5, 97.5])
    return {"n": int(len(err)), "mae": round(float(err.mean()), 3),
            "ci95": [round(float(lo), 3), round(float(hi), 3)]}


def line_clock(line_keys: list[str], warehouse: dict) -> tuple[str, dict]:
    time_like = [k for k in line_keys if _TIME_LIKE.search(k)]
    tick = warehouse.get("stg.an_history_tick", {}).get("updated_at")
    # ponytail: a time-like key is flagged for review, never auto-promoted to the
    # open's clock -- an `updatedAt` would date the close, not the open.
    evidence = {
        "value_column": "overUnderOpen (raw/lines_<season>.json, per provider line dict)",
        "line_dict_keys_inspected": line_keys,
        "time_like_line_keys": time_like,
        "not_a_quote_clock": "raw lines/games `startDate` is the game's kickoff, not "
                             "when any line was captured",
        "warehouse_probe": warehouse,
        "why": (
            "No key on a CFBD line dict carries a time, so overUnderOpen is a vendor "
            "label for the earliest number that book showed, captured at an unknown "
            "time. The label 'open' is not a timestamp."
            if not time_like else
            f"Time-like line keys {time_like} need review before any is treated as "
            "the capture time of overUnderOpen; until then it stays a label."
        ),
    }
    if tick:
        evidence["other_clock"] = (
            f"stg.an_history_tick.updated_at is a real per-quote clock (Action Network, "
            f"{tick['min']} to {tick['max']}, {tick['rows_in_replay_window']} rows in "
            f"this replay's window). It is a different source and is not a clock for "
            f"overUnderOpen or core.fact_game_line.total_open."
        )
    return "vendor_open_label_only", evidence


def replay(root: Path, season: int, week: int, provider: str, db_path: Path | None) -> dict:
    sources: list[Path] = []
    pool = load_pool(root, season, sources)
    wk = pool[(pool["season"] == season) & (pool["week"] == week)
              & (pool["season_type"] == "regular")].copy()

    manifest: dict = {
        "season": season, "week": week, "decision_mode": "pre_kickoff",
        "command": f'python -m scripts.pregame_replay_audit --season {season} '
                   f'--week {week} --provider "{provider}"',
        "code_sha256": _sha256(Path(__file__)),
        "generated_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "data_root": str(root),
        "n_games": int(len(wk)),
    }
    if wk.empty:
        manifest["blocker"] = f"season {season} week {week} is absent from games.csv"
        manifest["source_files"] = _hashes(sources)
        return manifest

    opens, by_provider, line_keys = load_vendor_open(root, season, provider,
                                                     wk["game_id"], sources)
    wk["vendor_open_label"] = wk["game_id"].map(opens)

    no_kick = wk[wk["kickoff"].isna()]
    decided = wk.dropna(subset=["kickoff"]).sort_values(["kickoff", "game_id"])
    first_kick = decided["kickoff"].min()

    per_game = []
    for g in decided.itertuples():
        seen = snapshot(pool, g.kickoff)
        later_same_week = int(((decided["kickoff"] >= g.kickoff)
                               & (decided["game_id"] != g.game_id)).sum())
        per_game.append({
            "game_id": int(g.game_id), "kickoff": g.kickoff.isoformat(),
            "home": g.home_team, "away": g.away_team,
            "n_visible_rows": int(len(seen)),
            "n_excluded_same_week": later_same_week,
            "vendor_open_label": None if pd.isna(g.vendor_open_label) else g.vendor_open_label,
            "points_total": None if pd.isna(g.points_total) else int(g.points_total),
        })

    train = snapshot(pool, first_kick).dropna(subset=["points_total"])
    train_mean = float(train["points_total"].mean())
    has_open = decided["vendor_open_label"].notna()
    actual = decided["points_total"]
    as_mean = pd.Series(train_mean, index=decided.index)

    window = (first_kick - pd.Timedelta(days=7), decided["kickoff"].max())
    warehouse = probe_warehouse(db_path, window) if db_path else {"skipped": True}
    clock, evidence = line_clock(line_keys, warehouse)

    manifest.update({
        "market_provider": provider,
        "market_provider_rule": (
            "one fixed provider, no fallback to another book; chosen on coverage "
            "(opens_by_provider_this_week), not on scores. models/middle ranks Bovada "
            "first and falls back across books, which is a different rule."),
        "opens_by_provider_this_week": by_provider,
        "n_with_vendor_open": int(has_open.sum()),
        "n_missing_vendor_open": int((~has_open).sum()),
        "n_no_kickoff": int(len(no_kick)),
        "n_kickoff_time_tbd": int(decided["kickoff_tbd"].sum()),
        "n_excluded_future": int(sum(p["n_excluded_same_week"] for p in per_game)),
        "n_excluded_future_definition": (
            "summed over this week's decisions: same-week games whose kickoff is not "
            "strictly before game G's kickoff, G itself not counted. Games tied at G's "
            "kickoff count, which is most of the total on a Saturday slate."),
        "line_clock": clock,
        "line_clock_evidence": evidence,
        "baselines": {
            "target": "points_total = home_points + away_points",
            "interval": f"percentile bootstrap over games, {BOOTSTRAP_RESAMPLES} "
                        f"resamples, seed {BOOTSTRAP_SEED}",
            "market_number": mae_interval(decided["vendor_open_label"], actual,
                                          BOOTSTRAP_SEED),
            "train_mean": {
                "value": round(train_mean, 3),
                "fit_on": {
                    "n": int(len(train)),
                    "kickoff_min": train["kickoff"].min().isoformat(),
                    "kickoff_max": train["kickoff"].max().isoformat(),
                    "seasons": sorted(int(s) for s in train["season"].unique()),
                    "rule": "every games.csv game with kickoff strictly before this "
                            "week's first kickoff",
                },
                "all_games": mae_interval(as_mean, actual, BOOTSTRAP_SEED),
                "same_games_as_market_number": mae_interval(
                    as_mean[has_open], actual[has_open], BOOTSTRAP_SEED),
            },
        },
        "not_reconstructible": _not_reconstructible(season, provider, no_kick),
        "per_game": per_game,
    })
    manifest["source_files"] = _hashes(sources)
    if db_path:
        st = db_path.stat() if db_path.exists() else None
        manifest["source_files"].append({
            "path": str(db_path), "sha256": None,
            "note": "probed read-only for line_clock_evidence only; not hashed (multi-GB "
                    "live warehouse)",
            "bytes": st.st_size if st else None,
            "mtime": datetime.fromtimestamp(st.st_mtime, timezone.utc).isoformat(
                timespec="seconds") if st else None,
        })
    return manifest


def _not_reconstructible(season: int, provider: str, no_kick: pd.DataFrame) -> list[dict]:
    out = [
        {"market": f"full-game total as a price ({provider} overUnderOpen)",
         "seasons": [season],
         "reason": "no capture time on the quote and no over/under odds in CFBD lines; "
                   "the number is scored only as a forecast, no wager is graded"},
        {"market": "full-game total close (overUnder / games.csv total)",
         "seasons": [season],
         "reason": "no capture time either; not substituted for the open"},
        {"market": "spread and moneyline (spreadOpen, spread, homeMoneyline, awayMoneyline)",
         "seasons": [season],
         "reason": "same CFBD line dicts, same missing clock; outside this slice"},
    ]
    if len(no_kick):
        out.append({"market": "games without a kickoff timestamp",
                    "game_ids": [int(x) for x in no_kick["game_id"]],
                    "reason": "decision time cannot be named; dropped, not guessed"})
    return out


def _hashes(sources: list[Path]) -> list[dict]:
    return [{"path": str(p), "sha256": _sha256(p)} for p in dict.fromkeys(sources)]


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--season", type=int, required=True)
    ap.add_argument("--week", type=int, required=True)
    ap.add_argument("--provider", default=DEFAULT_PROVIDER)
    ap.add_argument("--no-warehouse", action="store_true",
                    help="skip the read-only cfb.duckdb clock probe")
    args = ap.parse_args(argv)

    # Imported here so the module (and its test) loads without CFB_DATA_ROOT.
    from cfb_paths import DATA_ROOT, DB_PATH, PROCESSED

    manifest = replay(DATA_ROOT, args.season, args.week, args.provider,
                      None if args.no_warehouse else DB_PATH)
    out = PROCESSED / "pregame_replay" / f"replay_{args.season}_w{args.week:02d}.json"
    out.parent.mkdir(parents=True, exist_ok=True)
    text = json.dumps(manifest, indent=2, default=str)
    out.write_text(text + "\n", encoding="utf-8")
    print(text)
    print(f"\nmanifest: {out}")
    return 1 if "blocker" in manifest else 0


if __name__ == "__main__":
    raise SystemExit(main())

"""Load CFBD data from this repo's data/ folder and build entering-game features.

Reads three things from the hub data directory (default: repo_root/data):
  data/processed/games.csv   - game index, scores, closing total/spread
  data/raw/lines_*.json      - per-provider lines incl. `overUnderOpen`
  data/raw/advanced_game_stats_*.json - per-team-game pace/efficiency

Every team stat is an *entering-game* value: an expanding mean over that team's
strictly-prior games in the same season. Never fold a game's own box score into
its own features.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path

import numpy as np
import pandas as pd

from cfb_paths import DATA_ROOT

DEFAULT_DATA_ROOT = DATA_ROOT

# Per-team-game stats rolled forward into entering-game means.
_ROLL_COLS = (
    "o_plays", "o_drives", "o_ppa", "o_succ", "o_expl", "o_ppo",
    "d_plays", "d_drives", "d_ppa", "d_succ", "d_expl", "d_ppo",
)

# Registry features pulled from features.json. Entering-game only — no this-game
# havoc, reported attendance, or team-scoped post-game winProb.
_REGISTRY_COLS = (
    "home_running_ppa_off", "home_running_ppa_def",
    "away_running_ppa_off", "away_running_ppa_def",
    "home_running_success_off", "home_running_success_def",
    "away_running_success_off", "away_running_success_def",
    "home_running_explosiveness_off", "away_running_explosiveness_off",
    "home_running_explosiveness_def", "away_running_explosiveness_def",
    "home_team_talent", "away_team_talent",
    "homePregameElo", "awayPregameElo",
    "home_returning_ppa", "away_returning_ppa",
    "home_recruiting_points", "away_recruiting_points",
    "venue_elevation",
)

_WEATHER = {
    "temp": "weather_temperature",
    "wind": "weather_windSpeed",
    "precip": "weather_precipitation",
    "humid": "weather_humidity",
    "elev": "venue_elevation",
}

# Opening lines exist only for these books, best-first.
_OPEN_PROVIDERS = ("Bovada", "ESPN Bet", "DraftKings")


@dataclass(frozen=True)
class Dataset:
    frame: pd.DataFrame
    feature_cols: list[str]


def _read_games(root: Path) -> pd.DataFrame:
    g = pd.read_csv(root / "processed" / "games.csv")
    return g.dropna(subset=["total"]).copy()


def _read_game_dates(root: Path) -> pd.DataFrame:
    """Kickoff timestamps, needed to order a team's games within a season."""
    rows = []
    for path in sorted((root / "raw").glob("games_*.json")):
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
        except (ValueError, OSError):
            continue
        for r in payload:
            rows.append({
                "game_id": r.get("id"),
                "start": r.get("startDate") or r.get("start_date"),
                "home": r.get("homeTeam") or r.get("home_team"),
                "away": r.get("awayTeam") or r.get("away_team"),
            })
    df = pd.DataFrame(rows).drop_duplicates("game_id")
    df["dt"] = pd.to_datetime(df["start"], errors="coerce", utc=True)
    return df.dropna(subset=["dt"])


def _read_team_games(root: Path) -> pd.DataFrame:
    rows = []
    for path in sorted((root / "raw").glob("advanced_game_stats_*.json")):
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
        except (ValueError, OSError):
            continue
        for r in payload:
            off = r.get("offense") or {}
            dfn = r.get("defense") or {}
            rows.append({
                "game_id": r.get("gameId"), "team": r.get("team"), "season": r.get("season"),
                "o_plays": off.get("plays"), "o_drives": off.get("drives"),
                "o_ppa": off.get("ppa"), "o_succ": off.get("successRate"),
                "o_expl": off.get("explosiveness"), "o_ppo": off.get("pointsPerOpportunity"),
                "d_plays": dfn.get("plays"), "d_drives": dfn.get("drives"),
                "d_ppa": dfn.get("ppa"), "d_succ": dfn.get("successRate"),
                "d_expl": dfn.get("explosiveness"), "d_ppo": dfn.get("pointsPerOpportunity"),
            })
    return pd.DataFrame(rows).dropna(subset=["game_id", "team"])


def _read_lines(root: Path) -> pd.DataFrame:
    """One row per (game, provider) with opening and closing totals."""
    rows = []
    for path in sorted((root / "raw").glob("lines_*.json")):
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
        except (ValueError, OSError):
            continue
        for g in payload:
            for ln in (g.get("lines") or []):
                rows.append({
                    "game_id": g["id"], "provider": ln.get("provider"),
                    "ou_close": ln.get("overUnder"), "ou_open": ln.get("overUnderOpen"),
                })
    return pd.DataFrame(rows)


def _entering_game_stats(team_games: pd.DataFrame, dates: pd.DataFrame) -> pd.DataFrame:
    """Expanding mean shifted one game — the no-lookahead guarantee lives here."""
    df = team_games.merge(dates[["game_id", "dt"]], on="game_id", how="left")
    df = df.dropna(subset=["dt"]).sort_values(["team", "season", "dt"])
    for col in _ROLL_COLS:
        df["pre_" + col] = (
            df.groupby(["team", "season"])[col]
            .transform(lambda s: s.shift(1).expanding().mean())
        )
    df["pre_n"] = df.groupby(["team", "season"]).cumcount()
    return df


def _registry_features(root: Path, game_ids) -> pd.DataFrame:
    path = root / "processed" / "features.json"
    if not path.exists():
        return pd.DataFrame({"game_id": list(game_ids)})
    blob = json.loads(path.read_text(encoding="utf-8"))
    games = blob.get("games", blob)
    rows = []
    for gid in game_ids:
        f = games.get(str(gid)) or {}
        row = {"game_id": gid}
        row.update({k: f.get(k) for k in _REGISTRY_COLS})
        row.update({short: f.get(key) for short, key in _WEATHER.items()})
        row["dome"] = f.get("venue_dome")
        rows.append(row)
    return pd.DataFrame(rows)


def load(data_root: Path | str | None = None, *, min_prior_games: int = 3) -> Dataset:
    """Build the modelling frame. Returns games with both teams >= min_prior_games."""
    root = Path(data_root) if data_root else DEFAULT_DATA_ROOT
    if not (root / "processed" / "games.csv").exists():
        raise FileNotFoundError(
            f"No games.csv under {root}. Point --data-root at CFB_DATA_ROOT."
        )

    games = _read_games(root)
    dates = _read_game_dates(root)
    pre = _entering_game_stats(_read_team_games(root), dates)

    pre_cols = [c for c in pre.columns if c.startswith("pre_")]
    home = pre[["game_id", "team"] + pre_cols].add_prefix("h_").rename(
        columns={"h_game_id": "game_id", "h_team": "home"})
    away = pre[["game_id", "team"] + pre_cols].add_prefix("a_").rename(
        columns={"a_game_id": "game_id", "a_team": "away"})

    df = (games.merge(dates[["game_id", "home", "away"]], on="game_id", how="left")
                .merge(home, on=["game_id", "home"], how="left")
                .merge(away, on=["game_id", "away"], how="left"))

    df = df.merge(_registry_features(root, df["game_id"]), on="game_id", how="left")

    lines = _read_lines(root)
    rank = {p: i for i, p in enumerate(_OPEN_PROVIDERS)}
    lines["rank"] = lines["provider"].map(rank).fillna(99)
    opens = (lines.dropna(subset=["ou_open"]).sort_values("rank")
                  .drop_duplicates("game_id")[["game_id", "ou_open"]])
    df = df.merge(opens, on="game_id", how="left")

    df["pts"] = df["home_points"] + df["away_points"]

    # Derived features: pace is the sum of both offenses' tempo; mismatch pits
    # each offense against the defense it actually faces (averaging destroys this).
    df["pace_plays"] = df["h_pre_o_plays"] + df["a_pre_o_plays"]
    df["pace_drives"] = df["h_pre_o_drives"] + df["a_pre_o_drives"]
    df["mm_h_ppa"] = df["h_pre_o_ppa"] - df["a_pre_d_ppa"]
    df["mm_a_ppa"] = df["a_pre_o_ppa"] - df["h_pre_d_ppa"]
    df["mm_tot_ppa"] = df["mm_h_ppa"] + df["mm_a_ppa"]
    df["mm_h_succ"] = df["h_pre_o_succ"] - df["a_pre_d_succ"]
    df["mm_a_succ"] = df["a_pre_o_succ"] - df["h_pre_d_succ"]
    df["mm_tot_succ"] = df["mm_h_succ"] + df["mm_a_succ"]
    df["dome_i"] = df["dome"].map({True: 1, False: 0})

    df["min_n"] = df[["h_pre_n", "a_pre_n"]].min(axis=1)
    df = df[df["min_n"] >= min_prior_games].copy()

    feature_cols = [
        "pace_plays", "pace_drives",
        "mm_tot_ppa", "mm_tot_succ", "mm_h_ppa", "mm_a_ppa", "mm_h_succ", "mm_a_succ",
        "temp", "wind", "precip", "humid", "elev", "dome_i",
        *_REGISTRY_COLS,
    ]
    for col in feature_cols + ["ou_open", "total", "pts"]:
        df[col] = pd.to_numeric(df[col], errors="coerce")

    return Dataset(frame=df, feature_cols=feature_cols)

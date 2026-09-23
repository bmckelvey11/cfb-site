"""Versioned feature catalog, fixed feature sets, and the as-of loader (Release C, C2).

Every feature has an availability class (plan §27.5). A retrospective run may use only
`historical_replayable` features; the loader drops any other class, any feature the
catalog disagrees about, and any feature with a value known after its row's
`decision_ts`, and says why in the report.

Real features come from Release B's as-of ratings (`weekly_ratings_snapshots.csv`,
`ridge_v1` rows). Each snapshot's `as_of_ts` is checked against the week cutoff
recomputed from the raw games, so a CSV built from other data fails closed.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import NamedTuple

import numpy as np
import pandas as pd

from models.tuning.spec import AvailabilityClass, DatasetSpec, FeatureSetSpec

FEATURE_SETS = Path(__file__).with_name("feature_sets")
BASELINES = ("market_open", "past_mean", "ridge_v1_total")
ELIGIBLE = "historical_replayable"
REFUSED = {
    "snapshot_dependent": "snapshot_dependent: no snapshot-coverage check exists yet",
    "prospective_only": "prospective_only: shadow/live only, not reconstructible historically",
    "retrospective_descriptive": "retrospective_descriptive: known after kickoff, blocked from prediction",
    "provider_opaque": "provider_opaque: benchmark-only until its timing is audited",
}


class CatalogEntry(NamedTuple):
    version: int
    availability_class: AvailabilityClass
    description: str


CATALOG: dict[str, CatalogEntry] = {
    "rv1_off_home": CatalogEntry(1, "historical_replayable", "ridge_v1 offense O, home team, as of the week cutoff"),
    "rv1_def_home": CatalogEntry(1, "historical_replayable", "ridge_v1 defense D, home team, as of the week cutoff"),
    "rv1_pace_home": CatalogEntry(1, "historical_replayable", "ridge_v1 pace P, home team, as of the week cutoff"),
    "rv1_off_away": CatalogEntry(1, "historical_replayable", "ridge_v1 offense O, away team, as of the week cutoff"),
    "rv1_def_away": CatalogEntry(1, "historical_replayable", "ridge_v1 defense D, away team, as of the week cutoff"),
    "rv1_pace_away": CatalogEntry(1, "historical_replayable", "ridge_v1 pace P, away team, as of the week cutoff"),
    "rv1_total": CatalogEntry(1, "historical_replayable", "forecast_total from the ridge_v1 snapshot"),
    "min_prior_games": CatalogEntry(1, "historical_replayable", "fewer of the two teams' games in the snapshot"),
    "neutral": CatalogEntry(1, "historical_replayable", "neutral-site flag from the schedule, known before the cutoff"),
    "open_total": CatalogEntry(1, "provider_opaque", "Bovada overUnderOpen: no capture time, no price"),
}


@dataclass
class LoadReport:
    kept: list[str]
    dropped: dict[str, str]
    sources: list[Path] = field(default_factory=list)


def load_feature_set(path: str | Path) -> FeatureSetSpec:
    return FeatureSetSpec.model_validate_json(Path(path).read_text(encoding="utf-8"))


def screen_features(frame: pd.DataFrame, feature_set: FeatureSetSpec,
                    catalog: dict[str, CatalogEntry] = CATALOG) -> tuple[list[str], dict[str, str]]:
    """Declared features a retrospective run may use, and why each other one was dropped."""
    kept, dropped = [], {}
    for f in feature_set.features:
        entry = catalog.get(f.id)
        if entry is None:
            dropped[f.id] = "not in the catalog"
        elif (entry.version, entry.availability_class) != (f.version, f.availability_class):
            dropped[f.id] = (f"declared v{f.version} {f.availability_class}, catalog says "
                             f"v{entry.version} {entry.availability_class}")
        elif entry.availability_class != ELIGIBLE:
            dropped[f.id] = REFUSED[entry.availability_class]
        elif f.id not in frame or f"{f.id}__as_of" not in frame:
            dropped[f.id] = "not built by the loader"
        else:
            value, as_of = frame[f.id], frame[f"{f.id}__as_of"]
            late = value.notna() & (as_of.isna() | (as_of > frame["decision_ts"]))
            if late.any():
                dropped[f.id] = f"{int(late.sum())} rows known after decision_ts or with no as-of"
            else:
                kept.append(f.id)
    return kept, dropped


def load_frame(dataset: DatasetSpec, feature_set: FeatureSetSpec,
               data_root: Path | None = None) -> tuple[pd.DataFrame, LoadReport]:
    """One row per game: keys, decision_ts, target, the kept features, baselines."""
    if dataset.source == "synthetic_v1":
        frame, sources = synthetic_frame(dataset, feature_set), []
    else:
        if data_root is None:
            from cfb_paths import DATA_ROOT as data_root
        frame, sources = _release_b_frame(dataset, Path(data_root))
    kept, dropped = screen_features(frame, feature_set)
    declared = [f.id for f in feature_set.features]
    gone = [c for f in declared if f not in kept for c in (f, f"{f}__as_of") if c in frame]
    return frame.drop(columns=gone), LoadReport(kept, dropped, sources)


def source_paths(dataset: DatasetSpec, root: Path) -> list[Path]:
    """Every file `load_frame` reads for a Release B dataset, so a worker can hash them first."""
    if dataset.source != "cfb_release_b":
        return []
    span = range(min(dataset.seasons), max(dataset.seasons) + 1)
    return ([p for s in span for p in (root / "raw" / f"games_{s}.json",
                                       root / "raw" / f"drives_{s}.json")]
            + [root / "raw" / f"lines_{s}.json" for s in dataset.seasons]
            + [root / "processed" / "ratings" / "weekly_ratings_snapshots.csv"])


def _release_b_frame(dataset: DatasetSpec, root: Path) -> tuple[pd.DataFrame, list[Path]]:
    from scripts.pregame_replay_audit import snapshot
    from scripts.weekly_ratings import Ratings
    from scripts.weekly_ratings_eval import load, load_opens, week_cutoffs

    sources: list[Path] = []
    # Every season in the span is loaded so past_mean matches Release B's train mean
    # (2020 counts toward the mean even though it is never a fold season).
    games, _ = load(root, list(range(min(dataset.seasons), max(dataset.seasons) + 1)), sources)
    opens = load_opens(root, list(dataset.seasons), sources)
    snap_path = root / "processed" / "ratings" / "weekly_ratings_snapshots.csv"
    sources.append(snap_path)
    snaps = pd.read_csv(snap_path)
    snaps = snaps[(snaps["method"] == "ridge_v1") & snaps["season"].isin(dataset.seasons)]

    rows = []
    for (season, week), grp in snaps.groupby(["season", "as_of_week"], sort=True):
        sg = games[games["season"] == season]
        cut = week_cutoffs(sg).get(week)
        as_of = pd.Timestamp(grp["as_of_ts"].iloc[0])
        if cut is None or as_of != cut:
            raise ValueError(f"snapshot {season} week {week} is as of {as_of}, but the raw "
                             f"games put that week's cutoff at {cut}: rebuild the snapshots")
        s = grp.iloc[0]
        table = grp.set_index("team")[["O", "D", "P", "n_games"]]
        r = Ratings(mu=s.mu, nu=s.nu, h=s.h, c=s.c, table=table, unrated=0.0)
        past_mean = float(snapshot(games, cut)["total"].mean())
        for g in sg[sg["week"] == week].itertuples():
            rows.append(game_row(g, int(season), int(week), r, cut, past_mean,
                                 opens.get(g.game_id), outcome=g))
    return _finish(rows), sources


def game_row(g, season: int, week: int, r, cut: pd.Timestamp, past_mean: float,
             open_total: float | None, outcome=None) -> dict:
    """One game's row from one ratings snapshot. The snapshot-CSV path and the live
    fit-at-cutoff path both call this, so a live prediction sees the same features the
    model was tuned and calibrated on (plan §29.2). `outcome` carries total, home_reg,
    away_reg, ot for a played game; an unplayed game gets NaN targets."""
    from scripts.weekly_ratings import forecast_total

    def get(team: str, col: str) -> float:
        return float(r.table.at[team, col]) if team in r.table.index else r.unrated

    total_hat = forecast_total(r, g.home, g.away, g.neutral)
    nan = float("nan")
    return {
        "game_id": int(g.game_id), "season": season, "week": week,
        "kickoff": g.kickoff, "decision_ts": cut,
        "target": float(outcome.total) if outcome is not None else nan,
        # Target parts, never features: target = home_reg + away_reg + ot_points.
        "home_reg": float(outcome.home_reg) if outcome is not None else nan,
        "away_reg": float(outcome.away_reg) if outcome is not None else nan,
        "ot_points": float(outcome.ot) if outcome is not None else nan,
        "rv1_off_home": get(g.home, "O"), "rv1_def_home": get(g.home, "D"),
        "rv1_pace_home": get(g.home, "P"), "rv1_off_away": get(g.away, "O"),
        "rv1_def_away": get(g.away, "D"), "rv1_pace_away": get(g.away, "P"),
        "rv1_total": total_hat,
        "min_prior_games": min(get(g.home, "n_games"), get(g.away, "n_games")),
        "neutral": float(g.neutral),
        "open_total": open_total,
        "market_open": open_total, "past_mean": past_mean,
        "ridge_v1_total": total_hat,
    }


def _finish(rows: list[dict]) -> pd.DataFrame:
    frame = pd.DataFrame(rows)
    for fid in CATALOG:
        # Snapshot-derived and schedule features are known at the cutoff; the open has no
        # capture time at all, so its as-of is unknown.
        frame[f"{fid}__as_of"] = pd.NaT if fid == "open_total" else frame["decision_ts"]
    frame["open_total__as_of"] = pd.to_datetime(frame["open_total__as_of"], utc=True)
    return frame.sort_values(["decision_ts", "game_id"], kind="stable").reset_index(drop=True)


def fit_digest(fit_games: pd.DataFrame) -> str:
    """sha256 of the as-of evidence a snapshot was fit on: which games, their regulation
    points, and their possessions. Rebuilt at scoring time to detect a data revision."""
    import hashlib

    cols = ["game_id", "home_reg", "away_reg", "home_poss", "away_poss"]
    rows = fit_games[cols].sort_values("game_id").astype("int64").to_csv(index=False,
                                                                         lineterminator="\n")
    return hashlib.sha256(rows.encode("utf-8")).hexdigest()


def live_week_frame(season: int, week: int, root: Path, first_season: int = 2014,
                    lam: tuple[float, float] = (40, 8)) -> tuple[pd.DataFrame, dict]:
    """The week's scheduled FBS-vs-FBS games, featured from ridge_v1 fit at the week's
    cutoff (its earliest scheduled kickoff) on the season's games before it. Works for a
    week not yet played; targets are filled for games already completed."""
    import json

    from scripts.pregame_replay_audit import snapshot
    from scripts.weekly_forecast import week_schedule
    from scripts.weekly_ratings import fit_ridge, fit_set
    from scripts.weekly_ratings_eval import load, load_opens

    payload = json.loads((root / "raw" / f"games_{season}.json").read_text(encoding="utf-8"))
    sched = week_schedule(payload, week)
    if sched.empty:
        return pd.DataFrame(), {}
    cut = sched["kickoff"].min()
    games, _ = load(root, list(range(first_season, season + 1)), [])
    fs = fit_set(games[games["season"] == season], cut)
    r = fit_ridge(fs, *lam)
    past_mean = float(snapshot(games, cut)["total"].mean())
    opens = load_opens(root, [season], [])
    played = games[games["season"] == season].set_index("game_id")
    rows = [game_row(g, season, week, r, cut, past_mean, opens.get(g.game_id),
                     outcome=played.loc[g.game_id] if g.game_id in played.index else None)
            for g in sched.itertuples()]
    meta = {"cutoff": cut.isoformat(), "n_fit": int(len(fs)), "fit_digest": fit_digest(fs),
            "mu": r.mu, "nu": r.nu, "h": r.h, "c": r.c, "scheduled": int(len(sched))}
    return _finish(rows), meta


def synthetic_frame(dataset: DatasetSpec, feature_set: FeatureSetSpec) -> pd.DataFrame:
    """Deterministic stand-in with the real frame's columns, for tests without data."""
    rng = np.random.default_rng(dataset.synthetic_seed)
    ids = [f.id for f in feature_set.features]
    beta = rng.normal(0.0, 3.0, size=len(ids))
    rows = []
    for season in dataset.seasons:
        start = pd.Timestamp(f"{season}-09-01T16:00:00Z")
        for week in range(2, 14):
            for i in range(20):
                kickoff = start + pd.Timedelta(days=7 * (week - 2), hours=i)
                rows.append({"game_id": season * 10_000 + week * 100 + i, "season": season,
                             "week": week, "kickoff": kickoff,
                             "decision_ts": start + pd.Timedelta(days=7 * (week - 2))})
    frame = pd.DataFrame(rows)
    x = rng.normal(0.0, 1.0, size=(len(frame), len(ids)))
    signal = 55.0 + x @ beta
    frame["target"] = signal + rng.normal(0.0, 12.0, len(frame))
    # Integer parts derived from the target, with no extra draws (the stream is unchanged).
    whole = np.clip(np.round(frame["target"]), 0, None)
    frame["home_reg"] = np.round(whole * 0.52)
    frame["away_reg"] = whole - frame["home_reg"]
    frame["ot_points"] = 0.0
    for j, fid in enumerate(ids):
        frame[fid] = x[:, j]
    if ids:
        frame.loc[rng.random(len(frame)) < 0.02, ids[0]] = np.nan
    for fid in ids:
        frame[f"{fid}__as_of"] = frame["decision_ts"]
    frame["market_open"] = signal + rng.normal(0.0, 10.0, len(frame))
    frame["past_mean"] = 55.0 + rng.normal(0.0, 0.5, len(frame))
    frame["ridge_v1_total"] = signal + rng.normal(0.0, 11.0, len(frame))
    return frame

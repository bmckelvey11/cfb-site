"""Read-only data for the lab GUI (`models/tuning/ui/app.py`). Nothing here writes;
`actions.py` holds the few things that do.

Standard library and pandas only, so the GUI's own venv (`.venv-lab-ui`) needs no
optuna or sklearn, and the shadow tick's `.venv` never gets the GUI's packages.
Every database is opened read-only, so the GUI cannot block the tick or a worker.
"""
from __future__ import annotations

import hashlib
import json
import os
import sqlite3
import time
from pathlib import Path

import numpy as np
import pandas as pd

from models.tuning.ledger import read_only

ET = "America/New_York"
STALE_TICK_HOURS = 26      # the refresh runs daily at 05:00 ET
WARN_BEFORE_CUTOFF_DAYS = 7
HYPOTHESES = Path(__file__).resolve().parents[1] / "hypotheses.json"


def lab_root() -> Path:
    """`CFB_LAB_ROOT` overrides the lab root (a scratch lab for trying the GUI)."""
    if os.environ.get("CFB_LAB_ROOT"):
        return Path(os.environ["CFB_LAB_ROOT"])
    from cfb_paths import PROCESSED
    return PROCESSED / "tuning"


def _ro_query(path: Path, sql: str, params: tuple = ()) -> pd.DataFrame:
    """A read-only query that retries while a writer holds the lock."""
    for attempt in range(5):
        con = sqlite3.connect(f"file:{path.as_posix()}?mode=ro", uri=True, timeout=5)
        try:
            return pd.read_sql_query(sql, con, params=params)
        except (sqlite3.OperationalError, pd.errors.DatabaseError) as e:
            if "locked" not in str(e) or attempt == 4:
                raise
            time.sleep(0.5)
        finally:
            con.close()
    raise AssertionError("unreachable")


def _param(value: float, distribution_json: str):
    dist = json.loads(distribution_json)
    if dist.get("name") == "CategoricalDistribution":
        return dist["attributes"]["choices"][int(value)]
    return round(value, 6)


def trials(root: Path, run_id: str) -> pd.DataFrame:
    """One row per Optuna trial of a run: number, state, objective, parameters."""
    path = root / "optuna.sqlite3"
    if not path.exists():
        return pd.DataFrame()
    t = _ro_query(path, "SELECT t.trial_id, t.number, t.state, v.value, t.datetime_start, "
                        "t.datetime_complete FROM trials t JOIN studies s USING (study_id) "
                        "LEFT JOIN trial_values v ON v.trial_id = t.trial_id AND v.objective = 0 "
                        "WHERE s.study_name = ? ORDER BY t.number", (run_id,))
    if t.empty:
        return t
    p = _ro_query(path, "SELECT p.trial_id, p.param_name, p.param_value, p.distribution_json "
                        "FROM trial_params p JOIN trials t USING (trial_id) JOIN studies s "
                        "USING (study_id) WHERE s.study_name = ?", (run_id,))
    if not p.empty:
        p["v"] = [_param(v, d) for v, d in zip(p["param_value"], p["distribution_json"])]
        wide = p.pivot(index="trial_id", columns="param_name", values="v")
        t = t.join(wide, on="trial_id")
    return t.drop(columns="trial_id").rename(columns={"value": "objective"})


def log_tail(root: Path, run_id: str, lines: int = 40) -> str:
    path = root / "logs" / f"{run_id}.log"
    if not path.exists():
        return ""
    return "\n".join(path.read_text(encoding="utf-8", errors="replace").splitlines()[-lines:])


def _et(ts) -> str:
    return "" if ts is None or pd.isna(ts) else pd.Timestamp(ts).tz_convert(ET).strftime("%a %m/%d %I:%M %p ET")


def week_cutoffs(games_payload: list[dict]) -> pd.Series:
    """Earliest FBS-vs-FBS regular-season kickoff per week: each week's decision time."""
    kicks = [(g["week"], pd.to_datetime(g.get("startDate"), utc=True, errors="coerce"))
             for g in games_payload if g.get("seasonType") == "regular"
             and g.get("homeClassification") == "fbs" and g.get("awayClassification") == "fbs"]
    return pd.DataFrame(kicks, columns=["week", "kickoff"]).dropna().groupby("week")["kickoff"].min()


def shadow_view(sd: Path, raw_dir: Path, now: pd.Timestamp) -> dict:
    """Weeks, alerts, and verdict for one shadow period. Cutoffs come from the raw schedule
    of the season its first snapshot names (else the current year's)."""
    records, (chain_ok, chain_msg) = read_only(sd / "ledger.sqlite3")
    by = {}
    for r in records:
        by.setdefault(r.kind, []).append(r.payload)
    arm = (by.get("arm") or [{}])[0]
    period, rehearsal = arm.get("period_weeks", []), arm.get("rehearsal_weeks", [])
    season = pd.Timestamp(by["snapshot"][0]["cutoff"]).year if by.get("snapshot") else now.year
    games = raw_dir / f"games_{season}.json"
    cutoffs = (week_cutoffs(json.loads(games.read_text(encoding="utf-8"))) if games.exists()
               else pd.Series(dtype="datetime64[ns, UTC]"))
    status = sd / "status.md"
    last_tick = pd.Timestamp(status.stat().st_mtime, unit="s", tz="UTC") if status.exists() else None

    snaps = pd.DataFrame(by.get("snapshot", []))
    scores = pd.DataFrame(by.get("score", []))
    missed = {m["week"] for m in by.get("missed", [])}
    rows, alerts = [], []
    for w in sorted(set(period) | set(rehearsal)):
        cut = cutoffs.get(w)
        ws = snaps[snaps["week"] == w] if not snaps.empty else snaps
        before = ws[pd.to_datetime(ws["generated_at"]) < pd.to_datetime(ws["cutoff"])] if not ws.empty else ws
        sc = scores[scores["week"] == w] if not scores.empty else scores
        ch = sc[sc["alias"] == "challenger"] if not sc.empty else sc
        cm = sc[sc["alias"] == "champion"] if not sc.empty else sc
        rows.append({
            "week": w, "role": "rehearsal" if w in rehearsal else "period",
            "cutoff": _et(cut), "snapshots": len(ws),
            "last snapshot": _et(before["generated_at"].max()) if len(before) else "",
            "games": len(before.iloc[-1]["games"]) if len(before) else 0,
            "scored": len(ch),
            "champion MAE": round(cm["abs_error"].mean(), 2) if len(cm) else None,
            "challenger MAE": round(ch["abs_error"].mean(), 2) if len(ch) else None,
            "CRPS": round(ch["crps"].mean(), 2) if len(ch) and "crps" in ch else None,
            "80% cover": round(ch["cover_80"].mean(), 2) if len(ch) and "cover_80" in ch else None,
            "missed": w in missed})
        if w in period and not len(before) and cut is not None:
            due = (f"Week {w} needs a snapshot before {_et(cut)} "
                   f"({(cut - now).total_seconds() / 86400:.1f} days). The 05:00 ET refresh "
                   f"takes it once week {w - 1} is complete, if the PC is on.")
            if w in missed or cut <= now:
                alerts.append(("error", f"Week {w} MISSED: no snapshot before its cutoff ({_et(cut)}). "
                                        "The period is a NO-GO."))
            elif cut - now <= pd.Timedelta(days=WARN_BEFORE_CUTOFF_DAYS):
                alerts.append(("warning", due))
            elif not any(lvl == "info" for lvl, _ in alerts):
                alerts.append(("info", f"Next: {due[0].lower()}{due[1:]}"))
    if not chain_ok:
        alerts.insert(0, ("error", f"Ledger chain fails: {chain_msg}. No prediction can be trusted."))
    if last_tick is None:
        alerts.insert(0, ("error", "No status.md: the tick has never run."))
    elif now - last_tick > pd.Timedelta(hours=STALE_TICK_HOURS):
        alerts.insert(0, ("error", f"No tick for {(now - last_tick).total_seconds() / 3600:.0f} h "
                                   f"(last {_et(last_tick)}). Was the PC on and logged in at 05:00 ET?"))
    verdict = (by.get("period_verdict") or [None])[-1]
    if verdict is not None:
        alerts.insert(0, ("success" if verdict["go"] else "error",
                          f"Period verdict: {'GO' if verdict['go'] else 'NO-GO'} "
                          f"(decided {_et(verdict.get('decided_at'))})."))
    return {"shadow_id": sd.name, "chain_ok": chain_ok, "chain": chain_msg,
            "last_tick": _et(last_tick), "alerts": alerts, "weeks": pd.DataFrame(rows),
            "last_tick_hours": None if last_tick is None else (now - last_tick).total_seconds() / 3600,
            "counts": {k: len(v) for k, v in by.items()}, "verdict": verdict,
            "aliases": [(a["alias"], a["model"], a["reason"]) for a in by.get("alias", [])],
            "status_md": status.read_text(encoding="utf-8") if status.exists() else "",
            "replays": sorted((sd / "replay").glob("replay-*.json"))}


def jobs(lab_root: Path) -> pd.DataFrame:
    path = lab_root / "jobs.sqlite3"
    if not path.exists():
        return pd.DataFrame()
    df = _ro_query(path, "SELECT run_id, state, attempt, retries, error_kind, created_at, "
                         "updated_at FROM jobs ORDER BY job_id DESC")
    for c in ("created_at", "updated_at"):
        df[c] = pd.to_datetime(df[c], unit="s", utc=True).map(_et)
    return df


def run_dirs(lab_root: Path) -> list[Path]:
    return sorted((p for p in (lab_root / "runs").glob("*") if p.is_dir()), reverse=True)


def hypotheses(path: Path = HYPOTHESES) -> pd.DataFrame:
    return pd.DataFrame(json.loads(path.read_text(encoding="utf-8"))["hypotheses"])


# --- distributions (plan §37.2 page 13) ------------------------------------------------

def over_under(pmf: np.ndarray, line: float) -> dict[str, float]:
    """P(over), P(push), P(under) of an integer total table at `line` (same rule as
    `market.outcome_probs`; a test pins them together)."""
    k = int(np.floor(line))
    at_or_below = float(pmf[: min(max(k, -1), len(pmf) - 1) + 1].sum())
    push = float(pmf[k]) if line == k and 0 <= k < len(pmf) else 0.0
    return {"over": 1.0 - at_or_below, "push": push, "under": at_or_below - push}


def _teams(raw_dir: Path, seasons) -> dict[int, dict]:
    out = {}
    for s in sorted(set(int(x) for x in seasons)):
        path = raw_dir / f"games_{s}.json"
        if path.exists():
            for g in json.loads(path.read_text(encoding="utf-8")):
                if g.get("id") is None:
                    continue
                out[g["id"]] = {"home": g.get("homeTeam"), "away": g.get("awayTeam"),
                                "kickoff": pd.to_datetime(g.get("startDate"), utc=True, errors="coerce")}
    return out


def shadow_predictions(sd: Path, raw_dir: Path, week: int) -> tuple[pd.DataFrame, np.ndarray, dict]:
    """The week's latest snapshot: one row per game (both aliases) and its checked table."""
    records, _ = read_only(sd / "ledger.sqlite3")
    snaps = [r.payload for r in records if r.kind == "snapshot" and r.payload["week"] == week]
    if not snaps:
        return pd.DataFrame(), np.zeros((0, 0)), {}
    snap = snaps[-1]
    blob = (sd / snap["pmf_file"]).read_bytes()
    if hashlib.sha256(blob).hexdigest() != snap["pmf_sha256"]:
        raise ValueError(f"{snap['pmf_file']} does not match its ledger checksum")
    pmf = np.load(sd / snap["pmf_file"])
    preds = pd.DataFrame([r.payload for r in records if r.kind == "prediction"
                          and r.payload["snapshot_id"] == snap["snapshot_id"]])
    champ = preds[preds["alias"] == "champion"].set_index("game_id")["point"].rename("champion")
    ch = preds[preds["alias"] == "challenger"].set_index("game_id")
    df = ch[["point", "pmf_row", "q10", "q50", "q90", "p_home_win"]].rename(
        columns={"point": "challenger"}).join(champ)
    teams = _teams(raw_dir, [pd.Timestamp(snap["cutoff"]).year])
    df["game"] = [f"{teams.get(g, {}).get('away', '?')} @ {teams.get(g, {}).get('home', '?')}" for g in df.index]
    df["kickoff"] = [_et(teams.get(g, {}).get("kickoff")) for g in df.index]
    df = df.reset_index().sort_values(["kickoff", "game"])
    return df[["game_id", "kickoff", "game", "champion", "challenger", "q10", "q50", "q90",
               "p_home_win", "pmf_row"]], pmf, snap


def dist_outer(run_dir: Path, raw_dir: Path) -> tuple[pd.DataFrame, np.ndarray]:
    """A distribution run's outer-fold games (selected candidate's table) with team names."""
    pmf = np.load(run_dir / "pmf_outer.npy")
    order = pd.read_csv(run_dir / "pmf_games.csv")["game_id"]
    pred = pd.read_csv(run_dir / "predictions.csv").set_index("game_id").loc[order].reset_index()
    teams = _teams(raw_dir, pred["season"].unique())
    pred["game"] = [f"{teams.get(g, {}).get('away', '?')} @ {teams.get(g, {}).get('home', '?')}"
                    for g in pred["game_id"]]
    pred["pmf_row"] = range(len(pred))
    return pred, pmf


# --- historical replay (plan §37.2 page 12) ---------------------------------------------

def replay_week(snapshots: pd.DataFrame, raw_dir: Path, season: int, week: int
                ) -> tuple[pd.DataFrame, pd.DataFrame, dict]:
    """One week as the lab saw it at its cutoff: the frozen ridge_v1 ratings, and each game's
    forecast from them beside what happened. `snapshots` is Release B's snapshot CSV."""
    from scripts.weekly_ratings import Ratings, forecast_total

    snap = snapshots[(snapshots["method"] == "ridge_v1") & (snapshots["season"] == season)
                     & (snapshots["as_of_week"] == week)]
    if snap.empty:
        return pd.DataFrame(), pd.DataFrame(), {}
    first = snap.iloc[0]
    table = snap.set_index("team")[["O", "D", "P", "n_games", "n_possessions"]]
    r = Ratings(mu=first["mu"], nu=first["nu"], h=first["h"], c=first["c"], table=table, unrated=0.0)
    games = json.loads((raw_dir / f"games_{season}.json").read_text(encoding="utf-8"))
    rows = []
    for g in games:
        if (g.get("week") != week or g.get("seasonType") != "regular"
                or g.get("homeClassification") != "fbs" or g.get("awayClassification") != "fbs"):
            continue
        total = (g["homePoints"] + g["awayPoints"]) if g.get("completed") else None
        fc = forecast_total(r, g["homeTeam"], g["awayTeam"], bool(g.get("neutralSite")))
        rows.append({"game_id": g["id"], "kickoff": _et(pd.to_datetime(g.get("startDate"), utc=True)),
                     "game": f"{g['awayTeam']} @ {g['homeTeam']}", "forecast": fc,
                     "actual": total, "miss": None if total is None else fc - total})
    meta = {"as_of": first["as_of_ts"], "teams": len(table), "mu": first["mu"], "nu": first["nu"],
            "h": first["h"], "c": first["c"]}
    return (pd.DataFrame(rows).sort_values("kickoff") if rows else pd.DataFrame(),
            table.sort_values("O", ascending=False).reset_index(), meta)


# --- data quality and lineage (plan §37.2 page 11) ---------------------------------------

def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def lineage(root: Path, data_root: Path, hasher=sha256_file) -> pd.DataFrame:
    """Every published run's recorded source hashes against the files on disk now. A
    'changed' row is a data revision since the run: its numbers no longer reproduce."""
    rows = []
    for d in run_dirs(root):
        path = d / "manifest.json"
        if not path.exists():
            continue
        for src in json.loads(path.read_text(encoding="utf-8")).get("sources", []):
            f = data_root / src["path"]
            now_sha = hasher(f) if f.exists() else None
            rows.append({"run_id": d.name, "path": src["path"],
                         "status": "missing" if now_sha is None else
                         ("same" if now_sha == src["sha256"] else "changed"),
                         "recorded": src["sha256"][:12], "now": (now_sha or "")[:12]})
    return pd.DataFrame(rows)


def freshness(data_root: Path, season: int) -> pd.DataFrame:
    """Age of the inputs the live system reads."""
    items = {"CFBD games": data_root / "raw" / f"games_{season}.json",
             "CFBD drives": data_root / "raw" / f"drives_{season}.json",
             "CFBD lines": data_root / "raw" / f"lines_{season}.json"}
    an = sorted((data_root / "raw" / "actionnetwork").glob("history_event_*.json"),
                key=lambda p: p.stat().st_mtime)
    if an:
        items["Action Network history (newest file)"] = an[-1]
    now = time.time()
    return pd.DataFrame([{"input": k, "file": p.name, "updated": _et(pd.Timestamp(p.stat().st_mtime, unit="s", tz="UTC"))
                          if p.exists() else "missing",
                          "age_hours": round((now - p.stat().st_mtime) / 3600, 1) if p.exists() else None}
                         for k, p in items.items()])


def drops(eval_json: Path) -> pd.DataFrame:
    """Release B's per-season game counts and exclusions (why games are not in the frame)."""
    if not eval_json.exists():
        return pd.DataFrame()
    d = json.loads(eval_json.read_text(encoding="utf-8"))["drops_by_season"]
    return pd.DataFrame(d).T.fillna(0).astype(int).rename_axis("season").reset_index()


# --- registry (plan §37.2 page 16) ------------------------------------------------------

def registry(root: Path) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Published runs, and every alias move in every shadow ledger (newest last)."""
    runs = []
    for d in run_dirs(root):
        m = json.loads((d / "manifest.json").read_text(encoding="utf-8")) if (d / "manifest.json").exists() else {}
        runs.append({"run_id": d.name, "kind": "distribution" if d.name.startswith("dist-") else "tuning",
                     "spec": m.get("spec_id") or m.get("base_run_id"), "generated": m.get("generated_at"),
                     "git": m.get("git_sha"), "code": (m.get("code_sha256") or "")[:12],
                     "card": (d / "card.md").exists()})
    moves = []
    for sd in sorted((root / "shadow").glob("shadow-*")):
        if (sd / "ledger.sqlite3").exists():
            recs, _ = read_only(sd / "ledger.sqlite3")
            moves += [{"shadow": sd.name, "at": _et(pd.Timestamp(r.created_at)), **r.payload}
                      for r in recs if r.kind == "alias"]
    return pd.DataFrame(runs), pd.DataFrame(moves)

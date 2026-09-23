"""Read-only data for the lab GUI (`models/tuning/ui/app.py`). Nothing here writes;
`actions.py` holds the few things that do.

Standard library and pandas only, so the GUI's own venv (`.venv-lab-ui`) needs no
optuna or sklearn, and the shadow tick's `.venv` never gets the GUI's packages.
Every database is opened read-only, so the GUI cannot block the tick or a worker.
"""
from __future__ import annotations

import json
import os
import sqlite3
import time
from pathlib import Path

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
    con = sqlite3.connect(f"file:{path.as_posix()}?mode=ro", uri=True)
    try:
        df = pd.read_sql_query("SELECT run_id, state, attempt, retries, error_kind, created_at, "
                               "updated_at FROM jobs ORDER BY job_id DESC", con)
    finally:
        con.close()
    for c in ("created_at", "updated_at"):
        df[c] = pd.to_datetime(df[c], unit="s", utc=True).map(_et)
    return df


def run_dirs(lab_root: Path) -> list[Path]:
    return sorted((p for p in (lab_root / "runs").glob("*") if p.is_dir()), reverse=True)


def hypotheses(path: Path = HYPOTHESES) -> pd.DataFrame:
    return pd.DataFrame(json.loads(path.read_text(encoding="utf-8"))["hypotheses"])

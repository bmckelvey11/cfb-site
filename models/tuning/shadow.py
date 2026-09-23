"""Live shadow system (Release E): freeze once, then `tick` daily.

    python -m models.tuning shadow freeze --spec models/tuning/specs/shadow_2026_w05_08.json
    python -m models.tuning shadow tick   --spec models/tuning/specs/shadow_2026_w05_08.json
    python -m models.tuning shadow alias  --spec ... --alias champion --model M --reason "..."

`freeze` seals the challenger (Release C's model refit on every usable season, Release D's
joint residual and overtime pools from the window seasons) and writes a freeze JSON that
is committed before the first snapshot. `tick` runs after the daily data refresh: it
verifies the ledger chain and the frozen checksums, snapshots the next week while the
calendar is between weeks, records a `missed` week, scores finished games against the
prediction made last before each game's kickoff, logs data revisions, hashes the week's
Action Network history files, writes the period verdict once the period is over, and
rewrites `status.md`. Counting rules: the design spec for Release E.
"""
from __future__ import annotations

import hashlib
import io
import json
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
import pandas as pd

from models.tuning.distributions import joint_pmf, score_pmf, season_forecasts
from models.tuning.estimators import build_pipeline
from models.tuning.features import fit_digest, live_week_frame, load_frame
from models.tuning.ledger import Ledger
from models.tuning.shadow_spec import ShadowSpec
from models.tuning.worker import _git, code_fingerprint, verify_run

TARGETS = ("target", "home_reg", "away_reg")
SPECS_DIR = Path(__file__).with_name("specs")
ALIASES = ("champion", "challenger")


class ShadowRefused(Exception):
    pass


def _sha(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _npy(a: np.ndarray) -> bytes:
    buf = io.BytesIO()
    np.save(buf, np.ascontiguousarray(a, dtype=np.float64), allow_pickle=False)
    return buf.getvalue()


def shadow_dir(root: Path, spec: ShadowSpec) -> Path:
    return Path(root) / "shadow" / spec.shadow_id()


def freeze_path(spec: ShadowSpec) -> Path:
    return SPECS_DIR / f"{spec.spec_id}.freeze.json"


def _fit_params(pipe) -> dict:
    imp, scale, est = pipe.named_steps["impute"], pipe.named_steps["scale"], pipe.named_steps["model"]
    return {"impute_median": imp.statistics_.tolist(), "scale_mean": scale.mean_.tolist(),
            "scale_sd": scale.scale_.tolist(), "coef": np.ravel(est.coef_).tolist(),
            "intercept": float(est.intercept_)}


def predict_params(params: dict, x: np.ndarray) -> np.ndarray:
    """The fitted pipeline as arithmetic: impute medians, standardize, dot, intercept."""
    x = np.where(np.isnan(x), np.asarray(params["impute_median"]), x)
    z = (x - np.asarray(params["scale_mean"])) / np.asarray(params["scale_sd"])
    return z @ np.asarray(params["coef"]) + params["intercept"]


# --- freeze ---------------------------------------------------------------------

def freeze(spec: ShadowSpec, lab_root: Path, data_root: Path, out: Path | None = None) -> dict:
    from models.tuning.dist_run import load_base_run
    from models.tuning.dist_spec import DistRunSpec

    out = out or freeze_path(spec)
    if out.exists():
        raise ShadowRefused(f"{out} already holds a freeze; it is never rewritten")
    base, base_manifest, outer, _ = load_base_run(lab_root, spec.base_run_id)
    dist_dir = lab_root / "runs" / spec.dist_run_id
    if not verify_run(dist_dir):
        raise ShadowRefused(f"{dist_dir} is missing or fails its checksums")
    dist = DistRunSpec.model_validate_json((dist_dir / "dist_spec.json").read_text(encoding="utf-8"))
    scores = json.loads((dist_dir / "scores.json").read_text(encoding="utf-8"))
    if dist.base_run_id != spec.base_run_id or scores["selected"] != "joint_bootstrap":
        raise ShadowRefused("the distribution run must be joint_bootstrap on the same base run")
    model = outer[0].model
    frame, report = load_frame(base.dataset, base.feature_set, data_root)
    feats = report.kept
    usable = frame[~frame["season"].isin(base.folds.exclude_seasons)]
    x = usable[feats].to_numpy(dtype=float)
    params = {}
    for t in TARGETS:
        pipe = build_pipeline(model, base.seeds.model).fit(x, usable[t].to_numpy(dtype=float))
        params[t] = _fit_params(pipe)
        if not np.allclose(predict_params(params[t], x), pipe.predict(x), rtol=0, atol=1e-9):
            raise ShadowRefused(f"frozen arithmetic does not reproduce the pipeline for {t}")

    window = list(spec.window_seasons)
    mu = {t: season_forecasts(frame, base, model, t, window) for t in TARGETS}
    w = frame[frame["season"].isin(window)]
    early = (w["min_prior_games"] < dist.distribution.early_min_prior_games).to_numpy()
    pairs = np.column_stack([(w["home_reg"] - mu["home_reg"][w.index]).to_numpy(),
                             (w["away_reg"] - mu["away_reg"][w.index]).to_numpy()])
    ot = w.loc[w["ot_points"] > 0, "ot_points"].to_numpy(dtype=float)
    ref = frame[frame["season"].isin(range(2021, 2026))]
    drift_ref = {int(wk): {"rv1_total_mean": float(g["rv1_total"].mean()),
                           "rv1_total_sd": float(g["rv1_total"].std(ddof=1)),
                           "residual_sd": float((g["target"] - g["rv1_total"]).std(ddof=1)),
                           "n": int(len(g))}
                 for wk, g in ref.groupby("week")}

    files = {"challenger.json": (json.dumps({"model": model.model_dump(), "features": feats,
                                             "params": params}, indent=2, sort_keys=True) + "\n"
                                 ).encode("utf-8"),
             "pairs_early.npy": _npy(pairs[early]), "pairs_primary.npy": _npy(pairs[~early]),
             "ot.npy": _npy(ot)}
    frozen_dir = shadow_dir(lab_root, spec) / "frozen"
    frozen_dir.mkdir(parents=True, exist_ok=True)
    for name, data in files.items():
        (frozen_dir / name).write_bytes(data)
    doc = {"shadow_id": spec.shadow_id(), "spec_config_hash": spec.config_hash,
           "base_run_id": spec.base_run_id, "base_code_sha256": base_manifest["code_sha256"],
           "dist_run_id": spec.dist_run_id, "support_max": dist.distribution.support_max,
           "early_min_prior_games": dist.distribution.early_min_prior_games,
           "features": feats, "model": model.model_dump(),
           "artifacts": {name: _sha(data) for name, data in files.items()},
           "pools": {"pairs_early": int(early.sum()), "pairs_primary": int((~early).sum()),
                     "ot": int(len(ot)), "window_seasons": window},
           "drift_reference": drift_ref, "code_sha256": code_fingerprint(),
           "git_sha": _git("rev-parse", "--short=12", "HEAD"),
           "frozen_at": datetime.now(timezone.utc).isoformat(timespec="seconds")}
    out.write_text(json.dumps(doc, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return doc


def load_frozen(spec: ShadowSpec, lab_root: Path, freeze_file: Path | None = None) -> dict:
    """The committed freeze plus its artifacts, every checksum verified, or a refusal."""
    freeze_file = freeze_file or freeze_path(spec)
    if not freeze_file.exists():
        raise ShadowRefused(f"no freeze at {freeze_file}: run `shadow freeze` and commit it")
    doc = json.loads(freeze_file.read_text(encoding="utf-8"))
    if doc["spec_config_hash"] != spec.config_hash:
        raise ShadowRefused("the freeze was made for a different shadow spec")
    frozen_dir = shadow_dir(lab_root, spec) / "frozen"
    blobs = {}
    for name, sha in doc["artifacts"].items():
        path = frozen_dir / name
        if not path.exists() or _sha(path.read_bytes()) != sha:
            raise ShadowRefused(f"frozen artifact {name} is missing or altered")
        blobs[name] = path.read_bytes()
    ch = json.loads(blobs["challenger.json"])
    return {**doc, "challenger": ch,
            "pairs": {"early": np.load(io.BytesIO(blobs["pairs_early.npy"])),
                      "primary": np.load(io.BytesIO(blobs["pairs_primary.npy"]))},
            "ot": np.load(io.BytesIO(blobs["ot.npy"]))}


# --- schedule helpers -----------------------------------------------------------

def _schedule(payload: list[dict], season: int) -> pd.DataFrame:
    """FBS-vs-FBS regular-season games as the schedule reads now; `total` once final.

    Scoring reads the final score from here, not from Release B's game table, which drops
    games whose line scores do not add up; such a game still has a result to score.
    """
    rows = []
    for g in payload:
        if not (g.get("seasonType") == "regular" and g.get("season", season) == season
                and g.get("homeClassification") == "fbs" and g.get("awayClassification") == "fbs"
                and g.get("startDate")):
            continue
        done = bool(g.get("completed")) and g.get("homePoints") is not None \
            and g.get("awayPoints") is not None
        rows.append({"game_id": g["id"], "week": g["week"], "completed": done,
                     "kickoff": pd.Timestamp(g["startDate"]).tz_convert("UTC"),
                     "total": float(g["homePoints"] + g["awayPoints"]) if done else np.nan})
    return pd.DataFrame(rows, columns=["game_id", "week", "completed", "kickoff", "total"])


def _ready(sched: pd.DataFrame, cutoff: pd.Timestamp, now: pd.Timestamp, spec: ShadowSpec
           ) -> tuple[bool, list[str]]:
    """Between weeks, and last week's results are in (or the cutoff is close)."""
    before = sched[sched["kickoff"] < cutoff]
    if (before["kickoff"] >= now).any():
        return False, ["an earlier game has not kicked off yet"]
    recent = before[(before["kickoff"] <= now - pd.Timedelta(hours=spec.snapshot_grace_hours))
                    & (before["kickoff"] > now - pd.Timedelta(days=10))]
    pending = recent[~recent["completed"]]
    late = before[(before["kickoff"] > now - pd.Timedelta(hours=spec.snapshot_grace_hours))]
    stale = [f"{len(pending)} recent games not final"] if len(pending) else []
    stale += [f"{len(late)} games still inside the grace window"] if len(late) else []
    if stale and now < cutoff - pd.Timedelta(hours=spec.force_before_cutoff_hours):
        return False, stale
    return True, stale


def _quantile(cdf: np.ndarray, tau: float) -> int:
    return int((cdf >= tau - 1e-12).argmax())


# --- tick ------------------------------------------------------------------------

def _snapshot(spec, frozen, ledger, sd, data_root, week, cutoff, now, warnings) -> None:
    frame, meta = live_week_frame(spec.season, week, data_root, spec.first_season, spec.ridge_lambda)
    ch = frozen["challenger"]
    x = frame[ch["features"]].to_numpy(dtype=float)
    mu = {t: predict_params(ch["params"][t], x) for t in TARGETS}
    early = frame["min_prior_games"].to_numpy() < frozen["early_min_prior_games"]
    pools = [frozen["pairs"]["early" if e else "primary"] for e in early]
    pmf, home_win, tie = joint_pmf(mu["home_reg"], mu["away_reg"], pools,
                                   [frozen["ot"]] * len(frame), frozen["support_max"])
    generated = now.isoformat()
    stamp = now.strftime("%Y%m%dT%H%M%SZ")
    blob = _npy(pmf)
    rel = f"snapshots/week{week:02d}_{stamp}.npy"
    (sd / "snapshots").mkdir(parents=True, exist_ok=True)
    (sd / rel).write_bytes(blob)
    snap_id = f"{week}:{stamp}"
    items = [("snapshot", {
        "snapshot_id": snap_id, "week": week, "rehearsal": week in spec.rehearsal_weeks,
        "cutoff": cutoff.isoformat(), "generated_at": generated, "fit_digest": meta["fit_digest"],
        "n_fit": meta["n_fit"], "games": [int(g) for g in frame["game_id"]],
        "pmf_file": rel, "pmf_sha256": _sha(blob), "code_sha256": code_fingerprint(),
        "warnings": warnings})]
    cdf = np.cumsum(pmf, axis=1)
    for i, g in enumerate(frame.itertuples()):
        common = {"snapshot_id": snap_id, "week": week, "game_id": int(g.game_id),
                  "generated_at": generated, "decision_ts": cutoff.isoformat(),
                  "kickoff_at_snapshot": g.kickoff.isoformat()}
        items.append(("prediction", {**common, "alias": "champion", "model": spec.champion,
                                     "point": float(g.rv1_total)}))
        items.append(("prediction", {
            **common, "alias": "challenger", "model": f"lab_joint:{spec.dist_run_id}",
            "point": float(mu["target"][i]), "pmf_row": i,
            "pmf_mean": float(pmf[i] @ np.arange(pmf.shape[1])),
            "q10": _quantile(cdf[i], 0.1), "q50": _quantile(cdf[i], 0.5),
            "q90": _quantile(cdf[i], 0.9), "p_home_win": float(home_win[i])}))
    ledger.append_many(items, created_at=generated[:19] + "+00:00")


def _counted(preds: list, game_id: int, alias: str, kickoff: pd.Timestamp):
    """The last prediction for this game and alias generated before its kickoff."""
    before = [p for p in preds if p.payload["game_id"] == game_id and p.payload["alias"] == alias
              and pd.Timestamp(p.payload["generated_at"]) < kickoff]
    return before[-1] if before else None


def tick(spec: ShadowSpec, lab_root: Path, data_root: Path, now: pd.Timestamp | None = None,
         freeze_file: Path | None = None) -> int:
    from scripts.weekly_ratings import fit_set
    from scripts.weekly_ratings_eval import load

    now = now or pd.Timestamp.now(tz="UTC").floor("s")
    sd = shadow_dir(lab_root, spec)
    ledger = Ledger(sd / "ledger.sqlite3")
    ok, why = ledger.verify()
    if not ok:
        print(f"shadow: ledger chain fails ({why}); no predictions")
        return 1
    try:
        frozen = load_frozen(spec, lab_root, freeze_file)
    except ShadowRefused as e:
        print(f"shadow: {e}; no predictions")
        return 1
    if not ledger.records("arm"):
        ledger.append_many([
            ("arm", {"shadow_id": spec.shadow_id(), "spec_config_hash": spec.config_hash,
                     "period_weeks": list(spec.period_weeks),
                     "rehearsal_weeks": list(spec.rehearsal_weeks),
                     "artifacts": frozen["artifacts"], "policy": spec.policy.model_dump(),
                     "execution": spec.execution.model_dump()}),
            ("alias", {"alias": "champion", "model": spec.champion, "reason": "initial"}),
            ("alias", {"alias": "challenger", "model": f"lab_joint:{spec.dist_run_id}",
                       "reason": "initial"})])

    payload = json.loads((data_root / "raw" / f"games_{spec.season}.json").read_text(encoding="utf-8"))
    sched = _schedule(payload, spec.season)
    weeks = sorted(set(spec.period_weeks) | set(spec.rehearsal_weeks))
    cutoffs = {w: sched.loc[sched["week"] == w, "kickoff"].min() for w in weeks
               if (sched["week"] == w).any()}
    log = []

    # 1. Snapshot the next week while the calendar sits between weeks.
    upcoming = [w for w in weeks if w in cutoffs and cutoffs[w] > now]
    if upcoming:
        w = upcoming[0]
        ready, warnings = _ready(sched, cutoffs[w], now, spec)
        if ready:
            _snapshot(spec, frozen, ledger, sd, data_root, w, cutoffs[w], now, warnings)
            log.append(f"snapshot week {w}" + (f" ({'; '.join(warnings)})" if warnings else ""))
        else:
            log.append(f"waiting for week {w}: {'; '.join(warnings)}")

    snaps = ledger.records("snapshot")
    snapped = {r.payload["week"] for r in snaps}
    missed = {r.payload["week"] for r in ledger.records("missed")}
    for w in weeks:
        if w in cutoffs and cutoffs[w] <= now and w not in snapped and w not in missed:
            ledger.append("missed", {"week": w, "reason": "no snapshot before the cutoff",
                                     "cutoff": cutoffs[w].isoformat()})
            log.append(f"MISSED week {w}")

    # 2. Score finished games against the prediction that counts.
    final = sched[sched["completed"]].set_index("game_id")
    kick_now = sched.set_index("game_id")["kickoff"]
    preds = ledger.records("prediction")
    scored = {(r.payload["game_id"], r.payload["alias"]) for r in ledger.records("score")}
    snap_by_id = {r.payload["snapshot_id"]: r for r in ledger.records("snapshot")}
    pmf_cache: dict[str, np.ndarray | None] = {}
    new_scores = []
    for gid in sorted({p.payload["game_id"] for p in preds}):
        if gid not in final.index or gid not in kick_now.index:
            continue
        for alias in ALIASES:
            if (gid, alias) in scored:
                continue
            p = _counted(preds, gid, alias, kick_now[gid])
            if p is None:
                continue
            y = float(final.at[gid, "total"])
            rec = {"game_id": int(gid), "week": p.payload["week"], "alias": alias,
                   "prediction_seq": p.seq, "generated_at": p.payload["generated_at"],
                   "kickoff_final": kick_now[gid].isoformat(), "final_total": y,
                   "point": p.payload["point"], "abs_error": abs(p.payload["point"] - y),
                   "timing_ok": pd.Timestamp(p.payload["generated_at"]) < kick_now[gid],
                   "artifact_ok": True}
            if alias == "challenger":
                snap = snap_by_id[p.payload["snapshot_id"]]
                fid = snap.payload["pmf_file"]
                if fid not in pmf_cache:
                    path = sd / fid
                    ok_file = path.exists() and _sha(path.read_bytes()) == snap.payload["pmf_sha256"]
                    pmf_cache[fid] = np.load(path) if ok_file else None
                pmf = pmf_cache[fid]
                if pmf is None:
                    rec["artifact_ok"] = False
                else:
                    sc = score_pmf(pmf[[p.payload["pmf_row"]]], np.array([y]), (0.5,), (0.8,))
                    rec |= {"crps": float(sc.loc[0, "crps"]), "pit": float(sc.loc[0, "pit"]),
                            "cover_80": bool(sc.loc[0, "cover_0.8"])}
            new_scores.append(("score", rec))
    if new_scores:
        ledger.append_many(new_scores)
        log.append(f"scored {len(new_scores)} predictions")

    # 3. Data revisions: rebuild each week's as-of evidence and compare digests.
    games, _ = load(data_root, [spec.season], [])
    season_games = games[games["season"] == spec.season]
    revised = {(r.payload["week"], r.payload["rebuilt"]) for r in ledger.records("revision")}
    for w, cut in cutoffs.items():
        week_snaps = [s for s in snaps if s.payload["week"] == w
                      and pd.Timestamp(s.payload["generated_at"]) < cut]
        if cut > now or not week_snaps:
            continue
        recorded = week_snaps[-1].payload["fit_digest"]
        rebuilt = fit_digest(fit_set(season_games, cut))
        if rebuilt != recorded and (w, rebuilt) not in revised:
            ledger.append("revision", {"week": w, "recorded": recorded, "rebuilt": rebuilt,
                                       "snapshot_id": week_snaps[-1].payload["snapshot_id"]})
            log.append(f"revision logged for week {w}")

    # 4. Archive the week's Action Network history once its games are underway.
    archived = {r.payload["week"] for r in ledger.records("quotes_archived")}
    for w in weeks:
        last = sched.loc[sched["week"] == w, "kickoff"].max() if w in cutoffs else None
        if w in archived or last is None or now < last + pd.Timedelta(hours=12):
            continue
        xwalk, unmatched = an_crosswalk(data_root, spec.season, w, payload)
        files = {}
        for event, gid in sorted(xwalk.items()):
            path = data_root / "raw" / "actionnetwork" / f"history_event_{event}.json"
            if path.exists():
                files[str(event)] = {"game_id": gid, "sha256": _sha(path.read_bytes())}
        ledger.append("quotes_archived", {"week": w, "matched": len(xwalk), "files": files,
                                          "unmatched_events": unmatched})
        log.append(f"archived {len(files)} AN history files for week {w}")

    _verdict(spec, ledger, sched, final, now, sd)
    write_status(spec, ledger, frozen, sched, now, sd, log)
    print("shadow: " + ("; ".join(log) if log else "nothing to do"))
    return 0


def expected_games(spec: ShadowSpec, ledger: Ledger) -> dict[int, list[int]]:
    """Per period week: the games in its last snapshot generated before the cutoff."""
    out = {}
    for s in ledger.records("snapshot"):
        w = s.payload["week"]
        if w in spec.period_weeks and pd.Timestamp(s.payload["generated_at"]) < pd.Timestamp(s.payload["cutoff"]):
            out[w] = s.payload["games"]
    return out


def period_tally(spec, ledger, sched, final, now) -> dict:
    kick = sched.set_index("game_id")["kickoff"]
    exp = expected_games(spec, ledger)
    scores = {(r.payload["game_id"], r.payload["alias"]): r.payload for r in ledger.records("score")}
    t = {"expected": 0, "scored": 0, "no_action": 0, "pending": 0, "missing": [],
         "timing_violations": [], "artifact_failures": [],
         "missed_weeks": sorted(r.payload["week"] for r in ledger.records("missed")
                                if r.payload["week"] in spec.period_weeks),
         "revisions": len([r for r in ledger.records("revision")
                           if r.payload["week"] in spec.period_weeks]),
         "weeks_snapshotted": sorted(exp)}
    preds = ledger.records("prediction")
    for w, gids in exp.items():
        for gid in gids:
            t["expected"] += 1
            k = kick.get(gid)
            if all((gid, a) in scores for a in ALIASES):
                t["scored"] += 1
                for a in ALIASES:
                    if not scores[(gid, a)]["timing_ok"]:
                        t["timing_violations"].append(gid)
                    if not scores[(gid, a)]["artifact_ok"]:
                        t["artifact_failures"].append(gid)
            elif gid not in final.index and (k is None or now > k + pd.Timedelta(days=spec.no_action_after_days)):
                t["no_action"] += 1
            elif gid in final.index and any(_counted(preds, gid, a, k) is None for a in ALIASES):
                t["missing"].append(gid)
            else:
                t["pending"] += 1
    return t


def _verdict(spec, ledger, sched, final, now, sd) -> None:
    if ledger.records("period_verdict"):
        return
    weeks_known = set(sched["week"])
    if not set(spec.period_weeks) <= weeks_known:
        return
    t = period_tally(spec, ledger, sched, final, now)
    all_snapped = set(t["weeks_snapshotted"]) | set(t["missed_weeks"]) >= set(spec.period_weeks)
    if not all_snapped or t["pending"]:
        return
    ok, why = ledger.verify()
    go = (ok and not t["missing"] and not t["timing_violations"] and not t["artifact_failures"]
          and not t["missed_weeks"])
    ledger.append("period_verdict", {**{k: v for k, v in t.items()}, "chain": why, "go": go,
                                     "decided_at": now.isoformat()})


def set_alias(spec: ShadowSpec, lab_root: Path, alias: str, model: str, reason: str) -> None:
    """Promotion or rollback moves an alias with a reason; artifacts never change."""
    if alias not in ALIASES:
        raise ShadowRefused(f"unknown alias {alias}")
    Ledger(shadow_dir(lab_root, spec) / "ledger.sqlite3").append(
        "alias", {"alias": alias, "model": model, "reason": reason})


def an_crosswalk(data_root: Path, season: int, week: int, payload: list[dict]
                 ) -> tuple[dict[int, int], list[int]]:
    """Action Network event id -> CFBD game id for one week, by teams (duckdb_load's rule)."""
    from cfb_system_maker.duckdb_load import _AN_SCHOOL_ALIAS

    path = data_root / "raw" / "actionnetwork" / f"scoreboard_{season}_wk{week}.json"
    if not path.exists():
        return {}, []
    board = json.loads(path.read_text(encoding="utf-8")).get("games", [])
    cfbd = {(g["homeTeam"], g["awayTeam"]): g["id"] for g in payload
            if g.get("week") == week and g.get("seasonType") == "regular"}
    out, unmatched = {}, []
    for e in board:
        loc = {t["id"]: _AN_SCHOOL_ALIAS.get(t.get("location"), t.get("location"))
               for t in e.get("teams", [])}
        key = (loc.get(e.get("home_team_id")), loc.get(e.get("away_team_id")))
        if key in cfbd:
            out[int(e["id"])] = int(cfbd[key])
        else:
            unmatched.append(int(e["id"]))
    return out, unmatched


def write_status(spec, ledger, frozen, sched, now, sd, log) -> None:
    scores = [r.payload for r in ledger.records("score")]
    snaps = ledger.records("snapshot")
    lines = [f"# Shadow status: {spec.spec_id} (`{spec.shadow_id()}`)", "",
             f"As of {now.isoformat()}. Period weeks {', '.join(map(str, spec.period_weeks))}"
             + (f"; rehearsal {', '.join(map(str, spec.rehearsal_weeks))}" if spec.rehearsal_weeks else "")
             + f". Chain: {ledger.verify()[1]}.", "",
             "| week | cutoff (UTC) | snapshots | games | scored | champion MAE | challenger MAE "
             "| challenger CRPS | 80% cover | residual mean | rv1_total mean vs 2021–25 |",
             "| --- | --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | --- |"]
    weeks = sorted(set(spec.period_weeks) | set(spec.rehearsal_weeks))
    ref = frozen.get("drift_reference", {})
    for w in weeks:
        ws = [s for s in snaps if s.payload["week"] == w]
        sc = pd.DataFrame([s for s in scores if s["week"] == w])
        ch = sc[sc["alias"] == "challenger"] if len(sc) else sc
        cm = sc[sc["alias"] == "champion"] if len(sc) else sc
        cut = sched.loc[sched["week"] == w, "kickoff"].min() if (sched["week"] == w).any() else None
        preds = [p.payload for p in ledger.records("prediction")
                 if p.payload["week"] == w and p.payload["alias"] == "champion"]
        drift = ""
        if preds and str(w) in ref:
            last_snap = ws[-1].payload["snapshot_id"] if ws else None
            pts = [p["point"] for p in preds if p["snapshot_id"] == last_snap]
            r = ref[str(w)]
            z = (np.mean(pts) - r["rv1_total_mean"]) / (r["rv1_total_sd"] / np.sqrt(max(len(pts), 1)))
            drift = f"{np.mean(pts):.1f} vs {r['rv1_total_mean']:.1f} (z {z:+.1f}{', CHECK' if abs(z) > 3 else ''})"
        label = f"{w}{' (rehearsal)' if w in spec.rehearsal_weeks else ''}"

        def mean(col: str) -> str:  # a column is absent when every table failed its checksum
            return f"{ch[col].astype(float).mean():.2f}" if col in ch and ch[col].notna().any() else "—"

        lines.append(
            f"| {label} | {cut.strftime('%Y-%m-%d %H:%M') if cut is not None else '—'} | {len(ws)} | "
            f"{len(ws[-1].payload['games']) if ws else 0} | {len(ch)} | "
            f"{cm['abs_error'].mean():.2f} | {ch['abs_error'].mean():.2f} | "
            f"{mean('crps')} | {mean('cover_80')} | "
            f"{(ch['final_total'] - ch['point']).mean():+.2f} | {drift} |"
            if len(ch) else
            f"| {label} | {cut.strftime('%Y-%m-%d %H:%M') if cut is not None else '—'} | {len(ws)} | "
            f"{len(ws[-1].payload['games']) if ws else 0} | 0 | | | | | | {drift} |")
    verdict = ledger.records("period_verdict")
    lines += ["", "## Period", ""]
    if verdict:
        v = verdict[-1].payload
        lines.append(f"**Verdict: {'GO' if v['go'] else 'NO-GO'}.** Expected {v['expected']}, scored "
                     f"{v['scored']}, no-action {v['no_action']}, missing {len(v['missing'])}, timing "
                     f"violations {len(v['timing_violations'])}, artifact failures "
                     f"{len(v['artifact_failures'])}, missed weeks {v['missed_weeks'] or 'none'}, "
                     f"tracked revisions {v['revisions']}.")
    else:
        lines.append("Open: the verdict is written once every expected game is scored or no-action.")
    newest = pd.Timestamp(max((g["kickoff"] for g in sched[sched["completed"]].to_dict("records")),
                              default=pd.NaT)) if len(sched) else pd.NaT
    lines += ["", "## Data freshness", "", f"Newest completed game kicked off {newest}.", "",
              "## This run", "", *(f"- {m}" for m in (log or ["nothing to do"])), "",
              "Drift is an investigation trigger, not a refit (plan §34.3). Nothing here is "
              "priced; the frozen policy is replayed only after the period."]
    (sd / "status.md").write_text("\n".join(lines) + "\n", encoding="utf-8")

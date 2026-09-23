"""Release D join: predictive distributions on top of one published Release C run.

    python -m models.tuning dist --spec models/tuning/specs/dist_total_v1.json [--root DIR]

Reads the Release C run named by `base_run_id` (its checksums must verify), refuses if
today's source files differ from the ones that run recorded, rebuilds season-ahead
forecasts with its selected model (asserting they equal its outer predictions), builds
the three candidate tables, selects on the inner seasons, applies the declared gate once
to the outer seasons, and publishes `runs/dist-<hash12>/` atomically.
"""
from __future__ import annotations

import io
import json
import platform
from datetime import datetime, timezone
from importlib import metadata
from pathlib import Path

import numpy as np
import pandas as pd

from models.tuning.cards import render_dist_card
from models.tuning.dist_spec import DistRunSpec
from models.tuning.distributions import (
    calibration_report, empirical_pmf, joint_pmf, normal_pmf, open_label_scores, paired_diff,
    score_pmf, season_forecasts, window_seasons,
)
from models.tuning.features import load_frame, source_paths
from models.tuning.selective import aurc_vs_full, meta_scores, risk_coverage
from models.tuning.spec import FoldResult, RunSpec
from models.tuning.worker import (
    PACKAGES, _git, _sources_digest, code_fingerprint, publish_run, verify_run,
)

COVERAGES = (1.0, 0.9, 0.8, 0.7, 0.6, 0.5)


class DistRefused(Exception):
    pass


def load_base_run(root: Path, run_id: str) -> tuple[RunSpec, dict, list[FoldResult], pd.DataFrame]:
    run_dir = root / "runs" / run_id
    if not verify_run(run_dir):
        raise DistRefused(f"{run_dir} is missing or fails its checksums")
    spec = RunSpec.model_validate_json((run_dir / "run_spec.json").read_text(encoding="utf-8"))
    manifest = json.loads((run_dir / "manifest.json").read_text(encoding="utf-8"))
    outer = [FoldResult.model_validate_json(p.read_text(encoding="utf-8"))
             for p in sorted((run_dir / "outer").glob("*.json"))]
    if not outer or not all(r.verify() for r in outer):
        raise DistRefused(f"{run_id}: outer fold results are missing or fail their seals")
    if len({r.model for r in outer}) != 1:
        raise DistRefused(f"{run_id}: outer folds disagree on the selected model")
    predictions = pd.read_csv(run_dir / "predictions.csv")
    return spec, manifest, outer, predictions


def _pools(frame: pd.DataFrame, rows: pd.Index, early_min: int) -> dict:
    w = frame.loc[rows]
    seg = np.where(w["min_prior_games"] < early_min, "early", "primary") \
        if "min_prior_games" in w else np.full(len(w), "primary")
    out = {"sigma": float(w["r_total"].std(ddof=1)),
           "ot": w.loc[w["ot_points"] > 0, "ot_points"].to_numpy(dtype=float)}
    for s in ("early", "primary"):
        part = w[seg == s]
        if part.empty:
            part = w  # a segment with no window games falls back to the whole window
        out[s] = {"total": part["r_total"].to_numpy(dtype=float),
                  "pairs": part[["r_home", "r_away"]].to_numpy(dtype=float)}
    return out


def _tables(frame: pd.DataFrame, rows: pd.Index, pools: dict, dist) -> dict:
    g = frame.loc[rows]
    seg = np.where(g["min_prior_games"] < dist.early_min_prior_games, "early", "primary") \
        if "min_prior_games" in g else np.full(len(g), "primary")
    out = {}
    if "normal_const" in dist.candidates:
        out["normal_const"] = (normal_pmf(g["mu_total"].to_numpy(), np.full(len(g), pools["sigma"]),
                                          dist.support_max), None, None)
    if "empirical_total" in dist.candidates:
        out["empirical_total"] = (empirical_pmf(g["mu_total"].to_numpy(),
                                                [pools[s]["total"] for s in seg],
                                                dist.support_max), None, None)
    if "joint_bootstrap" in dist.candidates:
        out["joint_bootstrap"] = joint_pmf(g["mu_home"].to_numpy(), g["mu_away"].to_numpy(),
                                           [pools[s]["pairs"] for s in seg],
                                           [pools["ot"]] * len(g), dist.support_max)
    return out


def run_dist(spec: DistRunSpec, root: Path, data_root: Path | None = None) -> Path:
    run_id = spec.run_id()
    existing = root / "runs" / run_id
    if verify_run(existing):
        return existing
    base, base_manifest, base_outer, base_pred = load_base_run(root, spec.base_run_id)
    dist, gate = spec.distribution, spec.gate
    inner, outer_seasons = base.folds.inner_test_seasons, base.folds.outer_test_seasons
    if not set(spec.selection_seasons) <= set(inner):
        raise DistRefused("selection seasons must be inner (tuning) seasons of the base run")

    real = base.dataset.source == "cfb_release_b"
    if real and data_root is None:
        from cfb_paths import DATA_ROOT as data_root
    sources = _sources_digest(source_paths(base.dataset, Path(data_root)), Path(data_root)) \
        if real else _sources_digest([], None)
    if json.loads(sources) != base_manifest["sources"]:
        raise DistRefused("source files differ from the ones the base run recorded")
    frame, report = load_frame(base.dataset, base.feature_set, data_root)

    model = base_outer[0].model
    usable = sorted(s for s in frame["season"].unique() if s not in base.folds.exclude_seasons)
    forecast_seasons = usable[1:]
    for target, col in (("target", "mu_total"), ("home_reg", "mu_home"), ("away_reg", "mu_away")):
        frame[col] = season_forecasts(frame, base, model, target, forecast_seasons)
    # Compare with the sealed fold results, not predictions.csv: pandas' default CSV float
    # parser is not round-trip exact in the last bit.
    sealed = pd.Series({gid: y for r in base_outer for gid, y in r.predictions})
    mine = frame.set_index("game_id")["mu_total"].reindex(sealed.index)
    if len(sealed) != len(base_pred) or not np.array_equal(sealed.to_numpy(), mine.to_numpy()):
        raise DistRefused("season-ahead forecasts do not reproduce the base run's outer predictions")
    frame["r_total"] = frame["target"] - frame["mu_total"]
    frame["r_home"] = frame["home_reg"] - frame["mu_home"]
    frame["r_away"] = frame["away_reg"] - frame["mu_away"]
    if frame["target"].max() > dist.support_max:
        raise DistRefused(f"an observed total exceeds the support {dist.support_max}")

    scores: dict[str, dict[str, pd.DataFrame]] = {"selection": {}, "outer": {}}
    tables: dict[str, list[np.ndarray]] = {c: [] for c in dist.candidates}
    extras: dict[str, list[pd.DataFrame]] = {"joint": []}
    for stage, seasons in (("selection", spec.selection_seasons), ("outer", outer_seasons)):
        parts: dict[str, list[pd.DataFrame]] = {c: [] for c in dist.candidates}
        for s in seasons:
            window = window_seasons(s, forecast_seasons, dist.window_seasons)
            if len(window) < dist.window_seasons:
                raise DistRefused(f"season {s} has only {len(window)} window seasons")
            win_rows = frame.index[frame["season"].isin(window)]
            rows = frame.index[frame["season"] == s]
            pools = _pools(frame, win_rows, dist.early_min_prior_games)
            meta = frame.loc[rows, ["game_id", "season", "week", "target"]]
            for cand, (pmf, home_win, tie) in _tables(frame, rows, pools, dist).items():
                if not np.allclose(pmf.sum(axis=1), 1.0):
                    raise DistRefused(f"{cand} rows do not sum to 1 in {s}")
                sc = score_pmf(pmf, frame.loc[rows, "target"].to_numpy(), dist.quantiles,
                               dist.interval_levels)
                sc.index = rows
                parts[cand].append(pd.concat([meta, sc], axis=1))
                if stage == "outer":
                    tables[cand].append(pmf)
                    if home_win is not None:
                        extras["joint"].append(pd.DataFrame(
                            {"game_id": meta["game_id"], "p_home_win": home_win, "p_tie": tie},
                            index=rows))
        for cand in dist.candidates:
            scores[stage][cand] = pd.concat(parts[cand])

    selection = {c: float(scores["selection"][c]["crps"].mean()) for c in dist.candidates}
    selected = min(selection, key=lambda c: (selection[c], c))
    out_scores = scores["outer"]
    gate_report = calibration_report(out_scores[selected], gate, dist.interval_levels)

    outer_rows = out_scores[dist.baseline].index
    summary = {}
    for c in dist.candidates:
        sc = out_scores[c]
        summary[c] = {
            "crps": float(sc["crps"].mean()),
            "crps_by_season": {int(s): float(v) for s, v in sc.groupby("season")["crps"].mean().items()},
            "pinball": {f"{t:g}": float(sc[f"pinball_{t:g}"].mean()) for t in dist.quantiles},
            "width_80": float((sc["q_0.9"] - sc["q_0.1"]).mean()) if {"q_0.9", "q_0.1"} <= set(sc) else None,
            "calibration": calibration_report(sc, gate, dist.interval_levels),
            "open_label": open_label_scores(np.vstack(tables[c]), frame.loc[outer_rows, "target"].to_numpy(),
                                            frame.loc[outer_rows, "market_open"].to_numpy(dtype=float))
            if "market_open" in frame else None,
        }
    diffs = {}
    for c in dist.candidates:
        if c == dist.baseline:
            continue
        both = out_scores[c][["season", "week", "crps"]].rename(columns={"crps": "a"}).assign(
            b=out_scores[dist.baseline]["crps"])
        diffs[c] = paired_diff(both, "a", "b")

    coherence = None
    if extras["joint"]:
        jt = pd.concat(extras["joint"])
        g = frame.loc[jt.index]
        decided = g["home_reg"] != g["away_reg"]
        p_reg = ((jt["p_home_win"] - 0.5 * jt["p_tie"]) / (1 - jt["p_tie"]).clip(lower=1e-12))[decided]
        o = (g.loc[decided, "home_reg"] > g.loc[decided, "away_reg"]).astype(float)
        pooled = np.vstack(tables["joint_bootstrap"]) @ np.arange(dist.support_max + 1)
        coherence = {"simulated_ot_rate": float(jt["p_tie"].mean()),
                     "observed_ot_rate": float((g["ot_points"] > 0).mean()),
                     "pooled_mean": float(pooled.mean()), "observed_mean": float(g["target"].mean()),
                     "home_win_brier_regulation": float(((p_reg - o) ** 2).mean()),
                     "regulation_decided_games": int(decided.sum())}

    # Selective prediction for the selected candidate: abstain on high predicted error.
    feats = [f for f in report.kept]
    sel = []
    for s in outer_seasons:
        window = window_seasons(s, forecast_seasons, dist.window_seasons)
        sel.append(meta_scores(frame, feats, "r_total", s, window))
    sel_score = pd.concat(sel)
    so = out_scores[selected]
    selective = aurc_vs_full(so.assign(loss=so["crps"], score=sel_score.loc[so.index]), COVERAGES)
    mpg = frame.loc[so.index, "min_prior_games"] if "min_prior_games" in frame else None
    if mpg is not None:
        kept = so[mpg >= dist.early_min_prior_games]
        selective["min_prior_games_rule"] = {"coverage": float(len(kept) / len(so)),
                                             "mean_crps": float(kept["crps"].mean())}
    selective["full_mean_crps"] = float(so["crps"].mean())

    pmf_bytes = io.BytesIO()
    np.save(pmf_bytes, np.vstack(tables[selected]).astype(np.float64), allow_pickle=False)
    base_cols = ["season", "week", "game_id", "target"] + [c for c in ("market_open",) if c in frame]
    pred = frame.loc[outer_rows, base_cols].copy()
    for c in dist.candidates:
        for k in ("mean", "sd", "pit", "crps", "q_0.1", "q_0.5", "q_0.9"):
            if k in out_scores[c]:
                pred[f"{c}__{k}"] = out_scores[c][k]
    pred["selective_score"] = sel_score.loc[outer_rows]
    scores_doc = {"selected": selected, "selection_crps": selection, "outer": summary,
                  "gate": gate_report, "paired_crps_vs_baseline": diffs, "coherence": coherence}
    manifest = {
        "run_id": run_id, "config_hash": spec.config_hash, "base_run_id": spec.base_run_id,
        "base_code_sha256": base_manifest["code_sha256"], "code_sha256": code_fingerprint(),
        "git_sha": _git("rev-parse", "--short=12", "HEAD"), "python": platform.python_version(),
        "packages": {d: metadata.version(d) for d in PACKAGES}, "sources": json.loads(sources),
        "model": model.model_dump(), "features": {"kept": report.kept, "dropped": report.dropped},
        "forecast_seasons": [int(s) for s in forecast_seasons],
        "reproduce": f"python -m models.tuning dist --spec runs/{run_id}/dist_spec.json --root <lab root>",
        "generated_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
    }
    files = {
        "dist_spec.json": spec.model_dump_json(indent=2) + "\n",
        "manifest.json": json.dumps(manifest, indent=2, sort_keys=True) + "\n",
        "pmf_outer.npy": pmf_bytes.getvalue(),
        "pmf_games.csv": pred[["game_id"]].to_csv(index=False, lineterminator="\n"),
        "predictions.csv": pred.to_csv(index=False, lineterminator="\n"),
        "scores.json": json.dumps(scores_doc, indent=2, sort_keys=True, default=str) + "\n",
        "selective.json": json.dumps(selective, indent=2, sort_keys=True) + "\n",
        "card.md": render_dist_card(spec, manifest, scores_doc, selective),
    }
    return publish_run(root, run_id, files)

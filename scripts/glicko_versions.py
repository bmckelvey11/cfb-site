"""Version registry for the Glicko margin rating: every model the family has shipped or tested.

    python -m scripts.glicko_versions                 # list versions
    python -m scripts.glicko_versions --show P3-A     # one version in full
    python -m scripts.glicko_versions --check         # recompute stored fingerprints (needs CFB_DATA_ROOT)

A version is a name for one exact model: its class, its parameters, its forecast SD and the
game set it rates. `CURRENT` is what the ratings table publishes by default. Frozen versions
carry the fingerprint their freeze recorded, sha256 over (game_id, forecast mean, forecast SD)
on a fixed game set, so `--check` proves the code still reproduces the frozen model. Parameters
of the P3 bundles are read from their frozen files, never copied here. The changelog that
explains each version is docs/glicko-versions.md.

Status: adopted (in use), current (the published default), candidate (built and frozen,
waiting for its holdout), declared (specified, not frozen yet), rejected, retired.
"""
from __future__ import annotations

import argparse
import json
from dataclasses import dataclass, field
from pathlib import Path

from scripts.glicko_ratings import FROZEN_P1, FROZEN_V1, SIGMA_PRED_P1, GlickoMargin

SCRIPTS = Path(__file__).parent
P3_FROZEN = SCRIPTS / "glicko_p3_frozen.json"
P3D_FROZEN = SCRIPTS / "glicko_p3d_frozen.json"
P1_FROZEN = SCRIPTS / "glicko_p1_frozen.json"
P2_PICK = {"b_rp": 3.0, "b_rec": 1.5, "c": 0.0, "w": 0.7, "clip": 2.5}   # docs/glicko-p2-2026-10-15.md


@dataclass(frozen=True)
class Version:
    name: str
    status: str
    date: str                     # date adopted / frozen / rejected
    model: str                    # class name
    params: dict = field(default_factory=dict)
    sigma_pred: float | None = None   # forecast SD noise term; None = the gain sigma (P1's S)
    game_set: str = "pool"        # pool: every completed D-I game (P1+); lined: games.csv (v1)
    doc: str = ""
    frozen_file: str | None = None
    note: str = ""

    @property
    def stamp(self) -> str:
        """What the ratings table writes in its version column."""
        return f"{self.name}/1.0"


def _p3(bundle: str) -> dict:
    if not P3_FROZEN.exists():
        return {}
    b = json.loads(P3_FROZEN.read_text())["bundles"].get(bundle)
    return {} if b is None else {"params": b["pick"], "sigma_pred": b["sigma_pred"]}


def _p3d() -> dict:
    if not P3D_FROZEN.exists():
        return {}
    f = json.loads(P3D_FROZEN.read_text())
    return {"params": f["pick"], "sigma_pred": f["sigma_pred"], "status": "candidate",
            "date": f["frozen_at"][:10]}


def registry() -> dict[str, Version]:
    p3 = {b: _p3(b) for b in "ABC"}
    d = _p3d()
    vs = [
        Version("v1", "retired", "2026-09-24", "GlickoMargin", dict(FROZEN_V1), None, "lined",
                "docs/glicko-ratings-2026-09-24.md", None,
                "Rated only games with a betting line (games.csv). Superseded by P1."),
        Version("P1", "adopted", "2026-09-24", "GlickoMargin", dict(FROZEN_P1), None, "pool",
                "docs/glicko-pool-2026-09-24.md", "scripts/glicko_p1_frozen.json",
                "Every completed D-I game; offseason pull to the conference mean. Sealed 2026 "
                "confirmation reads its encompassing slope once."),
        Version("P1.1", "current", "2026-10-15", "GlickoMargin", dict(FROZEN_P1), SIGMA_PRED_P1, "pool",
                "docs/glicko-p2-2026-10-15.md", None,
                "P1's ratings and ranks unchanged; forecast SD uses sigma_pred 13.5 (gain keeps 15)."),
        Version("P2", "rejected", "2026-10-15", "GlickoPrior", dict(P2_PICK), None, "pool",
                "docs/glicko-p2-2026-10-15.md", None,
                "Returning production + recruiting prior and innovation clip; worse on 2021-25 and "
                "2026 wk 1-7."),
        *[Version(f"P3-{b}", "candidate" if p3[b] else "declared", "2026-10-17",
                  {"A": "GlickoFull", "B": "GlickoStart", "C": "GlickoContext"}[b],
                  p3[b].get("params", {}), p3[b].get("sigma_pred"), "pool",
                  "docs/superpowers/specs/2026-10-16-glicko-p3-bundles-design.md",
                  "scripts/glicko_p3_frozen.json" if p3[b] else None,
                  {"A": "Carries team covariance within a season (schedule strength).",
                   "B": "New-conference target, 3-season history, transfer-aware returning production.",
                   "C": "Home-edge trend + 2020 value, OT as a tie, game-type noise, neutral-site "
                        "proximity, time zones."}[b]) for b in "ABC"],
        Version("P3-D", d.get("status", "declared"), d.get("date", "2026-10-17"), "GlickoShrinkX",
                d.get("params", {}), d.get("sigma_pred"), "pool",
                "docs/superpowers/specs/2026-10-17-glicko-p3d-fcs-design.md",
                "scripts/glicko_p3d_frozen.json" if d else None,
                "FBS-vs-FCS expected margin shrunk by (1 - lam)."),
    ]
    return {v.name: v for v in vs}


REGISTRY = registry()
CURRENT = "P1.1"


def get(name: str = CURRENT) -> Version:
    if name not in REGISTRY:
        raise KeyError(f"unknown Glicko version {name!r}; known: {', '.join(REGISTRY)}")
    return REGISTRY[name]


def build(name: str, m0: float, data: dict | None = None):
    """(model, runner) for a pool-set version. `data` supplies features/context for B and C:
    {"feats": ..., "ctx": ...} as built by scripts.glicko_p3_eval.load."""
    from scripts.glicko_p3 import GlickoContext, GlickoFull, GlickoShrinkX, GlickoStart, run_ctx
    from scripts.glicko_ratings import run

    v = get(name)
    if v.game_set != "pool":
        raise ValueError(f"{name} rates the lined game set; rebuild it with scripts.glicko_ratings_eval")
    if v.status == "declared":
        raise ValueError(f"{name} is declared but not frozen yet")
    p = dict(v.params)
    if v.model == "GlickoMargin":
        return GlickoMargin(**FROZEN_P1, m0=m0), run
    if v.model == "GlickoFull":
        return GlickoFull(**{**FROZEN_P1, **p}, m0=m0), run
    if v.model == "GlickoStart":
        w = p.pop("w", FROZEN_P1["w"])
        return GlickoStart(**{**FROZEN_P1, "w": w}, m0=m0, new_conf=True, feats=data["feats"], **p), run
    if v.model == "GlickoContext":
        return GlickoContext(**FROZEN_P1, m0=m0, ctx=data["ctx"], ot_tie=True, near=True, **p), run_ctx
    if v.model == "GlickoShrinkX":
        return GlickoShrinkX(**FROZEN_P1, m0=m0, **p), run
    if v.model == "GlickoPrior":
        raise ValueError("P2 (rejected) is rebuilt only by scripts.glicko_p2_eval")
    raise ValueError(v.model)


def check(root: Path) -> dict[str, bool]:
    """Recompute every stored fingerprint the data allows. True = still reproduces its freeze."""
    out: dict[str, bool] = {}
    if P1_FROZEN.exists():
        from scripts.glicko_p1_confirm import p1_primary_fingerprint
        fp, _ = p1_primary_fingerprint(root)
        out["P1"] = fp == json.loads(P1_FROZEN.read_text())["primary_forecast_fingerprint"]
    if P3_FROZEN.exists():
        import scripts.glicko_p3_eval as e3
        d = e3.load(root, max(e3.DESCRIBE))
        for b, r in json.loads(P3_FROZEN.read_text())["bundles"].items():
            out[f"P3-{b}"] = e3.fingerprint(d, b, r["pick"], r["sigma_pred"])[0] == r["fingerprint"]
    if P3D_FROZEN.exists():
        import scripts.glicko_p3d_eval as ed
        f = json.loads(P3D_FROZEN.read_text())
        out["P3-D"] = ed.fingerprint(ed.load(root, max(ed.DESCRIBE)), f["pick"]["lam"], f["sigma_pred"])[0] == f["fingerprint"]
    return out


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--show")
    ap.add_argument("--check", action="store_true")
    args = ap.parse_args(argv)
    if args.check:
        from cfb_paths import DATA_ROOT
        res = check(DATA_ROOT)
        for k, ok in res.items():
            print(f"{k:<6} {'reproduces its freeze' if ok else 'FINGERPRINT CHANGED'}")
        return 0 if all(res.values()) else 1
    if args.show:
        print(json.dumps(get(args.show).__dict__, indent=2, default=str))
        return 0
    print(f"{'version':<8} {'status':<10} {'date':<11} {'model':<14} {'sigma_pred':<10} params")
    for v in REGISTRY.values():
        mark = "  <- CURRENT" if v.name == CURRENT else ""
        sp = "-" if v.sigma_pred is None else v.sigma_pred
        print(f"{v.name:<8} {v.status:<10} {v.date:<11} {v.model:<14} {str(sp):<10} "
              f"{json.dumps(v.params, default=str)}{mark}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

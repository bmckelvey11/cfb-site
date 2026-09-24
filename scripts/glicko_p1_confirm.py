"""Freeze rung P1's Glicko-margin pick and read its encompassing slope on 2026, once.

    python -m scripts.glicko_p1_confirm freeze                    # run once, now
    python -m scripts.glicko_p1_confirm confirm --season 2026     # interim until the season ends

P1's G2 pass (docs/glicko-pool-2026-09-24.md) was a second look at 2021-2025, already scored
once for v1. This freezes the exact adopted configuration so nothing about it can drift, then
reads the encompassing slope against the Bovada open on 2026 exactly once -- only after no
FBS-vs-FBS regular-season 2026 game remains scheduled (season_look, reused from
weekly_prior_scale.py unchanged). Any earlier run is interim: printed and written for
visibility, but it carries no verdict.

Writes data/processed/ratings/glicko_p1_confirm_<season>_<look>.json.
See docs/superpowers/specs/2026-09-24-glicko-p1-2026-confirmation-design.md.
"""
from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path

import pandas as pd

import scripts.glicko_ratings_eval as v1
from scripts.glicko_pool_eval import fcs_seed_pool, load_pool_games, pool_forecast
from scripts.glicko_ratings import FROZEN_P1, VERSION, events
from scripts.pregame_replay_audit import _sha256
from scripts.weekly_prior_scale import season_look, write_freeze

FROZEN = Path(__file__).with_name("glicko_p1_frozen.json")
CODE = ("glicko_ratings.py", "glicko_pool_eval.py", "glicko_ratings_eval.py",
        "glicko_p1_confirm.py")


def run_freeze() -> tuple[dict, Path]:
    frozen = {
        "candidate": "glicko_p1", "variant": "pool_conf",
        "frozen_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "design": "docs/superpowers/specs/2026-09-24-glicko-p1-2026-confirmation-design.md",
        "source_scoring_run": "docs/glicko-pool-2026-09-24.md",
        "params": FROZEN_P1, "glicko_ratings_version": VERSION,
        "code_sha256": {p: _sha256(Path(__file__).parent / p) for p in CODE},
    }
    write_freeze(FROZEN, frozen)
    return frozen, FROZEN


def confirm(season: int, frozen_path: Path = FROZEN) -> dict:
    if not frozen_path.exists():
        raise SystemExit(f"no frozen candidate at {frozen_path}: run `freeze` and commit it first")
    fz = json.loads(frozen_path.read_text(encoding="utf-8"))

    from cfb_paths import DATA_ROOT, PROCESSED

    sources: list[Path] = [frozen_path]
    schedule_path = DATA_ROOT / "raw" / f"games_{season}.json"
    sources.append(schedule_path)
    schedule = json.loads(schedule_path.read_text(encoding="utf-8"))
    look, schedule_state = season_look(schedule, pd.Timestamp.now(tz="UTC"))

    g_pool, drops = load_pool_games(DATA_ROOT, season, sources)
    m0 = fcs_seed_pool(g_pool)
    hist = g_pool[g_pool["season"] <= season].reset_index(drop=True)
    fc = pool_forecast(hist, events(hist), m0, fz["params"])

    market = v1.load_market(DATA_ROOT, [season], sources)
    d = hist.merge(fc, on="game_id", how="left").merge(market, on="game_id", how="left")
    d = d[(d["season"] == season) & (d["season_type"] == "regular")]
    d["fbs_fbs"] = (d["home_div"] == "fbs") & (d["away_div"] == "fbs")
    primary = d[d["fbs_fbs"] & d["open"].notna()].copy()
    primary["glk"], primary["glk_sd"] = primary["f"], primary["f_sd"]
    # The open's sd for CRPS: its own in-sample RMSE on this population -- its best case, the
    # same convention P1's own scoring used (docs/glicko-pool-2026-09-24.md's market note).
    if len(primary):
        primary["open_sd"] = float(((primary["open"] - primary["margin"]) ** 2).mean() ** 0.5)

    result = {
        "candidate": "glicko_p1", "season": season, "look": look,
        "schedule_state": schedule_state,
        "generated_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "frozen_at": fz["frozen_at"], "code_sha256_at_freeze": fz["code_sha256"],
        "code_sha256_now": {p: _sha256(Path(__file__).parent / p) for p in CODE},
        "primary_n": int(len(primary)),
        "primary_n_clusters": int(primary.groupby("week").ngroups) if len(primary) else 0,
        "open_sd_in_sample": float(primary["open_sd"].iloc[0]) if len(primary) else None,
    }
    if len(primary) >= 2 and primary["week"].nunique() >= 2:
        result["encompassing_vs_open"] = v1.encompassing(primary, "glk")
        result["margin_vs_open"] = {
            "mae": v1.paired(primary, "glk", "open", "mae"),
            "crps": v1.paired(primary, "glk", "open", "crps"),
        }
    else:
        result["encompassing_vs_open"] = None
        result["note"] = "too few primary games/clusters this season to fit a slope"

    if look == "final" and result["encompassing_vs_open"] is not None:
        lo = result["encompassing_vs_open"]["ci95"][0]
        result["verdict"] = "confirmed" if lo > 0 else "not confirmed"
    # An interim result never gets a "verdict" key: nothing is decided from it.

    out_dir = PROCESSED / "ratings"
    out_dir.mkdir(parents=True, exist_ok=True)
    out = out_dir / f"glicko_p1_confirm_{season}_{look}.json"
    result["source_files"] = [{"path": str(p), "sha256": _sha256(p)} for p in dict.fromkeys(sources)]
    out.write_text(json.dumps(result, indent=2, default=str) + "\n", encoding="utf-8")
    result["_out"] = str(out)
    return result


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    sub = ap.add_subparsers(dest="cmd", required=True)
    sub.add_parser("freeze")
    p_confirm = sub.add_parser("confirm")
    p_confirm.add_argument("--season", type=int, required=True)
    args = ap.parse_args(argv)

    if args.cmd == "freeze":
        frozen, path = run_freeze()
        print(f"froze {frozen['candidate']}/{frozen['variant']}: {frozen['params']}\nwrote {path}")
        return 0

    result = confirm(args.season, FROZEN)
    print(f"season {result['season']}: look={result['look']} "
          f"({result['schedule_state']}) primary_n={result['primary_n']} "
          f"clusters={result['primary_n_clusters']}")
    if result["encompassing_vs_open"] is not None:
        enc = result["encompassing_vs_open"]
        print(f"encompassing beta={enc['beta']} ci95={enc['ci95']}")
    if "verdict" in result:
        print(f"VERDICT: {result['verdict']}")
    else:
        print("no verdict (interim look -- nothing decided)")
    print(f"wrote {result['_out']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

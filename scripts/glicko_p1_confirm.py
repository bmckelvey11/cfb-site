"""Freeze rung P1's Glicko-margin pick and read its encompassing slope on 2026, once.

    python -m scripts.glicko_p1_confirm freeze                    # run once, now
    python -m scripts.glicko_p1_confirm confirm --season 2026     # interim until the season ends

P1's G2 pass (docs/glicko-pool-2026-09-24.md) was a second look at 2021-2025, already scored
once for v1. This freezes the exact adopted configuration -- and a fingerprint of the exact
forecasts it produces on P1's own 2021-2025 primary population -- so later edits to the pool
or model code cannot silently change what "the frozen candidate" means. It then reads the
encompassing slope against the Bovada open on 2026 exactly once -- only after no FBS-vs-FBS
regular-season 2026 game remains scheduled (season_look, reused from weekly_prior_scale.py
unchanged). Any earlier run is interim: printed and written for visibility, but it carries no
verdict. The fingerprint carries no 2021-2025 outcome -- game_id, forecast mean, forecast sd
-- so recomputing it is not a further look at those seasons' results.

Writes data/processed/ratings/glicko_p1_confirm_<season>_interim_<date>.json for an interim
look, or glicko_p1_confirm_<season>_final.json once, for the final one.
See docs/superpowers/specs/2026-09-24-glicko-p1-2026-confirmation-design.md.
"""
from __future__ import annotations

import argparse
import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path

import pandas as pd

import scripts.glicko_ratings_eval as v1
from scripts.glicko_pool_eval import (
    fcs_seed_pool, load_pool_games, load_v1_reference, pool_forecast,
)
from scripts.glicko_ratings import FROZEN_P1, VERSION, events
from scripts.pregame_replay_audit import _sha256
from scripts.weekly_prior_scale import season_look, write_freeze

FROZEN = Path(__file__).with_name("glicko_p1_frozen.json")
CODE = ("glicko_ratings.py", "glicko_pool_eval.py", "glicko_ratings_eval.py",
        "glicko_p1_confirm.py")
SOURCE_COMMITS = ["c28745e8", "0e2e0373"]


def p1_primary_fingerprint(data_root: Path) -> tuple[str, int]:
    """sha256 of (game_id, forecast mean, forecast sd) for P1's own 2021-2025 primary games,
    rounded to 6 decimals. Reproduced fresh from the pool/model code each call, so a change to
    either -- even one that leaves this confirm script untouched -- is caught. No outcome
    (margin, open, result) enters it: recomputing it is not a further read of those seasons.
    """
    sources: list[Path] = []
    d_v1, _, score_seasons = load_v1_reference(data_root, sources)
    g_pool, _ = load_pool_games(data_root, max(score_seasons), sources)
    m0 = fcs_seed_pool(g_pool)
    hist = g_pool[g_pool["season"] <= max(score_seasons)].reset_index(drop=True)
    fc = pool_forecast(hist, events(hist), m0, FROZEN_P1)
    d = d_v1.merge(fc, on="game_id", how="left")
    primary = d[d["primary"]][["game_id", "f", "f_sd"]].sort_values("game_id")
    rows = [f"{int(gid)},{mhat:.6f},{sd:.6f}" for gid, mhat, sd in primary.itertuples(index=False)]
    return hashlib.sha256("\n".join(rows).encode()).hexdigest(), len(rows)


def _verdict(look: str, encompassing: dict | None, fingerprint_ok: bool) -> str | None:
    """None unless `look` is 'final' and the fingerprint still matches; never decided early."""
    if look != "final" or encompassing is None or not fingerprint_ok:
        return None
    return "confirmed" if encompassing["ci95"][0] > 0 else "not confirmed"


def run_freeze() -> tuple[dict, Path]:
    from cfb_paths import DATA_ROOT

    fp_hash, fp_n = p1_primary_fingerprint(DATA_ROOT)
    frozen = {
        "candidate": "glicko_p1", "variant": "pool_conf",
        "frozen_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "design": "docs/superpowers/specs/2026-09-24-glicko-p1-2026-confirmation-design.md",
        "source_scoring_run": "docs/glicko-pool-2026-09-24.md",
        "source_commits": SOURCE_COMMITS,
        "params": FROZEN_P1, "glicko_ratings_version": VERSION,
        "primary_forecast_fingerprint": fp_hash, "primary_forecast_n": fp_n,
        "code_sha256": {p: _sha256(Path(__file__).parent / p) for p in CODE},
    }
    write_freeze(FROZEN, frozen)
    return frozen, FROZEN


def _out_path(out_dir: Path, season: int, look: str) -> Path:
    if look == "final":
        return out_dir / f"glicko_p1_confirm_{season}_final.json"
    stamp = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    return out_dir / f"glicko_p1_confirm_{season}_interim_{stamp}.json"


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

    out_dir = PROCESSED / "ratings"
    out_dir.mkdir(parents=True, exist_ok=True)
    out = _out_path(out_dir, season, look)
    if look == "final" and out.exists():
        raise SystemExit(f"{out} already holds a final confirmation; it is not rewritten")

    fp_hash, fp_n = p1_primary_fingerprint(DATA_ROOT)
    fingerprint_ok = fp_hash == fz.get("primary_forecast_fingerprint")

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
        "frozen_at": fz["frozen_at"], "source_commits": fz.get("source_commits"),
        "fingerprint_check": {"ok": fingerprint_ok, "frozen": fz.get("primary_forecast_fingerprint"),
                              "now": fp_hash, "n_frozen": fz.get("primary_forecast_n"), "n_now": fp_n},
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

    verdict = _verdict(look, result["encompassing_vs_open"], fingerprint_ok)
    if verdict is not None:
        result["verdict"] = verdict
    elif look == "final" and not fingerprint_ok:
        result["verdict_blocked_reason"] = ("P1's 2021-2025 forecast fingerprint no longer "
                                            "matches the freeze; re-freeze and re-approve before "
                                            "reading a verdict")
    # Otherwise (interim), no "verdict" key at all: nothing is decided from it.

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
        print(f"froze {frozen['candidate']}/{frozen['variant']}: {frozen['params']}\n"
              f"fingerprint {frozen['primary_forecast_fingerprint'][:12]} "
              f"over {frozen['primary_forecast_n']} games\nwrote {path}")
        return 0

    result = confirm(args.season, FROZEN)
    print(f"season {result['season']}: look={result['look']} "
          f"({result['schedule_state']}) primary_n={result['primary_n']} "
          f"clusters={result['primary_n_clusters']} "
          f"fingerprint_ok={result['fingerprint_check']['ok']}")
    if result["encompassing_vs_open"] is not None:
        enc = result["encompassing_vs_open"]
        print(f"encompassing beta={enc['beta']} ci95={enc['ci95']}")
    if "verdict" in result:
        print(f"VERDICT: {result['verdict']}")
    elif "verdict_blocked_reason" in result:
        print(f"VERDICT BLOCKED: {result['verdict_blocked_reason']}")
    else:
        print("no verdict (interim look -- nothing decided)")
    print(f"wrote {result['_out']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

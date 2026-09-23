"""Release F1: team ratings that drift week to week (a Kalman filter) against `ridge_v1`.

    python -m scripts.weekly_dynamic tune                   # 2014-2019; reproduction
    python -m scripts.weekly_dynamic tune --freeze          # first time only; never overwrites
    python -m scripts.weekly_dynamic screen                 # 2021-2025, descriptive
    python -m scripts.weekly_dynamic screen --record        # first time only: writes the gate
    python -m scripts.weekly_dynamic confirm --season 2026  # one look, after the regular season

Release B's two components keep their form, but each team's offense, defense, and pace
follow a random walk between weeks. Each season starts at league average with prior
variance 1/lambda (no carryover), so with zero drift the filter is `ridge_v1` exactly and
the tuning decides only whether drift helps. `decay_v1`, an exponentially weighted ridge at
the same lambda, is the second baseline. Rules, stop rules, and the power limit:
docs/superpowers/specs/2026-09-23-tuning-lab-release-f-dynamic-ratings-design.md.
"""
from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
import pandas as pd

from scripts.pregame_replay_audit import _sha256
from scripts.weekly_prior_scale import season_look, write_freeze
from scripts.weekly_ratings import Ratings, _solve, _team_rows, fit_set, forecast_total
from scripts.weekly_ratings_eval import (
    BOOT_DRAWS, BOOT_SEED, MIN_PRIOR_GAMES, OPEN_PROVIDER, Z_MDE, accuracy, classify_verdict,
    load, load_opens, paired_mae_diff, run_season, week_cutoffs,
)

FROZEN = Path(__file__).with_name("weekly_dynamic_v1.json")
GATE = Path(__file__).with_name("weekly_dynamic_v1_screen.json")
DESIGN = "docs/superpowers/specs/2026-09-23-tuning-lab-release-f-dynamic-ratings-design.md"
RIDGE_V1 = (40, 8)
FLAT = 1e-6                                   # prior precision of mu, h, nu: near-flat
Q_PPP = (0.0, 1e-4, 3e-4, 1e-3, 3e-3, 1e-2)   # weekly drift variance / sigma^2
Q_PACE = (0.0, 5e-4, 1.5e-3, 5e-3, 1.5e-2, 5e-2)
DECAY = (1.0, 0.98, 0.95, 0.9, 0.85, 0.8)     # weight per week of age
Q_STRESS = (0.5, 2.0)
TUNE = list(range(2014, 2020))
SCREEN = list(range(2021, 2026))
CONFIRM_FROM_WEEK = 9
CODE = ("weekly_dynamic.py", "weekly_ratings.py", "weekly_ratings_eval.py")


# --- model -----------------------------------------------------------------------

def _filter(x: np.ndarray, y: np.ndarray, w: np.ndarray, week: np.ndarray,
            prior_prec: np.ndarray, drift: np.ndarray) -> np.ndarray:
    """Posterior mean after a forward Kalman filter over week batches (information form).

    Before each week after the first, the drift variance is added once per week step; then
    that week's observations (variance 1/w) are folded in. With zero drift this is the
    ridge solution (X'WX + diag(prior_prec)) b = X'Wy.
    """
    prec, info, prev = np.diag(prior_prec.astype(float)), np.zeros(x.shape[1]), None
    for t in np.unique(week):
        if prev is not None and drift.any():
            cov = np.linalg.inv(prec)
            mean = cov @ info
            cov[np.diag_indices_from(cov)] += drift * (t - prev)
            prec = np.linalg.inv(cov)
            info = prec @ mean
        m = week == t
        prec += x[m].T @ (x[m] * w[m, None])
        info += x[m].T @ (w[m] * y[m])
        prev = t
    return np.linalg.solve(prec, info)


def _ppp_design(games: pd.DataFrame) -> tuple[pd.DataFrame, list[str], np.ndarray, np.ndarray]:
    rows = _team_rows(games)
    teams = sorted(set(rows["team"]) | set(rows["opp"]))
    idx = {t: i for i, t in enumerate(teams)}
    k = len(teams)
    x = np.zeros((len(rows), 2 + 2 * k))
    x[:, 0] = 1.0
    x[:, 1] = rows["H"]
    x[np.arange(len(rows)), 2 + rows["team"].map(idx)] = 1.0
    x[np.arange(len(rows)), 2 + k + rows["opp"].map(idx)] = 1.0
    week = np.r_[games["week"].to_numpy(), games["week"].to_numpy()]  # _team_rows: home, then away
    return rows, teams, x, week


def _pace_design(games: pd.DataFrame) -> tuple[list[str], np.ndarray]:
    teams = sorted(set(games["home"]) | set(games["away"]))
    idx = {t: i for i, t in enumerate(teams)}
    x = np.zeros((len(games), 1 + len(teams)))
    x[:, 0] = 1.0
    x[np.arange(len(games)), 1 + games["home"].map(idx)] = 1.0
    x[np.arange(len(games)), 1 + games["away"].map(idx)] = 1.0
    return teams, x


def kalman_ppp(games: pd.DataFrame, lam: float, q: float) -> tuple[float, float, pd.DataFrame]:
    rows, teams, x, week = _ppp_design(games)
    k = len(teams)
    b = _filter(x, rows["y"].to_numpy(float), rows["w"].to_numpy(float), week,
                np.r_[FLAT, FLAT, np.full(2 * k, lam)], np.r_[0.0, 0.0, np.full(2 * k, q)])
    return b[0], b[1], pd.DataFrame({"O": b[2:2 + k], "D": b[2 + k:]}, index=teams)


def kalman_pace(games: pd.DataFrame, lam: float, q: float) -> tuple[float, pd.Series]:
    teams, x = _pace_design(games)
    b = _filter(x, games["N"].to_numpy(float), np.ones(len(games)), games["week"].to_numpy(),
                np.r_[FLAT, np.full(len(teams), lam)], np.r_[0.0, np.full(len(teams), q)])
    return b[0], pd.Series(b[1:], index=teams, name="P")


def decay_ppp(games: pd.DataFrame, lam: float, d: float, target_week: int
              ) -> tuple[float, float, pd.DataFrame]:
    """Ridge with each game weighted d^((target_week - 1) - week); the latest week weighs 1."""
    rows, teams, x, week = _ppp_design(games)
    k = len(teams)
    w = rows["w"].to_numpy(float) * d ** ((target_week - 1) - week)
    b = _solve(x, rows["y"].to_numpy(float), w, np.r_[0.0, 0.0, np.full(2 * k, lam)])
    return b[0], b[1], pd.DataFrame({"O": b[2:2 + k], "D": b[2 + k:]}, index=teams)


def decay_pace(games: pd.DataFrame, lam: float, d: float, target_week: int
               ) -> tuple[float, pd.Series]:
    teams, x = _pace_design(games)
    w = d ** ((target_week - 1) - games["week"].to_numpy())
    b = _solve(x, games["N"].to_numpy(float), w, np.r_[0.0, np.full(len(teams), lam)])
    return b[0], pd.Series(b[1:], index=teams, name="P")


def _ratings(games: pd.DataFrame, ppp: tuple, pace: tuple) -> Ratings:
    mu, h, od = ppp
    nu, p = pace
    return Ratings(mu=float(mu), nu=float(nu), h=float(h), c=float(games["ot"].mean()),
                   table=od.join(p, how="outer"), unrated=0.0)


def fit_kalman(games: pd.DataFrame, lam_ppp: float, lam_pace: float, q_ppp: float,
               q_pace: float) -> Ratings:
    return _ratings(games, kalman_ppp(games, lam_ppp, q_ppp), kalman_pace(games, lam_pace, q_pace))


def fit_decay(games: pd.DataFrame, lam_ppp: float, lam_pace: float, d_ppp: float,
              d_pace: float, target_week: int) -> Ratings:
    return _ratings(games, decay_ppp(games, lam_ppp, d_ppp, target_week),
                    decay_pace(games, lam_pace, d_pace, target_week))


# --- tuning ------------------------------------------------------------------------

def tune(games: pd.DataFrame, seasons: list[int]) -> dict:
    """Release B's one-step-ahead component loss for every drift and decay grid point."""
    loss = {("kalman", "ppp"): dict.fromkeys(Q_PPP, 0.0), ("kalman", "pace"): dict.fromkeys(Q_PACE, 0.0),
            ("decay", "ppp"): dict.fromkeys(DECAY, 0.0), ("decay", "pace"): dict.fromkeys(DECAY, 0.0)}
    n_cutoffs = 0
    for s in seasons:
        sg = games[games["season"] == s]
        for week, cut in week_cutoffs(sg).items():
            fs = fit_set(sg, cut)
            target = sg[(sg["week"] == week) & ~sg["gated"]]
            if fs.empty or target.empty:
                continue
            n_cutoffs += 1
            rows = _team_rows(target)

            def ppp_loss(fit) -> float:
                mu, h, od = fit
                pred = (mu + rows["team"].map(od["O"]).fillna(0)
                        + rows["opp"].map(od["D"]).fillna(0) + h * rows["H"])
                return float((rows["w"] * (rows["y"] - pred) ** 2).sum())

            def pace_loss(fit) -> float:
                nu, p = fit
                pred = nu + target["home"].map(p).fillna(0) + target["away"].map(p).fillna(0)
                return float(((target["N"] - pred) ** 2).sum())

            for q in Q_PPP:
                loss[("kalman", "ppp")][q] += ppp_loss(kalman_ppp(fs, RIDGE_V1[0], q))
            for q in Q_PACE:
                loss[("kalman", "pace")][q] += pace_loss(kalman_pace(fs, RIDGE_V1[1], q))
            for d in DECAY:
                loss[("decay", "ppp")][d] += ppp_loss(decay_ppp(fs, RIDGE_V1[0], d, week))
                loss[("decay", "pace")][d] += pace_loss(decay_pace(fs, RIDGE_V1[1], d, week))

    def pick(losses: dict) -> dict:
        grid = list(losses)
        best = min(grid, key=losses.get)  # ties go to the earlier grid point: no drift, no decay
        return {"value": best, "loss_by_value": {f"{k:g}": round(v, 4) for k, v in losses.items()},
                "pick_on_grid_boundary": best in (grid[0], grid[-1])}

    return {"seasons": seasons, "n_cutoffs": n_cutoffs,
            **{f"{m}_{c}": pick(v) for (m, c), v in loss.items()}}


def run_tune(freeze: bool = False) -> tuple[dict, Path]:
    from cfb_paths import DATA_ROOT, PROCESSED

    sources: list[Path] = []
    games, _ = load(DATA_ROOT, TUNE, sources)
    t = tune(games, TUNE)
    frozen = {
        "candidate": "kalman_v1", "design": DESIGN,
        "frozen_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "tune_seasons": TUNE, "ridge_v1_lambda": list(RIDGE_V1),
        "q_ppp": t["kalman_ppp"]["value"], "q_pace": t["kalman_pace"]["value"],
        "decay_ppp": t["decay_ppp"]["value"], "decay_pace": t["decay_pace"]["value"],
        "trial_count": {"grid_points": 2 * len(Q_PPP) + 2 * len(DECAY)},
        "tuning": t,
        "code_sha256": {p: _sha256(Path(__file__).parent / p) for p in CODE},
        "source_files": [{"path": str(p), "sha256": _sha256(p)} for p in dict.fromkeys(sources)],
    }
    if freeze:
        write_freeze(FROZEN, frozen)
        return frozen, FROZEN
    path = PROCESSED / "ratings" / "weekly_dynamic_tune.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(frozen, indent=2) + "\n", encoding="utf-8")
    return frozen, path


# --- forecasts ----------------------------------------------------------------------

def dynamic_forecasts(games: pd.DataFrame, season: int, fz: dict, stress: bool) -> pd.DataFrame:
    """`kalman` (and its drift stress) and `decay` for every week-2+ game of `season`."""
    lam = fz["ridge_v1_lambda"]
    variants = {"kalman": 1.0, **({f"kalman_q{k:g}": k for k in Q_STRESS} if stress else {})}
    sg = games[games["season"] == season]
    rows = []
    for week, cut in week_cutoffs(sg).items():
        fs = fit_set(sg, cut)
        if fs.empty:
            continue
        fits = {name: fit_kalman(fs, *lam, fz["q_ppp"] * m, fz["q_pace"] * m)
                for name, m in variants.items()}
        fits["decay"] = fit_decay(fs, *lam, fz["decay_ppp"], fz["decay_pace"], week)
        for g in sg[sg["week"] == week].itertuples():
            rows.append({"game_id": g.game_id, **{n: forecast_total(r, g.home, g.away, g.neutral)
                                                  for n, r in fits.items()}})
    return pd.DataFrame(rows)


def _load_frozen(path: Path) -> dict:
    if not path.exists():
        raise SystemExit(f"no frozen candidate at {path}: run `tune --freeze` and commit it first")
    fz = json.loads(path.read_text(encoding="utf-8"))
    if fz["q_ppp"] == 0 and fz["q_pace"] == 0:
        raise SystemExit("zero drift won both components: there is no dynamic candidate (stop rule 1)")
    return fz


def _verdict(pop: pd.DataFrame, a: str, b: str) -> dict:
    p = paired_mae_diff(pop, a, b)
    return {**p, "verdict": classify_verdict(*p["ci95"], list(p["by_season"].values()))}


# --- screen ----------------------------------------------------------------------------

def screen(record: bool = False, frozen_path: Path = FROZEN, gate_path: Path = GATE) -> dict:
    fz = _load_frozen(frozen_path)
    from cfb_paths import DATA_ROOT, PROCESSED

    sources: list[Path] = [frozen_path]
    games, _ = load(DATA_ROOT, list(range(2014, max(SCREEN) + 1)), sources)
    opens = load_opens(DATA_ROOT, SCREEN, sources)
    parts = []
    for s in SCREEN:
        base, _ = run_season(games, s, *fz["ridge_v1_lambda"], opens)
        parts.append(base.merge(dynamic_forecasts(games, s, fz, stress=True), on="game_id"))
    scored = pd.concat(parts, ignore_index=True)
    has_open = scored["open"].notna()
    primary = scored[has_open & (scored["min_prior_games"] >= MIN_PRIOR_GAMES)]
    early = scored[has_open & (scored["min_prior_games"] < MIN_PRIOR_GAMES)]

    main = _verdict(primary, "kalman", "ridge")
    stress = {f"q_x{k:g}": _verdict(primary, f"kalman_q{k:g}", "ridge")["verdict"] for k in Q_STRESS}
    vs_half = paired_mae_diff(primary, "kalman", "ridge_x0.5")
    # Power for the confirmation: the cluster bootstrap's SE scales with 1/sqrt(clusters).
    last = primary[primary["season"] == max(SCREEN)]
    w9 = last[last["week"] >= CONFIRM_FROM_WEEK]
    se_proj = main["se"] * np.sqrt(main["n_clusters"] / max(w9["week"].nunique(), 1))
    gate = {"kalman_vs_ridge_v1": main["verdict"], "kalman_vs_ridge_x0.5_diff": vs_half["diff"],
            "pass": main["verdict"] == "improves" and vs_half["diff"] < 0}
    out = {
        "candidate": "kalman_v1", "design": DESIGN, "seasons": SCREEN,
        "note": "descriptive: 2021-2025 already served Releases B-D and the priors work",
        "generated_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "frozen": {k: fz[k] for k in ("q_ppp", "q_pace", "decay_ppp", "decay_pace", "frozen_at")},
        "frozen_sha256": _sha256(frozen_path),
        "populations": {"primary": int(len(primary)), "early": int(len(early))},
        "primary": {
            "accuracy": accuracy(primary, ["open", "ridge", "ridge_x0.5", "decay", "kalman"]),
            "kalman_vs_ridge_v1": {**main, "stable_under_stress": all(v == main["verdict"]
                                                                      for v in stress.values()),
                                   "stress_verdicts": stress},
            "kalman_vs_ridge_x0.5": vs_half,
            "kalman_vs_decay": _verdict(primary, "kalman", "decay"),
            "decay_vs_ridge_v1": _verdict(primary, "decay", "ridge"),
            "kalman_vs_open": paired_mae_diff(primary, "kalman", "open"),
        },
        "early": {"accuracy": accuracy(early, ["open", "ridge", "decay", "kalman"]),
                  "kalman_vs_ridge_v1": paired_mae_diff(early, "kalman", "ridge")},
        "confirmation_power": {"games_2025_w9plus": int(len(w9)),
                               "clusters_2025_w9plus": int(w9["week"].nunique()),
                               "mde80_projected": round(float(Z_MDE * se_proj), 4)},
        "gate": gate,
        "bootstrap": {"unit": "season-week", "draws": BOOT_DRAWS, "seed": BOOT_SEED},
        "market": {"provider": OPEN_PROVIDER, "field": "overUnderOpen"},
        "source_files": [{"path": str(p), "sha256": _sha256(p)} for p in dict.fromkeys(sources)],
    }
    path = PROCESSED / "ratings" / "weekly_dynamic_screen.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(out, indent=2, default=str) + "\n", encoding="utf-8")
    out["path"] = str(path)
    if record:
        write_freeze(gate_path, {k: out[k] for k in ("candidate", "generated_at", "frozen_sha256",
                                                     "populations", "confirmation_power", "gate")}
                     | {"kalman_vs_ridge_v1": {k: main[k] for k in ("diff", "ci95", "mde80",
                                                                     "by_season", "verdict")}})
    return out


# --- confirmation ----------------------------------------------------------------------

def confirm(season: int, frozen_path: Path = FROZEN, gate_path: Path = GATE,
            now: pd.Timestamp | None = None) -> dict:
    fz = _load_frozen(frozen_path)
    if not gate_path.exists():
        raise SystemExit(f"no screen gate at {gate_path}: run `screen --record` and commit it first")
    gate = json.loads(gate_path.read_text(encoding="utf-8"))
    if gate["frozen_sha256"] != _sha256(frozen_path):
        raise SystemExit("the screen gate was recorded against a different freeze")
    if not gate["gate"]["pass"]:
        raise SystemExit("the screen gate did not pass: F1 stops (stop rule 2)")

    from cfb_paths import DATA_ROOT, PROCESSED

    schedule = json.loads((DATA_ROOT / "raw" / f"games_{season}.json").read_text(encoding="utf-8"))
    look, state = season_look(schedule, now or pd.Timestamp.now(tz="UTC"))
    if look != "final":
        raise SystemExit(f"{season} is not final ({state}); the one look waits for it, no interim run")

    sources: list[Path] = [frozen_path, gate_path]
    games, _ = load(DATA_ROOT, list(range(2014, season + 1)), sources)
    opens = load_opens(DATA_ROOT, [season], sources)
    base, _ = run_season(games, season, *fz["ridge_v1_lambda"], opens)
    scored = base.merge(dynamic_forecasts(games, season, fz, stress=False), on="game_id")
    pop = scored[scored["open"].notna() & (scored["week"] >= CONFIRM_FROM_WEEK)
                 & (scored["min_prior_games"] >= MIN_PRIOR_GAMES)]
    p = paired_mae_diff(pop, "kalman", "ridge")
    verdict = classify_verdict(*p["ci95"], [p["diff"]])
    out = {
        "candidate": "kalman_v1", "season": season, "look": "final", "design": DESIGN,
        "generated_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "frozen_sha256": _sha256(frozen_path), "gate_sha256": _sha256(gate_path),
        "population": f"weeks >= {CONFIRM_FROM_WEEK}, both teams >= {MIN_PRIOR_GAMES} prior games, "
                      f"{OPEN_PROVIDER} open present",
        "kalman_vs_ridge_v1": {**p, "verdict": verdict},
        "result": {"improves": "confirmed", "matches": "unconfirmed", "worse": "failed"}[verdict],
        "accuracy": accuracy(pop, ["open", "ridge", "kalman"]),
        "kalman_vs_open": paired_mae_diff(pop, "kalman", "open"),
        "bootstrap": {"unit": "season-week", "draws": BOOT_DRAWS, "seed": BOOT_SEED},
        "source_files": [{"path": str(p), "sha256": _sha256(p)} for p in dict.fromkeys(sources)],
    }
    path = PROCESSED / "ratings" / f"kalman_v1_confirm_{season}_final.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(out, indent=2, default=str) + "\n", encoding="utf-8")
    out["path"] = str(path)
    return out


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    sub = ap.add_subparsers(dest="cmd", required=True)
    t = sub.add_parser("tune")
    t.add_argument("--freeze", action="store_true", help=f"write {FROZEN.name} (refuses if it exists)")
    s = sub.add_parser("screen")
    s.add_argument("--record", action="store_true", help=f"write {GATE.name} (refuses if it exists)")
    c = sub.add_parser("confirm")
    c.add_argument("--season", type=int, required=True)
    args = ap.parse_args(argv)
    if args.cmd == "tune":
        fz, path = run_tune(freeze=args.freeze)
        print(json.dumps({k: fz[k] for k in ("q_ppp", "q_pace", "decay_ppp", "decay_pace")}, indent=1))
        print(json.dumps({k: v for k, v in fz["tuning"].items() if k not in ("seasons",)}, indent=1))
        print(f"written: {path}" + (" -- commit it before running screen" if args.freeze else ""))
    elif args.cmd == "screen":
        out = screen(record=args.record)
        print(json.dumps({k: out[k] for k in ("populations", "primary", "confirmation_power", "gate")},
                         indent=1, default=str))
        print(f"written: {out['path']}" + (f" and {GATE}" if args.record else ""))
    else:
        out = confirm(args.season)
        print(json.dumps({k: out[k] for k in ("kalman_vs_ridge_v1", "result")}, indent=1, default=str))
        print(f"written: {out['path']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

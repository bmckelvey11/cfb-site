"""Forward CLV ledger: log a takeable total at bet-time, compare to the close.

CLV in points, from the bettor's side:
  UNDER: bet_line - close  (close dropping is good)
  OVER:  close - bet_line  (close rising is good)

Positive mean CLV means the market later agreed with the side. That is the
quantity that settles whether the backtest was real. Bovada historical opens
are not used here — only DraftKings / ESPN Bet current numbers.
"""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
import pandas as pd

from .data import DEFAULT_DATA_ROOT, _REGISTRY_COLS, _WEATHER, load
from .model import _fit_predict

TAKEABLE = ("DraftKings", "Draft Kings", "ESPN Bet")
DEFAULT_LEDGER = Path(__file__).resolve().parents[1] / "ledgers" / "totals_clv_ledger.jsonl"
MIN_EDGE = 3.0


def clv_points(side: str, bet_line: float, close: float) -> float:
    if side == "UNDER":
        return float(bet_line) - float(close)
    if side == "OVER":
        return float(close) - float(bet_line)
    raise ValueError(f"side must be OVER or UNDER, got {side!r}")


def pick_takeable(lines: list[dict]) -> tuple[float, str] | None:
    """Current over/under from a book that is actually bettable. Not Bovada."""
    rank = {p: i for i, p in enumerate(TAKEABLE)}
    found: list[tuple[int, dict]] = []
    for ln in lines or []:
        if ln.get("overUnder") is None:
            continue
        provider = ln.get("provider")
        if provider not in rank:
            continue
        found.append((rank[provider], ln))
    if not found:
        return None
    found.sort(key=lambda x: x[0])
    ln = found[0][1]
    return float(ln["overUnder"]), str(ln["provider"])


def _now() -> datetime:
    return datetime.now(timezone.utc)


def read_ledger(path: Path) -> list[dict]:
    if not path.exists():
        return []
    rows = []
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if line:
            rows.append(json.loads(line))
    return rows


def write_ledger(path: Path, rows: list[dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        "".join(json.dumps(r, sort_keys=True) + "\n" for r in rows),
        encoding="utf-8",
    )


def _features_blob(root: Path) -> dict:
    for rel in ("processed/upcoming_features.json", "processed/features.json"):
        path = root / rel
        if path.exists():
            blob = json.loads(path.read_text(encoding="utf-8"))
            games = blob.get("games", blob)
            if isinstance(games, dict) and games:
                return games
    return {}


def _live_candidates(root: Path, season: int, now: datetime) -> pd.DataFrame:
    games = json.loads((root / "raw" / f"games_{season}.json").read_text(encoding="utf-8"))
    lines_blob = json.loads((root / "raw" / f"lines_{season}.json").read_text(encoding="utf-8"))
    by_id = {int(g["id"]): g.get("lines") or [] for g in lines_blob if g.get("id") is not None}
    feats = _features_blob(root)

    rows = []
    for g in games:
        if g.get("completed") or g.get("homePoints") is not None:
            continue
        gid = g.get("id")
        start = g.get("startDate") or g.get("start_date")
        if gid is None or not start:
            continue
        kick = pd.to_datetime(start, utc=True)
        if kick <= now:
            continue
        picked = pick_takeable(by_id.get(int(gid), []))
        if picked is None:
            continue
        bet_line, provider = picked
        f = feats.get(str(int(gid))) or {}
        row = {
            "game_id": int(gid),
            "season": int(g.get("season") or season),
            "week": g.get("week"),
            "kickoff": kick.isoformat(),
            "away": g.get("awayTeam") or g.get("away_team"),
            "home": g.get("homeTeam") or g.get("home_team"),
            "bet_line": bet_line,
            "provider": provider,
            "min_n": 0.0,
        }
        for k in _REGISTRY_COLS:
            row[k] = f.get(k)
        for short, key in _WEATHER.items():
            row[short] = f.get(key)
        row["dome_i"] = {True: 1, False: 0}.get(f.get("venue_dome"))
        if row.get("homePregameElo") is None:
            row["homePregameElo"] = g.get("homePregameElo")
        if row.get("awayPregameElo") is None:
            row["awayPregameElo"] = g.get("awayPregameElo")
        for c in (
            "pace_plays", "pace_drives",
            "mm_tot_ppa", "mm_tot_succ", "mm_h_ppa", "mm_a_ppa", "mm_h_succ", "mm_a_succ",
        ):
            row[c] = np.nan
        rows.append(row)
    return pd.DataFrame(rows)


def snapshot(*, data_root: Path | str | None = None, season: int = 2026,
             ledger_path: Path | None = None, min_edge: float = MIN_EDGE,
             min_prior_games: int = 3, replace: bool = False,
             now: datetime | None = None) -> list[dict]:
    """Fit on completed history, log takeable totals for unplayed games."""
    root = Path(data_root) if data_root else DEFAULT_DATA_ROOT
    ledger_path = Path(ledger_path) if ledger_path else DEFAULT_LEDGER
    now = now or _now()

    ds = load(root, min_prior_games=min_prior_games)
    train = ds.frame.dropna(subset=["ou_open", "pts"])
    train = train[train["season"] < season]
    if len(train) < 300:
        raise RuntimeError(f"not enough train games before {season}: {len(train)}")

    live = _live_candidates(root, season, now)
    if live.empty:
        return []

    existing = {int(r["game_id"]): r for r in read_ledger(ledger_path)}
    if not replace:
        live = live[~live["game_id"].isin(existing)].copy()
    if live.empty:
        return []

    scored = live.copy()
    scored["ou_open"] = scored["bet_line"]
    for col in ds.feature_cols + ["ou_open"]:
        scored[col] = pd.to_numeric(scored[col], errors="coerce")
    scored["pred"] = _fit_predict(train, scored, ds.feature_cols, "ou_open")
    scored["edge"] = scored["bet_line"] - scored["pred"]
    scored["side"] = np.where(scored["edge"] > 0, "UNDER", "OVER")
    scored["abs_edge"] = scored["edge"].abs()

    new_rows = []
    for r in scored.itertuples(index=False):
        rec = {
            "logged_at": now.isoformat(),
            "game_id": int(r.game_id),
            "season": int(r.season),
            "week": None if pd.isna(r.week) else int(r.week),
            "kickoff": r.kickoff,
            "away": r.away,
            "home": r.home,
            "provider": r.provider,
            "bet_line": float(r.bet_line),
            "pred": round(float(r.pred), 2),
            "edge": round(float(r.edge), 2),
            "abs_edge": round(float(r.abs_edge), 2),
            "side": r.side,
            "would_bet": bool(float(r.abs_edge) >= min_edge),
            "regime": "unvalidated_early" if float(r.min_n) < min_prior_games else "validated",
            "min_n": float(r.min_n),
            "close": None,
            "close_provider": None,
            "close_at": None,
            "clv": None,
            "pts": None,
            "hit": None,
        }
        new_rows.append(rec)
        existing[rec["game_id"]] = rec

    write_ledger(ledger_path, [existing[k] for k in sorted(existing)])
    return new_rows


def refresh_closes(*, data_root: Path | str | None = None, season: int = 2026,
                   ledger_path: Path | None = None,
                   now: datetime | None = None) -> list[dict]:
    """Fill close / final points. Never overwrites bet_line."""
    root = Path(data_root) if data_root else DEFAULT_DATA_ROOT
    ledger_path = Path(ledger_path) if ledger_path else DEFAULT_LEDGER
    now = now or _now()
    rows = read_ledger(ledger_path)
    if not rows:
        return rows

    lines_blob = json.loads((root / "raw" / f"lines_{season}.json").read_text(encoding="utf-8"))
    by_id = {int(g["id"]): g.get("lines") or [] for g in lines_blob if g.get("id") is not None}
    games = json.loads((root / "raw" / f"games_{season}.json").read_text(encoding="utf-8"))
    finals = {}
    for g in games:
        gid = g.get("id")
        hp, ap = g.get("homePoints"), g.get("awayPoints")
        if gid is not None and hp is not None and ap is not None:
            finals[int(gid)] = int(hp) + int(ap)

    for rec in rows:
        if rec.get("season") != season:
            continue
        gid = int(rec["game_id"])
        picked = pick_takeable(by_id.get(gid, []))
        if rec.get("pts") is None and picked is not None:
            rec["close"] = picked[0]
            rec["close_provider"] = picked[1]
            rec["close_at"] = now.isoformat()
        if gid in finals:
            rec["pts"] = finals[gid]
        if rec.get("close") is not None:
            rec["clv"] = round(clv_points(rec["side"], rec["bet_line"], rec["close"]), 2)
        if rec.get("pts") is not None and rec.get("bet_line") is not None:
            if rec["pts"] == rec["bet_line"]:
                rec["hit"] = None
            else:
                went_under = rec["pts"] < rec["bet_line"]
                rec["hit"] = bool(went_under if rec["side"] == "UNDER" else not went_under)

    write_ledger(ledger_path, rows)
    return rows


def summarize(rows: list[dict], *, would_bet_only: bool = True) -> dict | None:
    pool = [r for r in rows if r.get("clv") is not None]
    if would_bet_only:
        pool = [r for r in pool if r.get("would_bet")]
    if not pool:
        return None
    clvs = [float(r["clv"]) for r in pool]
    hits = [r["hit"] for r in pool if r.get("hit") is not None]
    out = {
        "n": len(pool),
        "mean_clv": round(float(np.mean(clvs)), 3),
        "median_clv": round(float(np.median(clvs)), 3),
        "pct_positive": round(100 * float(np.mean([c > 0 for c in clvs])), 1),
    }
    if hits:
        out["n_graded"] = len(hits)
        out["hit_pct"] = round(100 * float(np.mean(hits)), 2)
    return out

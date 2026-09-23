"""Priced replay of a finished shadow period (Release E, task 7).

    python -m models.tuning replay --spec models/tuning/specs/replay_2026_w05_08.json
    python -m models.tuning replay --spec ... --rehearsal    # mechanics check on week 4 only

Runs only after the period's verdict is in the ledger. It prices what the ledger recorded,
never a regenerated forecast: each game's counted challenger prediction, its probability
table from the snapshot file (checksum-verified), and the Action Network history copied at
archive time (checksum-verified). Any mismatch refuses the whole replay.

Declared before any period game was played (replay spec and this code committed before
2026-10-02 00:00Z):

- **Policy and execution** are the shadow spec's, not redefined here.
- **Decision time** is the counted prediction's recorded `decision_ts` (the week cutoff),
  or the game's final kickoff if that moved earlier. Quotes are each book's last non-live,
  available tick at or before it, no older than the execution spec's maximum age. Action
  Network ticks are change events, so a price that stood unchanged for longer than that
  counts as stale: this understates availability.
- **CLV needs a proven close.** The collector stops re-pulling a settled game, so a file
  can end hours before kickoff, and its last pre-kickoff tick is then not the close. CLV
  counts only where the archived file holds some tick (live included) after the game's
  kickoff; every other bet is `close_unknown` and counted. The sensitivity table reports
  bets and units only, since it cannot apply that rule.
- **Market reference** for the proper score: at the decision time, every fresh book quoting
  both sides at the same number; take the most common number (ties go to the lower), and
  the mean multiplicative de-vigged P(over) there. The model's P(over) at that number is
  conditional on no push. Games landing on it are excluded.
- **Intervals** resample games (10,000 draws, seed 20260922). Games in one week share
  conditions, so these are too narrow; four weeks are too few for a week-cluster bootstrap.
"""
from __future__ import annotations

import json
from collections import Counter
from datetime import timedelta
from pathlib import Path
from typing import ClassVar, Literal

import numpy as np
import pandas as pd
from pydantic import Field

from models.tuning.ledger import Ledger
from models.tuning.market import (Forecast, _latest, backtest, devig, outcome_probs,
                                  quotes_from_an_ticks, sensitivity, summarize)
from models.tuning.shadow import ShadowRefused, _sha, shadow_dir
from models.tuning.shadow_spec import ShadowSpec
from models.tuning.spec import _sha256, _Spec, canonical_json
from models.tuning.worker import code_fingerprint

REPO = Path(__file__).resolve().parents[2]
FRAMING = ("Descriptive only: one pre-declared shadow period, trial count 1. Intervals "
           "resample games and ignore within-week dependence, so they are too narrow. "
           "Not evidence of an edge in either direction.")


class ReplaySpec(_Spec):
    PROVENANCE: ClassVar[frozenset[str]] = frozenset({"created_at", "created_by", "notes"})

    schema_version: Literal[1] = 1
    spec_id: str
    created_at: str
    created_by: str
    notes: str = ""
    shadow_spec: str                                   # repo-relative path
    shadow_id: str = Field(pattern=r"^shadow-[0-9a-f]{12}$")
    decision_time: Literal["week_cutoff"] = "week_cutoff"
    market_reference: Literal["modal_line_mean_devig"] = "modal_line_mean_devig"
    bootstrap_unit: Literal["game"] = "game"
    bootstrap_draws: int = 10_000
    bootstrap_seed: int = 20260922
    sensitivity_thresholds: tuple[float, ...] = (0.0, 0.01, 0.02, 0.03, 0.05, 0.08)

    @property
    def config_hash(self) -> str:
        return _sha256(canonical_json(self, exclude=self.PROVENANCE))

    def replay_id(self) -> str:
        return f"replay-{self.config_hash[:12]}"


def _boot_mean(x: np.ndarray, spec: ReplaySpec) -> dict:
    x = np.asarray(x, dtype=float)
    if x.size == 0:
        return {"n": 0, "mean": None, "ci95": None}
    rng = np.random.default_rng(spec.bootstrap_seed)
    draws = x[rng.integers(0, x.size, size=(spec.bootstrap_draws, x.size))].mean(axis=1)
    lo, hi = np.percentile(draws, [2.5, 97.5])
    return {"n": int(x.size), "mean": float(x.mean()), "ci95": [float(lo), float(hi)]}


def market_scores(forecasts: list[Forecast], quotes_by_game: dict, max_age: timedelta
                  ) -> pd.DataFrame:
    """Per game: model and de-vigged market P(over) at the modal fresh number, and the outcome."""
    rows = []
    for f in forecasts:
        qs = quotes_by_game.get(f.game_id, [])
        over, under = _latest(qs, "over", f.decision_ts), _latest(qs, "under", f.decision_ts)
        pairs = [(o.line_value, devig(o.american_price, under[b].american_price)[0])
                 for b, o in over.items()
                 if b in under and under[b].line_value == o.line_value
                 and f.decision_ts - o.captured_at_utc <= max_age
                 and f.decision_ts - under[b].captured_at_utc <= max_age]
        if not pairs:
            continue
        counts = Counter(line for line, _ in pairs)
        line = min(v for v, c in counts.items() if c == max(counts.values()))
        if f.final_total == line:
            continue
        win, push, _ = outcome_probs(f.pmf, "over", line)
        rows.append({"game_id": f.game_id, "line": line, "books": counts[line],
                     "p_model": float(np.clip(win / max(1 - push, 1e-12), 1e-12, 1 - 1e-12)),
                     "p_market": float(np.mean([p for v, p in pairs if v == line])),
                     "over": float(f.final_total > line)})
    return pd.DataFrame(rows)


def _proper(ms: pd.DataFrame, spec: ReplaySpec) -> dict:
    if ms.empty:
        return {"n": 0}
    o = ms["over"].to_numpy()
    brier = {c: (ms[c].to_numpy() - o) ** 2 for c in ("p_model", "p_market")}
    log = {c: -(o * np.log(ms[c]) + (1 - o) * np.log(1 - ms[c])).to_numpy()
           for c in ("p_model", "p_market")}
    return {"n": int(len(ms)), "over_rate": float(o.mean()),
            "brier_model": float(brier["p_model"].mean()),
            "brier_market": float(brier["p_market"].mean()),
            "brier_model_minus_market": _boot_mean(brier["p_model"] - brier["p_market"], spec),
            "log_loss_model_minus_market": _boot_mean(log["p_model"] - log["p_market"], spec)}


def _quote_files(sd: Path, data_root: Path, archive: dict) -> tuple[list[str], dict[int, int]]:
    paths, event_to_game = [], {}
    for event, info in archive["files"].items():
        # Periods archived before the copy existed fall back to the raw file.
        path = sd / info["file"] if "file" in info else \
            data_root / "raw" / "actionnetwork" / f"history_event_{event}.json"
        if not path.exists() or _sha(path.read_bytes()) != info["sha256"]:
            raise ShadowRefused(f"quote file for event {event} is missing or changed since archive")
        paths.append(str(path))
        event_to_game[int(event)] = int(info["game_id"])
    return paths, event_to_game


def replay(spec: ReplaySpec, lab_root: Path, data_root: Path, rehearsal: bool = False) -> dict:
    from scripts.actionnetwork_flatten import collect

    shadow = ShadowSpec.model_validate_json((REPO / spec.shadow_spec).read_text(encoding="utf-8"))
    if shadow.shadow_id() != spec.shadow_id:
        raise ShadowRefused(f"{spec.shadow_spec} is {shadow.shadow_id()}, not {spec.shadow_id}")
    sd = shadow_dir(lab_root, shadow)
    ledger = Ledger(sd / "ledger.sqlite3")
    ok, why = ledger.verify()
    if not ok:
        raise ShadowRefused(f"ledger chain fails: {why}")
    verdicts = ledger.records("period_verdict")
    if not rehearsal and not verdicts:
        raise ShadowRefused("the period has no verdict yet; the replay runs only after it")
    weeks = set(shadow.rehearsal_weeks if rehearsal else shadow.period_weeks)
    archives = {r.payload["week"]: r.payload for r in ledger.records("quotes_archived")}
    if not weeks <= set(archives):
        raise ShadowRefused(f"weeks without archived quotes: {sorted(weeks - set(archives))}")

    preds = {r.seq: r.payload for r in ledger.records("prediction")}
    snaps = {r.payload["snapshot_id"]: r.payload for r in ledger.records("snapshot")}
    pmfs: dict[str, np.ndarray] = {}
    forecasts, skipped = [], {"artifact_failed": 0}
    for r in ledger.records("score"):
        s = r.payload
        if s["alias"] != "challenger" or s["week"] not in weeks:
            continue
        if not s["artifact_ok"]:
            skipped["artifact_failed"] += 1
            continue
        p = preds[s["prediction_seq"]]
        snap = snaps[p["snapshot_id"]]
        if snap["pmf_file"] not in pmfs:
            blob = (sd / snap["pmf_file"]).read_bytes()
            if _sha(blob) != snap["pmf_sha256"]:
                raise ShadowRefused(f"{snap['pmf_file']} changed since its snapshot")
            pmfs[snap["pmf_file"]] = np.load(sd / snap["pmf_file"])
        kickoff = pd.Timestamp(s["kickoff_final"])
        forecasts.append(Forecast(
            game_id=s["game_id"],
            decision_ts=min(pd.Timestamp(p["decision_ts"]), kickoff).to_pydatetime(),
            kickoff=kickoff.to_pydatetime(),
            pmf=pmfs[snap["pmf_file"]][p["pmf_row"]], mean=p["pmf_mean"],
            # ponytail: the frozen policy abstains on neither, so neither is recorded.
            min_prior_games=0, selective_score=float("nan"), final_total=s["final_total"]))

    paths, event_to_game = [], {}
    for w in sorted(weeks):
        p, e = _quote_files(sd, data_root, archives[w])
        paths += p
        event_to_game |= e
    rows, _ = collect(paths)
    quotes, mapped = quotes_from_an_ticks(pd.DataFrame(rows, columns=[
        "event_id", "book_id", "period", "market_type", "side", "is_alt_market", "is_live",
        "updated_at", "line", "odds", "line_status"]), event_to_game)
    by_game: dict[int, list] = {}
    for q in quotes:
        by_game.setdefault(q.game_id, []).append(q)

    last_tick: dict[int, pd.Timestamp] = {}
    for r in rows:
        g = event_to_game.get(int(r["event_id"])) if r["event_id"] is not None else None
        if g is not None and r["updated_at"]:
            t = pd.Timestamp(r["updated_at"])
            last_tick[g] = max(t, last_tick.get(g, t))
    kick = {f.game_id: pd.Timestamp(f.kickoff) for f in forecasts}

    book = backtest(forecasts, by_game, shadow.policy, shadow.execution)
    close_unknown = 0
    if "clv_line" in book:
        proven = book["game_id"].map(lambda g: g in last_tick and last_tick[g] > kick[g])
        close_unknown = int(((book["action"] == "bet") & ~proven).sum())
        book.loc[~proven, ["clv_line", "clv_prob"]] = None
    bets = book[book["action"] == "bet"] if len(book) else book
    sens = sensitivity(forecasts, by_game, shadow.policy, shadow.execution,
                       spec.sensitivity_thresholds)
    actionable = sens.attrs["actionable"]
    sens = sens.drop(columns="mean_clv_line")
    ms = market_scores(forecasts, by_game, timedelta(minutes=shadow.execution.max_quote_age_minutes))
    out = {
        "replay_id": spec.replay_id(), "shadow_id": spec.shadow_id, "rehearsal": rehearsal,
        "framing": ("REHEARSAL: a mechanics check, never a result. " if rehearsal else "") + FRAMING,
        "weeks": sorted(weeks), "games_priced": len(forecasts), "skipped": skipped,
        "verdict_go": verdicts[-1].payload["go"] if verdicts else None,
        "policy": shadow.policy.model_dump(), "execution": shadow.execution.model_dump(),
        "quotes": mapped, "views": summarize(book),
        "units_per_bet": _boot_mean(bets["units"] if "units" in bets else [], spec),
        "clv_line": _boot_mean(bets["clv_line"].dropna() if "clv_line" in bets else [], spec),
        "clv_close_unknown": close_unknown,
        "sensitivity": sens.to_dict(orient="records"),
        "actionable": actionable,
        "p_over_vs_market": _proper(ms, spec),
        "code_sha256": code_fingerprint(),
    }
    dest = sd / "replay"
    dest.mkdir(exist_ok=True)
    name = f"{spec.replay_id()}{'-rehearsal' if rehearsal else ''}"
    (dest / f"{name}.json").write_text(json.dumps(out, indent=1, default=str), encoding="utf-8")
    book.to_csv(dest / f"{name}_ledger.csv", index=False)
    return out

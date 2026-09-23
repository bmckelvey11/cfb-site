"""Betting execution engine for full-game totals (Release D, D2; plan §31).

A decision can only reference a `Quote`: a specific book's line and American price with
the time it was captured. A number without a price or a clock, like the CFBD open, cannot
become a Quote, so it can never be priced, settled, or backtested.

Pieces: price conversion, settlement (versioned), win/push/loss probabilities at the
exact number from an integer predictive table, push-aware EV, multiplicative de-vig,
as-of quote selection with a maximum age, degradation against the bettor, versioned
policies, a flat one-unit ledger kept as separate edge / CLV / realized / availability
views (plan §30.3), and an execution-sensitivity table.
"""
from __future__ import annotations

import math
from dataclasses import dataclass
from datetime import datetime, timedelta

import numpy as np
import pandas as pd
from pydantic import AwareDatetime, Field, model_validator

from models.tuning.dist_spec import DecisionPolicySpec, ExecutionSpec
from models.tuning.spec import _Spec

RESULT_LOGIC_VERSION = "totals_full_game_v1"  # overtime counts; cancelled/postponed = no action
NO_ACTION = ("cancelled", "postponed", "suspended")
# Action Network book ids that are real sportsbooks; 15 (consensus) and 30 (Open) are not.
# docs/odds-sources-an-vs-apis-2026-09-11.md.
AN_BOOKS = {49: "Caesars", 68: "DraftKings", 69: "FanDuel", 71: "BetRivers", 75: "BetMGM"}
MODEST = {"line_half_point": {"line_degradation": 0.5},
          "price_10_cents": {"price_degradation_cents": 10},
          "missed_fill_10pct": {"missed_fill_rate": 0.1},
          "delay_60m": {"decision_delay_minutes": 60.0}}


def american_to_decimal(american: float) -> float:
    if abs(american) < 100:
        raise ValueError(f"American odds must be <= -100 or >= +100, got {american}")
    return 1 + american / 100 if american > 0 else 1 + 100 / abs(american)


def decimal_to_american(decimal: float) -> float:
    if decimal <= 1:
        raise ValueError(f"decimal odds must exceed 1, got {decimal}")
    return (decimal - 1) * 100 if decimal >= 2 else -100 / (decimal - 1)


def devig(american_over: float, american_under: float) -> tuple[float, float]:
    """Multiplicative de-vig: each side's implied probability over their sum."""
    qo, qu = 1 / american_to_decimal(american_over), 1 / american_to_decimal(american_under)
    return qo / (qo + qu), qu / (qo + qu)


class Quote(_Spec):
    """One executable price at one book at one time (plan §31.1)."""

    quote_id: str
    game_id: int | None
    source_event_id: str
    provider_id: str
    market_type: str = Field(pattern="^total$")
    period: str = Field(pattern="^full_game$")
    side: str = Field(pattern="^(over|under)$")
    line_value: float
    american_price: float
    decimal_price: float | None = None
    captured_at_utc: AwareDatetime
    source_received_at_utc: AwareDatetime | None = None
    is_live: bool = False
    availability_status: str = Field("available", pattern="^(available|unavailable)$")

    @model_validator(mode="before")
    @classmethod
    def _fill_decimal(cls, data):
        if isinstance(data, dict) and data.get("american_price") is not None \
                and data.get("decimal_price") is None:
            data = {**data, "decimal_price": american_to_decimal(data["american_price"])}
        return data

    @model_validator(mode="after")
    def _prices_agree(self):
        if not math.isclose(self.decimal_price, american_to_decimal(self.american_price),
                            rel_tol=1e-9):
            raise ValueError("decimal_price disagrees with american_price")
        return self


@dataclass(frozen=True)
class Settlement:
    result: str
    units: float
    logic_version: str = RESULT_LOGIC_VERSION


def settle(side: str, line: float, final_total: float, american: float,
           status: str = "final", stake: float = 1.0) -> Settlement:
    if status in NO_ACTION:
        return Settlement("no_action", 0.0)
    if final_total == line:
        return Settlement("push", 0.0)
    won = final_total > line if side == "over" else final_total < line
    return Settlement("win", stake * (american_to_decimal(american) - 1)) if won \
        else Settlement("loss", -stake)


def outcome_probs(pmf: np.ndarray, side: str, line: float) -> tuple[float, float, float]:
    """(win, push, loss) for one side at the exact number, from an integer table."""
    cdf = np.cumsum(pmf)
    k = int(math.floor(line))
    at_or_below = float(cdf[min(max(k, 0), len(pmf) - 1)]) if k >= 0 else 0.0
    push = float(pmf[k]) if line == k and 0 <= k < len(pmf) else 0.0
    over, under = 1.0 - at_or_below, at_or_below - push
    return (over, push, under) if side == "over" else (under, push, over)


def expected_value(p_win: float, p_loss: float, american: float) -> float:
    """EV per unit staked: a push returns the stake and contributes zero (plan §31.3)."""
    return p_win * (american_to_decimal(american) - 1) - p_loss


def _cents(american: float) -> float:
    return american - 100 if american >= 100 else american + 100


def _from_cents(x: float) -> float:
    return 100 + x if x >= 0 else -100 + x


def degrade(q: Quote, ex: ExecutionSpec) -> Quote:
    """Move the line and the price against the bettor by the execution spec's amounts."""
    line = q.line_value + (ex.line_degradation if q.side == "over" else -ex.line_degradation)
    price = _from_cents(_cents(q.american_price) - ex.price_degradation_cents)
    if (line, price) == (q.line_value, q.american_price):
        return q
    return Quote.model_validate({**q.model_dump(exclude={"decimal_price"}), "line_value": line,
                                 "american_price": price})


def _favour(q: Quote) -> tuple[float, float]:
    """Sort key, best first: the more favourable line, then the higher payout."""
    return (q.line_value if q.side == "over" else -q.line_value, -q.decimal_price)


def _latest(quotes: list[Quote], side: str, at: datetime, provider: str | None = None) -> dict:
    latest: dict[str, Quote] = {}
    for q in sorted(quotes, key=lambda q: (q.captured_at_utc, q.quote_id)):
        if (q.side == side and not q.is_live and q.captured_at_utc <= at
                and (provider is None or q.provider_id == provider)):
            latest[q.provider_id] = q
    return {p: q for p, q in latest.items() if q.availability_status == "available"}


def select_quote(quotes: list[Quote], side: str, decision_ts: datetime,
                 ex: ExecutionSpec) -> Quote | None:
    """Each book's last pre-decision, non-live, available tick, then the execution rule."""
    at = decision_ts + timedelta(minutes=ex.decision_delay_minutes)
    fresh = [q for q in _latest(quotes, side, at).values()
             if at - q.captured_at_utc <= timedelta(minutes=ex.max_quote_age_minutes)]
    if ex.quote_rule == "named":
        fresh = [q for q in fresh if q.provider_id == ex.book]
    if not fresh:
        return None
    ranked = sorted(fresh, key=lambda q: (_favour(q), q.provider_id))
    return ranked[0] if ex.quote_rule in ("best", "named") else ranked[len(ranked) // 2]


@dataclass(frozen=True)
class Forecast:
    game_id: int
    decision_ts: datetime
    kickoff: datetime
    pmf: np.ndarray
    mean: float
    min_prior_games: int
    selective_score: float
    final_total: float
    status: str = "final"


def _row(f: Forecast, policy: DecisionPolicySpec, action: str, **extra) -> dict:
    return {"game_id": f.game_id, "policy_id": policy.policy_id,
            "policy_version": policy.version, "action": action,
            "result_logic_version": RESULT_LOGIC_VERSION, **extra}


def _candidate(f: Forecast, quotes: list[Quote], side: str, policy: DecisionPolicySpec,
               ex: ExecutionSpec) -> dict | None:
    q = select_quote(quotes, side, f.decision_ts, ex)
    if q is None:
        return None
    taken = degrade(q, ex)
    p_win, p_push, p_loss = outcome_probs(f.pmf, side, taken.line_value)
    ev = expected_value(p_win, p_loss, taken.american_price)
    point_edge = (f.mean - taken.line_value) if side == "over" else (taken.line_value - f.mean)
    other = "under" if side == "over" else "over"
    pair = _latest(quotes, other, f.decision_ts + timedelta(minutes=ex.decision_delay_minutes),
                   provider=q.provider_id).get(q.provider_id)
    prob_edge = None
    if pair is not None and pair.line_value == q.line_value:
        fair = devig(q.american_price, pair.american_price)[0]
        prob_edge = p_win / max(1 - p_push, 1e-12) - fair
    score = {"point_edge": point_edge, "min_ev": ev, "prob_edge": prob_edge}.get(policy.kind)
    return {"side": side, "quote": q, "taken": taken, "p_win": p_win, "p_push": p_push,
            "p_loss": p_loss, "ev": ev, "point_edge": point_edge, "prob_edge": prob_edge,
            "score": score}


def _clv(f: Forecast, quotes: list[Quote], c: dict) -> tuple[float | None, float | None]:
    """Line and de-vigged probability moved in the bettor's favour by the book's close."""
    q = c["quote"]
    close = _latest(quotes, c["side"], f.kickoff, provider=q.provider_id).get(q.provider_id)
    if close is None:
        return None, None
    moved = close.line_value - q.line_value
    clv_line = moved if c["side"] == "over" else -moved
    other = "under" if c["side"] == "over" else "over"
    pair_now = _latest(quotes, other, q.captured_at_utc, provider=q.provider_id).get(q.provider_id)
    pair_close = _latest(quotes, other, f.kickoff, provider=q.provider_id).get(q.provider_id)
    if (pair_now is None or pair_close is None or close.line_value != q.line_value
            or pair_now.line_value != q.line_value or pair_close.line_value != q.line_value):
        return clv_line, None  # probabilities at different numbers are not comparable
    return clv_line, devig(close.american_price, pair_close.american_price)[0] \
        - devig(q.american_price, pair_now.american_price)[0]


def backtest(forecasts: list[Forecast], quotes_by_game: dict[int, list[Quote]],
             policy: DecisionPolicySpec, ex: ExecutionSpec) -> pd.DataFrame:
    """One ledger row per game: pass, abstain, no_quote, missed, or a flat one-unit bet."""
    rng = np.random.default_rng(ex.fill_seed)
    rows = []
    for f in forecasts:
        if policy.kind == "no_bet":
            rows.append(_row(f, policy, "pass"))
            continue
        if f.min_prior_games < policy.min_prior_games or (
                policy.max_selective_score is not None
                and f.selective_score > policy.max_selective_score):
            rows.append(_row(f, policy, "abstain"))
            continue
        quotes = quotes_by_game.get(f.game_id, [])
        cands = [c for side in ("over", "under")
                 if (c := _candidate(f, quotes, side, policy, ex)) is not None]
        if not cands:
            rows.append(_row(f, policy, "no_quote"))
            continue
        scored = [c for c in cands if c["score"] is not None]
        best = max(scored, key=lambda c: (c["score"], c["side"] == "over"), default=None)
        base = {}
        if best is not None:
            t = best["taken"]
            age = (f.decision_ts + timedelta(minutes=ex.decision_delay_minutes)
                   - best["quote"].captured_at_utc).total_seconds() / 60
            base = {"side": best["side"], "provider": t.provider_id, "quote_id": t.quote_id,
                    "line": t.line_value, "american": t.american_price,
                    "captured_at": t.captured_at_utc.isoformat(), "quote_age_min": age,
                    **{k: best[k] for k in ("p_win", "p_push", "p_loss", "ev", "point_edge",
                                            "prob_edge")}}
        if best is None or best["score"] < policy.threshold:
            rows.append(_row(f, policy, "pass", **base))
            continue
        if rng.random() < ex.missed_fill_rate:
            rows.append(_row(f, policy, "missed", **base))
            continue
        s = settle(best["side"], best["taken"].line_value, f.final_total,
                   best["taken"].american_price, f.status, ex.stake)
        clv_line, clv_prob = _clv(f, quotes, best)
        rows.append(_row(f, policy, "bet", **base, result=s.result, units=s.units,
                         clv_line=clv_line, clv_prob=clv_prob))
    return pd.DataFrame(rows)


def summarize(ledger: pd.DataFrame) -> dict:
    """Separate views (plan §30.3); never one blended score."""
    bets = ledger[ledger["action"] == "bet"] if "action" in ledger else ledger.iloc[0:0]
    col = (lambda c: bets[c].dropna() if c in bets else pd.Series(dtype=float))
    return {
        "edge": {"bets": int(len(bets)), "mean_ev": float(col("ev").mean()) if len(bets) else None,
                 "mean_point_edge": float(col("point_edge").mean()) if len(bets) else None},
        "clv": {"n": int(col("clv_line").size), "mean_line": float(col("clv_line").mean())
                if col("clv_line").size else None,
                "positive_share": float((col("clv_line") > 0).mean()) if col("clv_line").size else None,
                "mean_prob": float(col("clv_prob").mean()) if col("clv_prob").size else None},
        "realized": {"bets": int(len(bets)), "units": float(col("units").sum()),
                     "wins": int((col("result") == "win").sum()) if "result" in bets else 0,
                     "pushes": int((col("result") == "push").sum()) if "result" in bets else 0},
        "availability": {"games": int(len(ledger)),
                         # Abstained and no_bet games never look for a quote.
                         "with_quote": int(ledger["provider"].notna().sum()) if "provider" in ledger else 0,
                         "no_quote": int((ledger["action"] == "no_quote").sum()) if len(ledger) else 0,
                         "missed_fills": int((ledger["action"] == "missed").sum()) if len(ledger) else 0,
                         "median_quote_age_min": float(ledger["quote_age_min"].median())
                         if "quote_age_min" in ledger and ledger["quote_age_min"].notna().any() else None},
    }


def sensitivity(forecasts: list[Forecast], quotes_by_game: dict[int, list[Quote]],
                policy: DecisionPolicySpec, base: ExecutionSpec,
                thresholds: tuple[float, ...]) -> pd.DataFrame:
    """Units and bets per (scenario, threshold). `attrs['actionable']` is False when the
    base is not positive or any modest degradation turns units non-positive (plan §31.6)."""
    scenarios = {"base": {}, **MODEST, "median_book": {"quote_rule": "median"}}
    rows = []
    for name, over in scenarios.items():
        ex = ExecutionSpec.model_validate({**base.model_dump(), **over})
        for th in thresholds:
            pol = policy if policy.kind == "no_bet" else policy.model_copy(update={"threshold": th})
            s = summarize(backtest(forecasts, quotes_by_game, pol, ex))
            rows.append({"scenario": name, "threshold": th, "bets": s["realized"]["bets"],
                         "units": s["realized"]["units"], "mean_ev": s["edge"]["mean_ev"],
                         "mean_clv_line": s["clv"]["mean_line"]})
    table = pd.DataFrame(rows)
    at_base = table[table["threshold"] == policy.threshold]
    base_units = at_base.loc[at_base["scenario"] == "base", "units"]
    modest = at_base[at_base["scenario"].isin(MODEST)]
    table.attrs["actionable"] = bool(len(base_units) and base_units.iloc[0] > 0
                                     and (modest["units"] > 0).all())
    return table


def _flag(s: pd.Series) -> pd.Series:
    truth = {True: True, False: False, "True": True, "False": False, "true": True,
             "false": False, 1: True, 0: False}
    return s.map(lambda v: truth.get(v, None) if not (isinstance(v, float) and math.isnan(v))
                 else None).astype(object)


def quotes_from_an_ticks(ticks: pd.DataFrame,
                         event_to_game: dict[int, int] | None = None) -> tuple[list[Quote], dict]:
    """Full-game total ticks at real books as Quotes, plus counts of what was dropped."""
    dropped: dict[str, int] = {}

    def drop(mask: pd.Series, reason: str) -> pd.DataFrame:
        dropped[reason] = int(mask.sum())
        return ticks_[~mask]

    ticks_ = ticks
    ticks_ = drop(~((ticks_["period"] == "event") & (ticks_["market_type"] == "total")
                    & ticks_["side"].isin(["over", "under"])), "not_full_game_total")
    ticks_ = drop(~ticks_["book_id"].isin(list(AN_BOOKS)), "not_a_real_book")
    # The CSV mixes booleans, their strings, and blanks; astype(bool) would read a blank or
    # "False" as True. Parse explicitly and drop an unknown flag rather than guess.
    live, alt = _flag(ticks_["is_live"]), _flag(ticks_["is_alt_market"])
    ticks_ = drop(live.isna() | alt.isna(), "flag_unknown")
    live, alt = live[ticks_.index], alt[ticks_.index]
    ticks_ = drop(live.astype(bool), "live")
    ticks_ = drop(alt[ticks_.index].astype(bool), "alternate")
    ticks_ = drop(ticks_["odds"].isna() | (ticks_["odds"].abs() < 100) | ticks_["line"].isna(),
                  "no_price")
    quotes = []
    for t in ticks_.itertuples(index=False):
        at = pd.Timestamp(t.updated_at)
        quotes.append(Quote(
            quote_id=f"an:{t.event_id}:{t.book_id}:{t.side}:{t.updated_at}",
            game_id=(event_to_game or {}).get(int(t.event_id)),
            source_event_id=str(t.event_id), provider_id=AN_BOOKS[int(t.book_id)],
            market_type="total", period="full_game", side=t.side,
            line_value=float(t.line), american_price=float(t.odds),
            captured_at_utc=at.to_pydatetime(),
            availability_status="unavailable" if t.line_status == "unavailable" else "available"))
    return quotes, {"kept": len(quotes), "dropped": dropped}

"""Release D, D2: quotes, settlement, push-aware pricing, selection, policies, ledger.

Every expected number here is computed by hand; no real quotes or outcomes are used.
"""
from datetime import datetime, timedelta, timezone

import numpy as np
import pandas as pd
import pytest
from pydantic import ValidationError

from models.tuning.dist_spec import DecisionPolicySpec, ExecutionSpec
from models.tuning.market import (
    AN_BOOKS, RESULT_LOGIC_VERSION, Forecast, Quote, american_to_decimal, backtest,
    decimal_to_american, degrade, devig, expected_value, outcome_probs, quotes_from_an_ticks,
    select_quote, sensitivity, settle, summarize,
)

T = datetime(2026, 9, 26, 16, 0, tzinfo=timezone.utc)   # decision time
KICK = T + timedelta(hours=3)


def _q(provider, side, line, price, at, live=False, status="available", game=1):
    return Quote(quote_id=f"{provider}:{side}:{at.isoformat()}", game_id=game,
                 source_event_id="e1", provider_id=provider, market_type="total",
                 period="full_game", side=side, line_value=line, american_price=price,
                 captured_at_utc=at, is_live=live, availability_status=status)


def test_price_conversions():
    assert american_to_decimal(-110) == pytest.approx(1 + 100 / 110)
    assert american_to_decimal(150) == pytest.approx(2.5)
    for a in (-250, -110, 100, 135):
        assert decimal_to_american(american_to_decimal(a)) == pytest.approx(a)
    with pytest.raises(ValueError):
        american_to_decimal(50)


def test_a_quote_needs_a_price_and_a_capture_time():
    base = dict(quote_id="q", game_id=1, source_event_id="e", provider_id="DraftKings",
                market_type="total", period="full_game", side="over", line_value=47.5)
    with pytest.raises(ValidationError):
        Quote(**base, captured_at_utc=T)                          # the CFBD open: no price
    with pytest.raises(ValidationError):
        Quote(**base, american_price=-110)                        # no clock
    with pytest.raises(ValidationError):
        Quote(**base, american_price=-110, captured_at_utc=T.replace(tzinfo=None))
    with pytest.raises(ValidationError):
        Quote(**base, american_price=-110, captured_at_utc=T, decimal_price=2.5)
    q = Quote(**base, american_price=-110, captured_at_utc=T)
    assert q.decimal_price == pytest.approx(american_to_decimal(-110))


@pytest.mark.parametrize("side, line, total, status, result, units", [
    ("over", 47.5, 48, "final", "win", 100 / 110),
    ("over", 47.5, 47, "final", "loss", -1.0),
    ("over", 47.0, 47, "final", "push", 0.0),
    ("under", 47.0, 46, "final", "win", 100 / 110),
    ("under", 47.5, 55, "final", "loss", -1.0),
    ("over", 47.5, 60, "cancelled", "no_action", 0.0),
])
def test_settlement(side, line, total, status, result, units):
    s = settle(side, line, total, -110, status)
    assert (s.result, s.logic_version) == (result, RESULT_LOGIC_VERSION)
    assert s.units == pytest.approx(units)


PMF = np.zeros(151)
PMF[46], PMF[47], PMF[48] = 0.25, 0.25, 0.5


@pytest.mark.parametrize("side, line, expected", [
    ("over", 47.0, (0.5, 0.25, 0.25)),
    ("over", 47.5, (0.5, 0.0, 0.5)),
    ("under", 46.5, (0.25, 0.0, 0.75)),
    ("under", 47.0, (0.25, 0.25, 0.5)),
])
def test_outcome_probabilities_at_the_exact_number(side, line, expected):
    assert outcome_probs(PMF, side, line) == pytest.approx(expected)


def test_ev_counts_a_push_as_zero_and_devig_is_multiplicative():
    assert expected_value(0.5, 0.25, -110) == pytest.approx(0.5 * 100 / 110 - 0.25)
    assert devig(-110, -110) == pytest.approx((0.5, 0.5))
    qo, qu = 120 / 220, 100 / 200
    assert devig(-120, 100) == pytest.approx((qo / (qo + qu), qu / (qo + qu)))


def test_degradation_moves_line_and_price_against_the_bettor():
    over = _q("A", "over", 47.5, -110, T)
    d = degrade(over, ExecutionSpec(line_degradation=0.5, price_degradation_cents=10))
    assert (d.line_value, d.american_price) == (48.0, -120)
    under = _q("A", "under", 47.5, 105, T)
    d = degrade(under, ExecutionSpec(line_degradation=0.5, price_degradation_cents=10))
    assert (d.line_value, d.american_price) == (47.0, -105)


def _book():
    return [
        _q("A", "over", 47.5, -110, T - timedelta(hours=3)),
        _q("A", "over", 48.0, -110, T - timedelta(hours=1)),     # A's latest before T
        _q("A", "over", 46.0, -110, T + timedelta(minutes=5)),   # after T: invisible
        _q("B", "over", 47.0, -115, T - timedelta(minutes=30)),  # best over line
        _q("C", "over", 46.5, -110, T - timedelta(hours=30)),    # stale
        _q("D", "over", 45.0, -110, T - timedelta(minutes=10), live=True),
        _q("E", "over", 46.0, -110, T - timedelta(hours=2)),
        _q("E", "over", 46.0, -110, T - timedelta(minutes=20), status="unavailable"),
    ]


def test_quote_selection_is_as_of_the_decision_and_honours_the_rule():
    quotes = _book()
    best = select_quote(quotes, "over", T, ExecutionSpec(max_quote_age_minutes=600))
    assert (best.provider_id, best.line_value) == ("B", 47.0)
    named = select_quote(quotes, "over", T, ExecutionSpec(quote_rule="named", book="A"))
    assert named.line_value == 48.0
    median = select_quote(quotes, "over", T, ExecutionSpec(quote_rule="median"))
    assert median.provider_id == "A"            # B 47.0 better, A 48.0 worse: take the worse middle
    late = select_quote(quotes, "over", T, ExecutionSpec(decision_delay_minutes=10))
    assert (late.provider_id, late.line_value) == ("A", 46.0)   # A's 16:05 tick now visible
    wide = select_quote(quotes, "over", T, ExecutionSpec(max_quote_age_minutes=31 * 60))
    assert wide.provider_id == "C"                              # stale C only allowed when wide


def _forecast(final=49, mean=47.75, gid=1, early=10):
    return Forecast(game_id=gid, decision_ts=T, kickoff=KICK, pmf=PMF, mean=mean,
                    min_prior_games=early, selective_score=0.0, final_total=final,
                    status="final")


def test_backtest_prices_bets_settles_them_and_measures_clv():
    quotes = _book() + [
        _q("B", "under", 47.0, -105, T - timedelta(minutes=30)),
        _q("B", "over", 48.5, -110, KICK - timedelta(minutes=5)),   # B's closing tick
        _q("B", "under", 48.5, -110, KICK - timedelta(minutes=5)),
    ]
    policy = DecisionPolicySpec(policy_id="ev", version=1, kind="min_ev", threshold=0.01)
    ledger = backtest([_forecast()], {1: quotes}, policy, ExecutionSpec())
    row = ledger.iloc[0]
    assert (row["action"], row["side"], row["provider"], row["line"]) == ("bet", "over", "B", 47.0)
    # over 47: win 0.5 (48), push 0.25 (47), loss 0.25 (46) at -115.
    assert row["ev"] == pytest.approx(0.5 * 100 / 115 - 0.25)
    assert (row["result"], row["units"]) == ("win", pytest.approx(100 / 115))
    assert row["clv_line"] == pytest.approx(1.5)                 # closed 48.5, we had 47
    assert row["result_logic_version"] == RESULT_LOGIC_VERSION
    assert row["quote_age_min"] == pytest.approx(30.0)


def test_policies_abstain_and_pass():
    quotes = {1: _book()}
    no_bet = DecisionPolicySpec(policy_id="n", version=1, kind="no_bet")
    assert backtest([_forecast()], quotes, no_bet, ExecutionSpec()).iloc[0]["action"] == "pass"
    early = DecisionPolicySpec(policy_id="e", version=1, kind="point_edge", threshold=0.5,
                               min_prior_games=3)
    assert backtest([_forecast(early=1)], quotes, early, ExecutionSpec()).iloc[0]["action"] == "abstain"
    high = DecisionPolicySpec(policy_id="h", version=1, kind="point_edge", threshold=5.0)
    assert backtest([_forecast()], quotes, high, ExecutionSpec()).iloc[0]["action"] == "pass"
    none = backtest([_forecast(gid=2)], quotes, high, ExecutionSpec()).iloc[0]
    assert none["action"] == "no_quote"


def test_missed_fills_are_seeded():
    forecasts = [_forecast(gid=g) for g in range(1, 41)]
    quotes = {g: [q.model_copy(update={"game_id": g}) for q in _book()] for g in range(1, 41)}
    policy = DecisionPolicySpec(policy_id="ev", version=1, kind="min_ev", threshold=0.0)
    ex = ExecutionSpec(missed_fill_rate=0.5, fill_seed=7)
    a, b = backtest(forecasts, quotes, policy, ex), backtest(forecasts, quotes, policy, ex)
    pd.testing.assert_frame_equal(a, b)
    assert 5 < (a["action"] == "missed").sum() < 35


def test_summary_keeps_the_ledgers_apart_and_sensitivity_flags_fragility():
    forecasts = [_forecast(gid=g, final=49 if g % 2 else 46) for g in range(1, 21)]
    quotes = {g: [q.model_copy(update={"game_id": g}) for q in _book()] for g in range(1, 21)}
    policy = DecisionPolicySpec(policy_id="ev", version=1, kind="min_ev", threshold=0.0)
    s = summarize(backtest(forecasts, quotes, policy, ExecutionSpec()))
    assert set(s) == {"edge", "clv", "realized", "availability"}
    assert s["availability"]["games"] == 20 and s["realized"]["bets"] == 20
    table = sensitivity(forecasts, quotes, policy, ExecutionSpec(), thresholds=(0.0, 0.05))
    assert {"base", "line_half_point", "price_10_cents", "missed_fill_10pct",
            "delay_60m"} <= set(table["scenario"])
    assert table.attrs["actionable"] in (True, False)
    assert "threshold" in table and len(table) == 2 * table["scenario"].nunique()


def test_an_mapper_keeps_only_full_game_totals_at_real_books():
    rows = pd.DataFrame([
        # kept: DraftKings over and under
        dict(event_id=1, book_id=68, period="event", market_type="total", side="over",
             is_alt_market=False, is_live=False, updated_at="2026-09-20T12:00:00Z",
             line=51.5, odds=-110, line_status="normal"),
        dict(event_id=1, book_id=68, period="event", market_type="total", side="under",
             is_alt_market=False, is_live=False, updated_at="2026-09-20T12:00:00Z",
             line=51.5, odds=-110, line_status="unavailable"),
        # dropped: consensus book, live, alternate, spread market, first half, no odds
        dict(event_id=1, book_id=15, period="event", market_type="total", side="over",
             is_alt_market=False, is_live=False, updated_at="2026-09-20T12:00:00Z",
             line=51.5, odds=-110, line_status="normal"),
        dict(event_id=1, book_id=69, period="event", market_type="total", side="over",
             is_alt_market=False, is_live=True, updated_at="2026-09-20T12:00:00Z",
             line=51.5, odds=-110, line_status="normal"),
        dict(event_id=1, book_id=69, period="event", market_type="total", side="over",
             is_alt_market=True, is_live=False, updated_at="2026-09-20T12:00:00Z",
             line=55.5, odds=150, line_status="normal"),
        dict(event_id=1, book_id=69, period="event", market_type="spread", side="home",
             is_alt_market=False, is_live=False, updated_at="2026-09-20T12:00:00Z",
             line=-3.5, odds=-110, line_status="normal"),
        dict(event_id=1, book_id=69, period="firsthalf", market_type="total", side="over",
             is_alt_market=False, is_live=False, updated_at="2026-09-20T12:00:00Z",
             line=24.5, odds=-110, line_status="normal"),
        dict(event_id=1, book_id=71, period="event", market_type="total", side="over",
             is_alt_market=False, is_live=False, updated_at="2026-09-20T12:00:00Z",
             line=51.5, odds=None, line_status="normal"),
        # blank live flag: unknown, dropped rather than guessed
        dict(event_id=1, book_id=75, period="event", market_type="total", side="over",
             is_alt_market=False, is_live=None, updated_at="2026-09-20T12:00:00Z",
             line=51.5, odds=-110, line_status="normal"),
        # the string "False" must not read as True
        dict(event_id=1, book_id=49, period="event", market_type="total", side="under",
             is_alt_market="False", is_live="False", updated_at="2026-09-20T12:05:00Z",
             line=51.5, odds=-105, line_status="normal"),
    ])
    quotes, report = quotes_from_an_ticks(rows, {1: 401})
    assert [(q.provider_id, q.side, q.availability_status) for q in quotes] == [
        ("DraftKings", "over", "available"), ("DraftKings", "under", "unavailable"),
        ("Caesars", "under", "available")]
    assert quotes[0].game_id == 401 and quotes[0].quote_id.startswith("an:1:68:over:")
    assert report["kept"] == 3
    assert report["dropped"] == {"not_full_game_total": 2, "not_a_real_book": 1,
                                 "flag_unknown": 1, "live": 1, "alternate": 1, "no_price": 1}
    assert quotes_from_an_ticks(rows)[0][0].game_id is None
    assert AN_BOOKS[68] == "DraftKings" and 15 not in AN_BOOKS

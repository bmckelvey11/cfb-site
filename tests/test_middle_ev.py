"""The middle EV math lives in JS inside middle_calculator.html, so test it there.

Porting the five-branch logic to Python for testing would create two copies that
drift. Instead this extracts the EV_MATH block from the page and runs it under
node, so the tested code is literally the code the page ships.
"""

from __future__ import annotations

import json
import re
import shutil
import subprocess
import textwrap
from pathlib import Path

import pytest

HTML = Path(__file__).resolve().parents[1] / "models" / "totals" / "middle_calculator.html"
BLOCK = re.compile(r"/\* ---- EV_MATH:BEGIN.*?\*/(.*?)/\* ---- EV_MATH:END ---- \*/", re.DOTALL)

pytestmark = pytest.mark.skipif(shutil.which("node") is None, reason="node not installed")

WIN = 100 / 110 * 100  # profit on a $100 -110 winner
TOL = 0.01


def eval_js(bet: dict, dist: dict, expression: str):
    """Run `expression` against the page's own EV block, with `bet` and `dist` bound."""
    source = BLOCK.search(HTML.read_text(encoding="utf-8"))
    assert source, "EV_MATH block not found in middle_calculator.html"
    script = source.group(1) + textwrap.dedent(
        f"""
        const bet = {json.dumps(bet)};
        const raw = {json.dumps({str(k): v for k, v in dist.items()})};
        const dist = {{}};
        for (const k of Object.keys(raw)) dist[Number(k)] = raw[k];
        console.log(JSON.stringify(({expression})));
        """
    )
    proc = subprocess.run(
        ["node", "--input-type=commonjs", "-e", script],
        capture_output=True, text=True, timeout=60,
    )
    assert proc.returncode == 0, proc.stderr
    return json.loads(proc.stdout)


def run_js(bet: dict, dist: dict) -> dict:
    return eval_js(bet, dist, """(() => {
        const out = evaluate(bet, dist);
        return {
            ev: out.ev, evPct: out.evPct, preEv: out.preEv,
            liveEv: out.liveEv, liveEvPct: out.liveEvPct,
            rows: out.rows.map(r => ({key: r.key, pre: r.pre, live: r.live, net: r.net, prob: r.prob})),
        };
    })()""")


def bet(pre_side="over", pre_num=52.0, live_num=56.0, pre_stake=100, live_stake=100):
    return {
        "preSide": pre_side,
        "liveSide": "under" if pre_side == "over" else "over",
        "preNum": pre_num, "prePrice": -110, "preStake": pre_stake,
        "liveNum": live_num, "livePrice": -110, "liveStake": live_stake,
    }


def rows_by_key(result):
    return {r["key"]: r for r in result["rows"]}


def test_over_then_under_five_branches():
    """Pregame Over 52 + live Under 56: the classic middle, integer numbers."""
    dist = {48: 0.2, 52: 0.1, 54: 0.3, 56: 0.1, 60: 0.3}
    r = rows_by_key(run_js(bet(), dist))

    assert (r["below"]["pre"], r["below"]["live"]) == ("loss", "win")
    assert r["below"]["net"] == pytest.approx(WIN - 100, abs=TOL)

    # A push on one leg while the other wins is a WINNER, not a half-loss.
    assert (r["pushLo"]["pre"], r["pushLo"]["live"]) == ("push", "win")
    assert r["pushLo"]["net"] == pytest.approx(WIN, abs=TOL)

    assert (r["middle"]["pre"], r["middle"]["live"]) == ("win", "win")
    assert r["middle"]["net"] == pytest.approx(2 * WIN, abs=TOL)

    assert (r["pushHi"]["pre"], r["pushHi"]["live"]) == ("win", "push")
    assert r["pushHi"]["net"] == pytest.approx(WIN, abs=TOL)

    assert (r["above"]["pre"], r["above"]["live"]) == ("win", "loss")
    assert r["above"]["net"] == pytest.approx(WIN - 100, abs=TOL)


def test_under_then_over_is_symmetric():
    """Pregame Under 60 + live Over 54 mirrors the Over case exactly."""
    dist = {50: 0.2, 54: 0.1, 57: 0.3, 60: 0.1, 64: 0.3}
    r = rows_by_key(run_js(bet(pre_side="under", pre_num=60.0, live_num=54.0), dist))

    assert (r["below"]["pre"], r["below"]["live"]) == ("win", "loss")
    assert (r["pushLo"]["pre"], r["pushLo"]["live"]) == ("win", "push")
    assert (r["middle"]["pre"], r["middle"]["live"]) == ("win", "win")
    assert (r["pushHi"]["pre"], r["pushHi"]["live"]) == ("push", "win")
    assert (r["above"]["pre"], r["above"]["live"]) == ("loss", "win")
    assert r["middle"]["net"] == pytest.approx(2 * WIN, abs=TOL)


def test_half_point_numbers_have_no_push_mass():
    dist = {48: 0.4, 55: 0.3, 62: 0.3}
    r = rows_by_key(run_js(bet(pre_num=52.5, live_num=58.5), dist))
    assert r["pushLo"]["prob"] == 0
    assert r["pushHi"]["prob"] == 0
    assert r["middle"]["prob"] == pytest.approx(0.3, abs=1e-9)


def test_probabilities_partition_the_distribution():
    dist = {48: 0.2, 52: 0.1, 54: 0.3, 56: 0.1, 60: 0.3}
    out = run_js(bet(), dist)
    assert sum(r["prob"] for r in out["rows"]) == pytest.approx(1.0, abs=1e-9)


def test_ev_matches_hand_computation():
    dist = {48: 0.2, 52: 0.1, 54: 0.3, 56: 0.1, 60: 0.3}
    out = run_js(bet(), dist)
    expected = (
        0.2 * (WIN - 100)      # below
        + 0.1 * WIN            # push low
        + 0.3 * (2 * WIN)      # middle
        + 0.1 * WIN            # push high
        + 0.3 * (WIN - 100)    # above
    )
    assert out["ev"] == pytest.approx(expected, abs=TOL)
    assert out["evPct"] == pytest.approx(expected / 200, abs=1e-6)


def test_unequal_stakes_change_the_loss_legs():
    dist = {48: 0.5, 60: 0.5}
    r = rows_by_key(run_js(bet(pre_stake=100, live_stake=250), dist))
    # Over leg loses $100, Under leg wins on $250 at -110.
    assert r["below"]["net"] == pytest.approx(250 * 100 / 110 - 100, abs=TOL)
    # Over leg wins on $100, Under leg loses $250.
    assert r["above"]["net"] == pytest.approx(WIN - 250, abs=TOL)


def test_plus_money_payout():
    dist = {54: 1.0}
    b = bet()
    b["prePrice"] = 150
    r = rows_by_key(run_js(b, dist))
    assert r["middle"]["net"] == pytest.approx(150 + WIN, abs=TOL)


def test_live_leg_ev_is_separable_and_sums_to_the_whole_position():
    """The pregame stake is sunk, so the live leg's own EV is the real decision."""
    dist = {48: 0.2, 52: 0.1, 54: 0.3, 56: 0.1, 60: 0.3}
    out = run_js(bet(), dist)
    assert out["preEv"] + out["liveEv"] == pytest.approx(out["ev"], abs=TOL)
    # Under 56 at -110 against P(T < 56) = 0.6, P(push) = 0.1, P(loss) = 0.3.
    assert out["liveEv"] == pytest.approx(0.6 * WIN - 0.3 * 100, abs=TOL)


def test_a_wider_spread_lowers_the_middle_probability():
    """The live number is always an edge of the window, so the distribution is
    centred on that edge and the window sits on one side of the mean. Widening
    the spread pushes mass out of it -- P(middle) falls, it does not rise.

    This pins the direction of the tool's stated bias. If it ever flips, the
    caveat on the page ("P(middle) is a lower bound") becomes false.
    """
    b = bet(pre_num=52.0, live_num=58.0)
    # Symmetric distributions centred on the live number, 58, widening outward.
    narrow = {56: 0.2, 57: 0.2, 58: 0.2, 59: 0.2, 60: 0.2}
    wide = {48: 0.2, 53: 0.2, 58: 0.2, 63: 0.2, 68: 0.2}
    p_narrow = rows_by_key(run_js(b, narrow))["middle"]["prob"]
    p_wide = rows_by_key(run_js(b, wide))["middle"]["prob"]
    assert p_narrow > p_wide, f"widening raised P(middle): {p_narrow} -> {p_wide}"


def test_no_middle_window_when_line_moves_the_wrong_way():
    """Over 56 + live Under 52: no final total wins both legs."""
    dist = {48: 0.3, 54: 0.4, 60: 0.3}
    r = rows_by_key(run_js(bet(pre_num=56.0, live_num=52.0), dist))
    # The 52-56 band loses the Over and loses nothing else -- it is not a middle.
    assert (r["middle"]["pre"], r["middle"]["live"]) == ("loss", "loss")
    assert r["middle"]["net"] == pytest.approx(-200, abs=TOL)


# --- stake sizing -------------------------------------------------------------

# Centred on the live number (Under 58 wins half the time), so the hedge is
# -EV by roughly the vig -- which is what the real table produces. A
# distribution that made the live leg +EV would turn Kelly into a value bet
# and none of the hedging properties below would hold.
SIZING_DIST = {44: 0.15, 50: 0.15, 54: 0.20, 62: 0.25, 70: 0.25}


def test_equalizing_stake_makes_both_outside_outcomes_pay_the_same():
    b = bet(pre_num=52.0, live_num=58.0)
    b["liveStake"] = eval_js(b, SIZING_DIST, "equalizingStake(bet)")
    r = rows_by_key(run_js(b, SIZING_DIST))
    assert r["below"]["net"] == pytest.approx(r["above"]["net"], abs=TOL)


def test_equalizing_stake_scales_with_the_price_ratio():
    """y = x * dO / dU -- equal stakes are right only at equal prices."""
    b = bet(pre_num=52.0, live_num=58.0)
    b["prePrice"], b["livePrice"] = 150, -200
    got = eval_js(b, SIZING_DIST, "equalizingStake(bet)")
    assert got == pytest.approx(100 * 1.5 / 0.5, abs=TOL)


def test_kelly_stake_beats_its_neighbours():
    """The returned stake maximises expected log growth, so nudging it either
    way must not improve growth. That is the whole claim behind calling it
    optimal."""
    b = bet(pre_num=52.0, live_num=58.0, pre_stake=1000)
    got = eval_js(b, SIZING_DIST, """(() => {
        const W = 10000, y = kellyStake(bet, dist, W);
        return {y, at: growth(bet, dist, W, y),
                lo: growth(bet, dist, W, y * 0.9),
                hi: growth(bet, dist, W, y * 1.1)};
    })()""")
    assert got["y"] > 0
    assert got["at"] >= got["lo"] and got["at"] >= got["hi"]


def test_kelly_stake_grows_with_the_position_as_a_share_of_bankroll():
    """A 1%-of-bankroll position barely needs hedging; a 50% one nearly wants
    the full flattening stake."""
    fractions = []
    for stake, bankroll in [(100, 10000), (1000, 10000), (500, 1000)]:
        b = bet(pre_num=52.0, live_num=58.0, pre_stake=stake)
        fractions.append(eval_js(b, SIZING_DIST, f"""(() => {{
            const y = kellyStake(bet, dist, {bankroll});
            return y / equalizingStake(bet);
        }})()"""))
    assert fractions == sorted(fractions), f"not monotone in position size: {fractions}"
    assert fractions[0] < 0.5 < fractions[-1]
    # A -EV hedge never wants more than the flattening stake.
    assert all(f <= 1.0 for f in fractions), fractions


def test_kelly_stake_is_zero_when_the_hedge_costs_more_than_it_is_worth():
    """A tiny position priced at brutal juice: no hedge maximises growth."""
    b = bet(pre_num=52.0, live_num=58.0, pre_stake=10)
    b["livePrice"] = -100000
    assert eval_js(b, SIZING_DIST, "kellyStake(bet, dist, 1000000)") == 0


def test_growth_refuses_a_stake_that_could_bust_the_bankroll():
    b = bet(pre_num=52.0, live_num=58.0, pre_stake=100)
    assert eval_js(b, SIZING_DIST, "growth(bet, dist, 200, 500) === -Infinity ? 'busts' : 'ok'") == "busts"
    # Whatever it picks must itself be survivable.
    assert eval_js(b, SIZING_DIST,
                   "Number.isFinite(growth(bet, dist, 200, kellyStake(bet, dist, 200)))") is True

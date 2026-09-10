"""Compare PFF Greenline's total projections against Pinnacle's number.

    python research/totals/scripts/greenline_vs_pinnacle.py --week 2
    python research/totals/scripts/greenline_vs_pinnacle.py --week 2 --book DraftKings
    python research/totals/scripts/greenline_vs_pinnacle.py --self-check

Pinnacle is the reference price, not just another book: low margin, high limits,
and it moves on money rather than on handle. Comparing Greenline to a retail book
says how good a number you can get; comparing it to Pinnacle says whether the
projection disagrees with the sharpest opinion available.

The distinction matters for reading the under lean. Greenline sitting below a
recreational book's total can mean the book is shaded for public over money.
Greenline sitting below PINNACLE means the projection genuinely disagrees with
the market's best estimate -- that is a claim of edge, and it is falsifiable.

Pinnacle totals come from the oddspapi snapshot (`scripts/pull_oddspapi.py`,
one request per run). Only full-game main lines are read: a market id ends
`/<period>/totals` and period 0 is the full game, so first-half and quarter
markets are skipped rather than silently averaged in.

Pinnacle's own no-vig midpoint is reported beside the posted line. The posted
number is where you bet; the de-vigged midpoint is what Pinnacle actually thinks,
and on a -108/-112 total those differ by roughly a tenth of a point.
"""

from __future__ import annotations

import argparse
import csv
import json
import statistics as st
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[0]))
sys.path.insert(0, str(Path(__file__).resolve().parents[3]))
from cfb_paths import INGEST  # noqa: E402
from match_greenline_books import (  # noqa: E402
    GL_DIR, break_even, edge_at, is_placeholder, latest_snapshot, match, p_under, slug_names,
)

PIN_DIR = INGEST / "oddspapi"
# How far from its own typical shade a projection may sit before it stops looking like
# the model's usual lean and starts looking like a mistake on that one game.
MAX_GAP_SD = 2.5


def american(price: str | None) -> int | None:
    try:
        return int(str(price).replace("+", ""))
    except (TypeError, ValueError):
        return None


def pinnacle_totals() -> tuple[list[dict], str, Path]:
    """Full-game main-line totals from the newest oddspapi snapshot."""
    snaps = sorted(PIN_DIR.glob("oddspapi_ncaa_*.json"))
    if not snaps:
        raise SystemExit(f"no snapshot in {PIN_DIR} -- run scripts/pull_oddspapi.py")
    path = snaps[-1]
    payload = json.loads(path.read_text(encoding="utf-8"))
    out = []
    for fx in payload["fixtures"]:
        markets = ((fx.get("bookmakerOdds") or {}).get("pinnacle") or {}).get("markets") or {}
        line = over = under = limit = None
        for m in markets.values():
            mid = m.get("bookmakerMarketId", "")
            parts = mid.split("/")
            if not (mid.endswith("/totals") and len(parts) >= 2 and parts[-2] == "0"):
                continue                      # period 0 only; 1H and quarters are other markets
            for oc in (m.get("outcomes") or {}).values():
                pl = (oc.get("players") or {}).get("0") or {}
                if not (pl.get("mainLine") and pl.get("active")):
                    continue
                oid = str(pl.get("bookmakerOutcomeId") or "")
                if "/" not in oid:
                    continue
                pts, side = oid.rsplit("/", 1)
                try:
                    pts = float(pts)
                except ValueError:
                    continue
                line = pts
                limit = max(limit or 0, float(pl.get("limit") or 0))
                if side == "over":
                    over = american(pl.get("priceAmerican"))
                elif side == "under":
                    under = american(pl.get("priceAmerican"))
        if line is None or over is None or under is None:
            continue
        try:
            kick = datetime.fromisoformat(fx["startTime"].replace("Z", "+00:00"))
        except (KeyError, ValueError):
            continue
        out.append({"kick": kick, "line": line, "over": over, "under": under, "limit": limit,
                    "home": _t(fx.get("participant1Name")), "away": _t(fx.get("participant2Name")),
                    "home_name": fx.get("participant1Name"), "away_name": fx.get("participant2Name")})
    return out, payload.get("pulled_at", path.stem), path


def _t(name):
    from match_greenline_books import toks
    return toks(name or "")


def novig_under(over_odds: int, under_odds: int) -> float:
    """Pinnacle's under probability with the margin removed, proportionally."""
    po, pu = break_even(over_odds), break_even(under_odds)
    return pu / (po + pu)


def fair_line(line: float, over_odds: int, under_odds: int, sigma_pts: float) -> float:
    """The total at which Pinnacle would be even money, given its priced skew.

    Prices rarely sit at -110/-110, and the tilt is information: an under at -115
    means Pinnacle's own midpoint is below the posted number. Converted through the
    same normal the rest of this work uses, so it is comparable to a projection.
    """
    from statistics import NormalDist
    return line - NormalDist().inv_cdf(novig_under(over_odds, under_odds)) * sigma_pts


def self_check() -> None:
    assert american("-108") == -108 and american("+120") == 120
    assert american(None) is None and american("x") is None

    # A balanced market is a coin flip and its fair line is the posted line.
    assert abs(novig_under(-110, -110) - 0.5) < 1e-9
    assert abs(fair_line(50.0, -110, -110, 10.0) - 50.0) < 1e-9
    # Juice on the under means Pinnacle leans under, so its fair total sits below.
    assert novig_under(-105, -115) > 0.5
    assert fair_line(50.0, -105, -115, 10.0) < 50.0
    # ...and the reverse.
    assert fair_line(50.0, -115, -105, 10.0) > 50.0
    # The margin itself must not move the midpoint: doubling both sides is symmetric.
    assert abs(novig_under(-120, -120) - 0.5) < 1e-9
    print("self-check ok")


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--season", type=int, default=2026)
    ap.add_argument("--week", default="2")
    ap.add_argument("--book", default="DraftKings", help="retail book to show beside Pinnacle")
    ap.add_argument("--reference", choices=("pff", "pinnacle"), default="pff",
                    help="whose number is treated as the true mean when pricing the bet")
    ap.add_argument("--self-check", action="store_true")
    args = ap.parse_args()

    if args.self_check:
        self_check()
        return

    # The FULL flag set, not the unders-only slate: that file is selected on
    # projection < line, so measuring the offset against Pinnacle there would
    # recover the selection rule and nothing else.
    gl_path = GL_DIR / f"pff_greenline_{args.season}_w{args.week}.csv"
    if not gl_path.exists():
        raise SystemExit(f"{gl_path} not found")
    flags = [{"game_id": x["pff_game_id"], "kickoff": x["kickoff_raw"][:16],
              "away": x["away_abbreviation"], "home": x["home_abbreviation"],
              "line": x["market_over_under"], "projection": x["greenline_total_projection"],
              "band": x.get("total_best_side", "")}
             for x in csv.DictReader(gl_path.open(encoding="utf-8"))
             if x.get("greenline_total_projection") and x.get("market_over_under")]
    sched = {x["pff_game_id"]: x for x in
             csv.DictReader((GL_DIR / f"pff_schedule_{args.season}.csv").open(encoding="utf-8"))}

    pin, pin_at, pin_path = pinnacle_totals()
    oa, oa_at, _ = latest_snapshot()
    print(f"=== Greenline projections vs Pinnacle, {args.season} week {args.week} ===")
    print(f"Pinnacle {pin_path.name} (pulled {pin_at})")
    print(f"{args.book} snapshot pulled {oa_at}\n")

    rows = []
    for fl in flags:
        g = sched.get(fl["game_id"])
        away, home = slug_names(g.get("matchup_path", "")) if g else ("", "")
        kick = datetime.fromisoformat(fl["kickoff"]).replace(
            tzinfo=timezone(timedelta(hours=-4))).astimezone(timezone.utc)
        ph = is_placeholder(fl["kickoff"])
        pe = match(kick, away, home, pin, ph)
        if pe is None:
            continue
        be = match(kick, away, home, oa, ph)
        proj = float(fl["projection"])
        sig = None
        from match_greenline_books import sigma
        sig = sigma(pe["line"])
        rows.append({
            "game": f"{fl['away']} @ {fl['home']}", "band": fl["band"],
            "pff_line": float(fl["line"]), "proj": proj,
            "pin_line": pe["line"], "pin_over": pe["over"], "pin_under": pe["under"],
            "pin_fair": fair_line(pe["line"], pe["over"], pe["under"], sig),
            "pin_limit": pe["limit"],
            "book_line": (be or {}).get("totals", {}).get(args.book, (None, None))[0],
            "book_odds": (be or {}).get("totals", {}).get(args.book, (None, None))[1],
            "edge_vs_pin": edge_at(pe["line"], proj, pe["under"]),
            # Pinnacle as the true mean: PFF's projection drops out entirely and the
            # bet is worth only what the book's number beats Pinnacle's fair one by.
            "edge_pin_ref": (
                edge_at(be["totals"][args.book][0], fair_line(pe["line"], pe["over"],
                                                              pe["under"], sig),
                        be["totals"][args.book][1])
                if be and args.book in be.get("totals", {}) else None),
        })

    if not rows:
        raise SystemExit("no Greenline flag matched a Pinnacle full-game total")

    rows.sort(key=lambda r: r["proj"] - r["pin_fair"])
    print(f"{'game':<14} {'PFF proj':>8} {'Pin':>6} {'Pin fair':>8} {'proj-fair':>9} "
          f"{'Pin u':>6} {args.book[:6]:>7} {'edge@Pin':>9}")
    for r in rows:
        bl = f"{r['book_line']:.1f}" if r["book_line"] is not None else "  --"
        print(f"{r['game']:<14} {r['proj']:8.1f} {r['pin_line']:6.1f} {r['pin_fair']:8.2f} "
              f"{r['proj']-r['pin_fair']:+9.2f} {r['pin_under']:+6d} {bl:>7} "
              f"{r['edge_vs_pin']*100:+8.2f}%")

    d = [r["proj"] - r["pin_fair"] for r in rows]
    print(f"\nprojection minus Pinnacle's fair total, n={len(rows)}:")
    print(f"  mean {st.mean(d):+.2f}   median {st.median(d):+.2f}   sd {st.pstdev(d):.2f}")
    print(f"  below Pinnacle: {sum(1 for v in d if v < 0)}/{len(d)}")
    print(f"  (all {len(rows)} flagged games, both sides -- not the unders-only slate)")
    for side in ("under", "over"):
        sub = [r["proj"] - r["pin_fair"] for r in rows if r["band"] == side]
        if sub:
            print(f"    PFF flags {side:<5}: n={len(sub):2d}  mean {st.mean(sub):+.2f}  "
                  f"median {st.median(sub):+.2f}  below Pinnacle {sum(1 for v in sub if v<0)}/{len(sub)}")
    live = [r for r in rows if r["edge_vs_pin"] > 0]
    print(f"  still positive priced at Pinnacle's own number and juice: {len(live)}/{len(rows)}")

    ref = [r for r in rows if r["band"] == "under"]
    if ref:
        gaps = [r["proj"] - r["pin_fair"] for r in ref]
        med, sd = st.median(gaps), st.pstdev(gaps)
        print(f"\nSANITY CHECK -- is any projection wildly off Pinnacle? (n={len(ref)} unders)")
        print(f"  proj - Pinnacle fair: median {med:+.2f}  sd {sd:.2f}  "
              f"range {min(gaps):+.2f}..{max(gaps):+.2f}")
        print("  A consistent shade is the model. One game far from the rest is a mistake.")
        odd = [r for r in ref if abs((r["proj"] - r["pin_fair"]) - med) > MAX_GAP_SD * sd]
        if odd:
            print(f"  {len(odd)} beyond {MAX_GAP_SD} sd of the usual shade -- suspect:")
            for r in sorted(odd, key=lambda r: r["proj"] - r["pin_fair"]):
                print(f"    {r['game']:<14} proj {r['proj']:.1f} vs Pinnacle fair "
                      f"{r['pin_fair']:.2f}  ({r['proj']-r['pin_fair']:+.2f})")
        else:
            print(f"  none beyond {MAX_GAP_SD} sd -- no projection is out of line with Pinnacle")
        far = [r for r in ref if r["edge_pin_ref"] is not None and r["edge_pin_ref"] <= 0]
        print(f"  for reference only: {len(far)}/{len(ref)} would be negative if Pinnacle's")
        print("  fair total, not PFF's projection, were treated as the true mean.")

    dk = [r for r in rows if r["book_line"] is not None]
    if dk:
        gap = [r["book_line"] - r["pin_line"] for r in dk]
        print(f"\n{args.book} minus Pinnacle's posted total, n={len(dk)}:")
        print(f"  mean {st.mean(gap):+.2f}   median {st.median(gap):+.2f}")
        better = sum(1 for v in gap if v > 0)
        print(f"  {args.book} hangs the higher (better for an under) number in {better}/{len(dk)}")

    lim = [r["pin_limit"] for r in rows if r["pin_limit"]]
    if lim:
        print(f"\nPinnacle limits: median {st.median(lim):,.0f}  min {min(lim):,.0f}  max {max(lim):,.0f}")
        print("(a low limit is Pinnacle saying it is unsure, not that it is confident)")

    dest = GL_DIR / f"greenline_vs_pinnacle_{args.season}_w{args.week}.csv"
    with dest.open("w", newline="", encoding="utf-8") as fh:
        w = csv.DictWriter(fh, fieldnames=list(rows[0]))
        w.writeheader()
        w.writerows(rows)
    print(f"\nwrote {dest}")


if __name__ == "__main__":
    main()

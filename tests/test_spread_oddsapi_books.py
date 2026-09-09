import json
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "research" / "spread" / "scripts"))
import weekly_slate as ws  # noqa: E402

NOW = datetime(2026, 9, 9, 20, 30, tzinfo=timezone.utc)


def snapshot(events, pulled_at="2026-09-09T20:05:31Z"):
    return {"pulled_at": pulled_at, "sport": "americanfootball_ncaaf", "events": events}


def event(home, away, quotes, commence="2026-09-12T23:00:00Z"):
    """One the-odds-api event; `quotes` is {book: (home_point, price)}."""
    return {
        "id": f"{home}-{away}", "commence_time": commence,
        "home_team": home, "away_team": away,
        "bookmakers": [
            {"key": b, "title": b.title(), "markets": [{"key": "spreads", "outcomes": [
                {"name": home, "price": price, "point": point},
                {"name": away, "price": -110, "point": -point},
            ]}]}
            for b, (point, price) in quotes.items()
        ],
    }


def write(tmp_path, payload, monkeypatch):
    folder = tmp_path / "oddsapi"
    folder.mkdir()
    (folder / "odds_americanfootball_ncaaf_20260909T200531Z.json").write_text(
        json.dumps(payload), encoding="utf-8")
    monkeypatch.setattr(ws, "OA_SNAP_DIR", folder)


# ------------------------------------------------------------------ name resolution


def test_mascot_is_stripped_to_the_school():
    keys = {"miami", "florida a&m", "marshall"}
    assert ws.oa_resolve("Miami Hurricanes", keys) == "miami"
    assert ws.oa_resolve("Florida A&M Rattlers", keys) == "florida a&m"
    assert ws.oa_resolve("Marshall Thundering Herd", keys) == "marshall"  # two-token mascot


def test_alias_bridges_a_spelling_the_strip_cannot_reach():
    # PT abbreviates; stripping "Panthers" leaves "florida international", which is not the key.
    assert ws.oa_resolve("Florida International Panthers", {"florida intl"}) == "florida intl"
    assert ws.oa_resolve("Middle Tennessee Blue Raiders", {"middle tenn"}) == "middle tenn"


def test_an_over_eager_strip_leaves_the_game_unpriced_not_mispriced():
    """The strip alone is ambiguous: "Florida International Panthers" can reach "florida".

    What stops that from pricing FIU's game off the Gators' line is that the merge keys on
    BOTH teams -- the road name has to misresolve onto the same PT row too.
    """
    slate = pd.DataFrame({"key": ["florida"], "rkey": ["texas"]})           # Texas @ Florida
    home = ws.oa_resolve("Florida International Panthers", set(slate.key))  # strips to "florida"
    road = ws.oa_resolve("Buffalo Bulls", set(slate.rkey))

    assert home == "florida"
    merged = slate.merge(pd.DataFrame({"key": [home], "rkey": [road], "oa_fair_an": [-7.5]}),
                         on=["key", "rkey"], how="left")
    assert merged.oa_fair_an.isna().all()


def test_unresolvable_name_falls_through_rather_than_guessing():
    assert ws.oa_resolve("Nowhere State Ghosts", {"miami"}) == "nowhere state ghosts"


# ------------------------------------------------------------------ quotes and shopping


def test_reads_home_side_quotes_from_the_latest_snapshot(tmp_path, monkeypatch):
    write(tmp_path, snapshot([event("Marshall Thundering Herd", "Middle Tennessee Blue Raiders",
                                    {"draftkings": (-7.5, -110), "fanduel": (-7.0, -108)})]),
          monkeypatch)

    oa = ws.oddsapi_books(NOW)

    assert len(oa) == 1
    assert oa.oa_quotes.iloc[0] == {"draftkings": (-7.5, -110), "fanduel": (-7.0, -108)}
    assert oa.oa_as_of.iloc[0] == "2026-09-09T20:05:31Z"


def test_prices_outside_the_odds_window_are_dropped(tmp_path, monkeypatch):
    write(tmp_path, snapshot([event("A Team", "B Team",
                                    {"draftkings": (-7.5, -110), "betus": (-3.0, -400)})]),
          monkeypatch)

    assert ws.oddsapi_books(NOW).oa_quotes.iloc[0] == {"draftkings": (-7.5, -110)}


def test_games_outside_the_eight_day_window_are_dropped(tmp_path, monkeypatch):
    far = (NOW + timedelta(days=20)).isoformat().replace("+00:00", "Z")
    write(tmp_path, snapshot([event("A Team", "B Team", {"draftkings": (-7.5, -110)}, commence=far)]),
          monkeypatch)

    assert ws.oddsapi_books(NOW).empty


def test_missing_snapshot_dir_is_not_fatal(tmp_path, monkeypatch):
    monkeypatch.setattr(ws, "OA_SNAP_DIR", tmp_path / "absent")
    assert ws.oddsapi_books(NOW).empty


def test_shop_medians_and_bests_in_an_sign():
    out = ws.oa_shop({"a": (-7.5, -110), "b": (-7.0, -108), "c": (-8.0, -105)})

    assert out["oa_fair_an"] == -7.5 and out["oa_n_books"] == 3
    # AN sign: negative = home favored, so the MAX is the best home number.
    assert out["oa_best_home_an"] == -7.0 and out["oa_best_home_book"] == "b"
    assert out["oa_best_away_an"] == -8.0 and out["oa_best_away_book"] == "c"


def test_shop_needs_two_books():
    assert ws.oa_shop({"a": (-7.5, -110)}) == {}


def test_outlier_book_is_dropped_from_the_median():
    out = ws.oa_shop({"a": (-7.5, -110), "b": (-7.0, -110), "c": (-7.5, -110), "d": (30.0, -110)})

    assert out["oa_n_books"] == 3 and out["oa_fair_an"] == -7.5

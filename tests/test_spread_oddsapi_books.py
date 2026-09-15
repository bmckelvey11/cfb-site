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


def test_miami_fla_meets_the_feeds_on_plain_miami():
    # PT writes "Miami (Fla.)"; the-odds-api writes "Miami Hurricanes" and Pinnacle "Miami".
    # 2026 week 3 the game went unpriced because the PT key kept its "(fl)".
    key = ws.norm("Miami (Fla.)")
    assert key == "miami"
    assert ws.oa_resolve("Miami Hurricanes", {key}) == key
    assert ws.oa_resolve("Miami", {key}) == key
    assert ws.norm("Miami (Ohio)") == "miami (oh)"
    assert ws.oa_resolve("Miami (OH) RedHawks", {key, "miami (oh)"}) == "miami (oh)"


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
    # keyed by display name, not by the feed's own book key, so both feeds dedup into one dict
    assert oa.oa_quotes.iloc[0] == {"DraftKings": (-7.5, -110), "FanDuel": (-7.0, -108)}
    assert oa.oa_as_of.iloc[0] == "2026-09-09T20:05:31Z"


def test_prices_outside_the_odds_window_are_dropped(tmp_path, monkeypatch):
    write(tmp_path, snapshot([event("A Team", "B Team",
                                    {"draftkings": (-7.5, -110), "betus": (-3.0, -400)})]),
          monkeypatch)

    assert ws.oddsapi_books(NOW).oa_quotes.iloc[0] == {"DraftKings": (-7.5, -110)}


def test_games_outside_the_eight_day_window_are_dropped(tmp_path, monkeypatch):
    far = (NOW + timedelta(days=20)).isoformat().replace("+00:00", "Z")
    write(tmp_path, snapshot([event("A Team", "B Team", {"draftkings": (-7.5, -110)}, commence=far)]),
          monkeypatch)

    assert ws.oddsapi_books(NOW).empty


def test_an_unmapped_book_does_not_vote(tmp_path, monkeypatch):
    # A book that appears in the feed but not in OA_BOOKS has no display name, so it cannot be
    # deduped against Action Network's. Counting it anyway would let the same book vote twice.
    write(tmp_path, snapshot([event("A Team", "B Team",
                                    {"draftkings": (-7.5, -110), "brandnewbook": (-7.0, -110)})]),
          monkeypatch)

    assert ws.oddsapi_books(NOW).oa_quotes.iloc[0] == {"DraftKings": (-7.5, -110)}


def test_action_network_no_longer_votes():
    """Amendment S4: the fair is the-odds-api's books plus Pinnacle; Caesars left with AN."""
    assert ws.BOOK_SET_VERSION == 4
    assert set(ws.BOOKS) == set(ws.OA_BOOKS.values()) | {"Pinnacle"}
    assert "Caesars" not in ws.BOOKS


def test_live_books_carries_join_keys_and_no_prices(monkeypatch):
    """The AN scoreboard is still read for the event id version B keys its close on -- nothing else."""
    payload = {"games": [{"id": 7, "start_time": "2026-09-12T23:00:00Z",
                          "home_team_id": 1, "away_team_id": 2,
                          "teams": [{"id": 1, "display_name": "Marshall"},
                                    {"id": 2, "display_name": "Middle Tenn"}],
                          "markets": {"68": {"event": {"spread": [
                              {"side": "home", "value": -7.5, "odds": -110}]}}}}]}
    monkeypatch.setattr(ws.clt, "_get", lambda url, params=None, **kw: json.dumps(payload).encode())
    monkeypatch.setattr(ws.time, "sleep", lambda s: None)

    books = ws.live_books(NOW)

    assert list(books.event_id) == [7] and books.key.iloc[0] == "marshall"
    assert "quotes" not in books.columns


def test_missing_snapshot_dir_is_not_fatal(tmp_path, monkeypatch):
    monkeypatch.setattr(ws, "OA_SNAP_DIR", tmp_path / "absent")
    assert ws.oddsapi_books(NOW).empty


def test_shop_labels_the_best_book_by_name_not_by_feed_id():
    # shop() used to translate an Action Network id through REAL_BOOKS; with two feeds in one
    # Series the key has to already be the printable name. Caesars prices into the median but
    # cannot win either side: BETTABLE is the slip's book set, not the fair's.
    out = ws.shop({"Caesars": (-7.5, -110), "DraftKings": (-7.0, -108), "FanDuel": (-8.0, -105)})

    assert out["best_home_book"] == "DraftKings" and out["best_away_book"] == "FanDuel"
    assert out["n_books"] == 3


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


# ------------------------------------------------------------------ the book-set tag

import migrate_book_set_version as mig  # noqa: E402


def test_untagged_rows_are_stamped_as_the_pre_promotion_set():
    log = pd.DataFrame({"home": ["A", "B"], "book_fair": [-3.0, 7.0]})

    out, n = mig.migrate(log)

    assert n == 2 and (out.book_set_version == mig.PRE_PROMOTION).all()


def test_already_tagged_rows_are_left_alone():
    """Promoted rows carry version 2 and must never be relabelled as the old set."""
    log = pd.DataFrame({"home": ["A", "B"], "book_set_version": [1, 2]})

    out, n = mig.migrate(log)

    assert n == 0 and list(out.book_set_version) == [1, 2]


def test_migration_is_idempotent():
    log = pd.DataFrame({"home": ["A", "B"]})

    once, _ = mig.migrate(log)
    twice, n = mig.migrate(once)

    assert n == 0 and once.equals(twice)

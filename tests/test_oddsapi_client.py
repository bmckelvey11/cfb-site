import json

import pytest

from cfb_system_maker.oddsapi_client import (
    _redact,
    fetch_odds,
    find_odds_token,
    write_snapshot,
)

EVENT = {
    "id": "18dec56516beb8daed598bc5c7a6872d",
    "sport_key": "americanfootball_ncaaf",
    "commence_time": "2026-09-11T00:00:00Z",
    "home_team": "Miami Hurricanes",
    "away_team": "Florida A&M Rattlers",
    "bookmakers": [
        {
            "key": "fanduel",
            "title": "FanDuel",
            "last_update": "2026-09-09T19:46:36Z",
            "markets": [
                {
                    "key": "totals",
                    "last_update": "2026-09-09T19:46:35Z",
                    "outcomes": [
                        {"name": "Over", "price": -114, "point": 62.5},
                        {"name": "Under", "price": -106, "point": 62.5},
                    ],
                }
            ],
        }
    ],
}


def make_fetch(captured=None):
    """Fake the-odds-api. Returns the event list plus the quota headers."""
    def fetch(url, params):
        if captured is not None:
            captured.append((url, params))
        return [EVENT], {"x-requests-last": "3", "x-requests-used": "3", "x-requests-remaining": "497"}
    return fetch


def test_envelope_carries_snapshot_time_and_quota():
    payload = fetch_odds(token="secret", fetch_fn=make_fetch())

    assert payload["pulled_at"].endswith("Z")  # snapshot time is explicit, not implied
    assert payload["requests_last"] == 3 and payload["requests_remaining"] == 497
    assert payload["events"] == [EVENT]


def test_request_params_are_comma_joined():
    captured = []
    fetch_odds(
        token="secret", regions=("us", "us2"), markets=("h2h", "totals"),
        fetch_fn=make_fetch(captured),
    )

    url, params = captured[0]
    assert url.endswith("/sports/americanfootball_ncaaf/odds")
    assert params["regions"] == "us,us2" and params["markets"] == "h2h,totals"
    assert params["apiKey"] == "secret"


def test_write_snapshot_names_file_by_pull_time(tmp_path):
    payload = fetch_odds(token="secret", fetch_fn=make_fetch())
    path = write_snapshot(payload, tmp_path)

    assert path.parent == tmp_path
    assert path.name.startswith("odds_americanfootball_ncaaf_")
    assert json.loads(path.read_text(encoding="utf-8"))["events"] == [EVENT]


def test_redact_strips_the_key_from_error_text():
    # The key rides in a query param on this API, so it reaches error bodies.
    assert _redact("bad key sk-123 in ?apiKey=sk-123", "sk-123") == "bad key *** in ?apiKey=***"


def test_find_odds_token_reads_env_file(tmp_path, monkeypatch):
    monkeypatch.delenv("ODDS_API", raising=False)
    monkeypatch.delenv("ODDS_API_KEY", raising=False)
    env = tmp_path / "env.env"
    env.write_text("PFF_API=other\n\nODDS_API=abc123\n", encoding="utf-8")

    assert find_odds_token(env) == "abc123"
    with pytest.raises(RuntimeError):
        find_odds_token(tmp_path / "missing.env")

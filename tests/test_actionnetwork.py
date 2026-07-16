import json

from cfb_system_maker.actionnetwork_client import actionnetwork_scrape


def make_fetch(games_by_week, captured=None):
    """Fake Action Network API. Scoreboard returns games for a (season, week);
    history returns a per-book payload keyed by the requested event id."""
    def fetch(url, params):
        if captured is not None:
            captured.append((url, params))
        if "scoreboard" in url:
            return {"games": games_by_week.get(params["week"], [])}
        event_id = url.rstrip("/").split("/")[-2]  # .../event/{id}/history
        return {"15": {"firsthalf": {"spread": [{"event_id": int(event_id)}]}}}
    return fetch


def test_scoreboard_and_history_files(tmp_path):
    games = {1: [{"id": 100}, {"id": 101}], 2: [{"id": 200}]}
    reports = actionnetwork_scrape(
        [2025], data_dir=tmp_path, weeks=range(1, 3), delay=0, fetch_fn=make_fetch(games)
    )

    raw = tmp_path / "raw" / "actionnetwork"
    assert (raw / "scoreboard_2025_wk1.json").exists()
    assert (raw / "history_100.json").exists()
    assert (raw / "history_200.json").exists()

    by = {r.name: r for r in reports}
    assert by["scoreboard_2025"].files == 2 and by["scoreboard_2025"].events == 3
    assert by["history_2025"].files == 3 and by["history_2025"].error is None


def test_periods_passed_to_history(tmp_path):
    captured = []
    games = {1: [{"id": 100}]}
    actionnetwork_scrape(
        [2025], data_dir=tmp_path, weeks=range(1, 2), delay=0,
        periods=("firsthalf", "firstquarter"), fetch_fn=make_fetch(games, captured),
    )

    hist = [p for url, p in captured if "history" in url][0]
    assert hist["periods"] == "firsthalf,firstquarter"


def test_empty_week_writes_no_file(tmp_path):
    games = {1: [{"id": 100}], 2: []}  # week 2 has no games
    reports = actionnetwork_scrape(
        [2025], data_dir=tmp_path, weeks=range(1, 3), delay=0, fetch_fn=make_fetch(games)
    )

    raw = tmp_path / "raw" / "actionnetwork"
    assert (raw / "scoreboard_2025_wk1.json").exists()
    assert not (raw / "scoreboard_2025_wk2.json").exists()
    assert {r.name: r for r in reports}["scoreboard_2025"].files == 1


def test_resume_skips_existing(tmp_path):
    games = {1: [{"id": 100}]}
    actionnetwork_scrape([2025], data_dir=tmp_path, weeks=range(1, 2), delay=0, fetch_fn=make_fetch(games))
    reports = actionnetwork_scrape([2025], data_dir=tmp_path, weeks=range(1, 2), delay=0, fetch_fn=make_fetch(games))

    by = {r.name: r for r in reports}
    assert by["scoreboard_2025"].skipped == 1 and by["scoreboard_2025"].files == 0
    assert by["history_2025"].skipped == 1 and by["history_2025"].files == 0


def test_only_history_reads_ids_from_disk(tmp_path):
    games = {1: [{"id": 100}, {"id": 101}]}
    actionnetwork_scrape([2025], data_dir=tmp_path, weeks=range(1, 2), delay=0,
                         only={"scoreboard"}, fetch_fn=make_fetch(games))
    reports = actionnetwork_scrape([2025], data_dir=tmp_path, weeks=range(1, 2), delay=0,
                                   only={"history"}, fetch_fn=make_fetch(games))

    raw = tmp_path / "raw" / "actionnetwork"
    assert (raw / "history_100.json").exists() and (raw / "history_101.json").exists()
    assert {r.name: r for r in reports}["history_2025"].files == 2

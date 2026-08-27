from cfb_system_maker.web import create_app


def test_betlog_page_renders_empty_state(tmp_path):
    app = create_app(data_dir=tmp_path)
    client = app.test_client()
    resp = client.get("/betlog")
    assert resp.status_code == 200
    assert b"No bets imported yet" in resp.data


def test_betlog_page_renders_bets_with_clv(tmp_path, monkeypatch):
    import json

    from cfb_system_maker.betlog import BetLogRecord, save_betlog

    bet = BetLogRecord(
        game_id=1, date="2023-09-01", home_team="San Diego State", away_team="Ohio",
        bet_type="spread", side="away", line_taken=4.0, odds=-110,
        result="win", units_wagered=1.0, units_net=0.91,
    )
    save_betlog([bet], tmp_path)

    raw_dir = tmp_path / "raw"
    raw_dir.mkdir()
    # spread is home-relative (San Diego State, the home team, favored by 2):
    # away-relative for Ohio's side that's +2.0, smaller than the +4.0 our
    # bettor took, so our bettor got the better number -- CLV positive.
    lines_data = [{"id": 1, "season": 2023, "lines": [{"provider": "consensus", "spread": -2.0}]}]
    (raw_dir / "lines_2023.json").write_text(json.dumps(lines_data))

    app = create_app(data_dir=tmp_path)
    client = app.test_client()
    resp = client.get("/betlog")

    assert resp.status_code == 200
    assert b"San Diego State" in resp.data
    assert b"Ohio" in resp.data
    # closing_side_relative = -(-2.0) = 2.0 (away terms); CLV = 4.0 - 2.0 = 2.0
    assert b"2.0" in resp.data
    # CLV is positive, so the cell must carry the .positive color class --
    # this discriminates from a broken compute_clv in a way the substring
    # check above (matched by the closing-line cell too) cannot.
    assert b'class="positive"' in resp.data


def test_betlog_page_shows_bets_missing_closing_line_separately(tmp_path):
    from cfb_system_maker.betlog import BetLogRecord, save_betlog

    bet = BetLogRecord(
        game_id=999, date="2023-09-01", home_team="Nowhere", away_team="Nobody",
        bet_type="spread", side="away", line_taken=4.0, odds=-110,
        result="win", units_wagered=1.0, units_net=0.91,
    )
    save_betlog([bet], tmp_path)  # no lines_2023.json at all -- no closing line available

    app = create_app(data_dir=tmp_path)
    client = app.test_client()
    resp = client.get("/betlog")
    assert resp.status_code == 200
    assert b"CLV not available" in resp.data


def test_dashboard_links_to_betlog(tmp_path):
    app = create_app(data_dir=tmp_path)
    client = app.test_client()
    resp = client.get("/")
    assert resp.status_code == 200
    assert b'href="/betlog"' in resp.data

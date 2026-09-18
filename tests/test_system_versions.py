from cfb_system_maker.storage import list_versions, next_version_name, save_system, version_family
from cfb_system_maker.models import SystemFilter


def test_bare_name_is_v1_of_its_own_family():
    assert version_family("sec-primetime-unders") == ("sec-primetime-unders", 1)


def test_version_suffix_splits_off():
    assert version_family("sec-primetime-unders-v2") == ("sec-primetime-unders", 2)


def test_digits_in_the_name_are_not_a_version():
    assert version_family("week-3-unders") == ("week-3-unders", 1)


def test_next_version_counts_from_the_highest_not_the_count():
    # v2 deleted: the next save must not reuse its name.
    assert next_version_name("base", ["base", "base-v3", "other"]) == "base-v4"


def test_next_version_of_a_version_stays_in_the_family():
    assert next_version_name("base-v3", ["base", "base-v3"]) == "base-v4"


def test_versions_sort_numerically(tmp_path):
    system = SystemFilter(bet_type="spread", side="home")
    for name in ("base", "base-v2", "base-v10", "other"):
        save_system(name, system, tmp_path)
    assert list_versions("base", tmp_path) == ["base", "base-v2", "base-v10"]


def _app_with_data(tmp_path):
    from cfb_system_maker.normalize import normalize_games
    from cfb_system_maker.sample_data import SAMPLE_GAMES_2023, SAMPLE_LINES_2023
    from cfb_system_maker.storage import save_processed_games
    from cfb_system_maker.web import create_app

    save_processed_games(tmp_path, normalize_games(SAMPLE_GAMES_2023, SAMPLE_LINES_2023, provider="consensus"))
    return create_app(tmp_path)


def test_save_version_writes_the_next_version_and_loads_it(tmp_path):
    app = _app_with_data(tmp_path)
    save_system("home-favs", SystemFilter(side="home", favorite=True), tmp_path)

    response = app.test_client().post("/save-version", data={"save_name": "home-favs", "side": "home"})

    assert (tmp_path / "systems" / "home-favs-v2.json").exists()
    assert "load_system=home-favs-v2" in response.headers["Location"]


def test_save_version_without_a_name_reports_the_error(tmp_path):
    app = _app_with_data(tmp_path)
    response = app.test_client().post("/save-version", data={"save_name": "  "})
    assert "save_error=missing_name" in response.headers["Location"]


def test_compare_family_selects_every_version(tmp_path):
    app = _app_with_data(tmp_path)
    save_system("home-favs", SystemFilter(side="home", favorite=True), tmp_path)
    save_system("home-favs-v2", SystemFilter(side="home", favorite=True, min_spread=-7), tmp_path)
    save_system("away-dogs", SystemFilter(side="away", underdog=True), tmp_path)

    html = app.test_client().get("/compare?family=home-favs").get_data(as_text=True)

    assert "What differs" in html
    # The version's own filter shows as a difference; the shared one does not.
    assert "the spread is at least -7" in html
    assert "Same in all (1)" in html
    assert "the team is a favorite" in html


def test_compare_family_does_not_pull_in_other_systems(tmp_path):
    app = _app_with_data(tmp_path)
    save_system("home-favs", SystemFilter(side="home", favorite=True), tmp_path)
    save_system("away-dogs", SystemFilter(side="away", underdog=True), tmp_path)

    html = app.test_client().get("/compare?family=home-favs").get_data(as_text=True)

    # away-dogs still appears in the picker checkbox list, never as a column.
    assert "<th>away-dogs</th>" not in html


def test_diff_labels_resolve_feature_keys_through_the_registry():
    from cfb_system_maker.web import _humanize_sentence_key

    # Registry label, not the vendor spelling that lives in the sentence key.
    assert _humanize_sentence_key("ff:conferenceGame") == "Conference Game"
    # Perspective survives, so bet-side and opponent rows stay distinguishable.
    assert (
        _humanize_sentence_key("ff:pregame_win_prob@bet_side")
        == "Team Win Probability (pregame) — Bet-side"
    )
    # Core filters are sentence-cased to match.
    assert _humanize_sentence_key("spread_range") == "Spread range"
    # An unknown feature falls back to its key rather than raising.
    assert _humanize_sentence_key("ff:not_a_feature") == "not_a_feature"

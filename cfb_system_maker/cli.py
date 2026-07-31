from __future__ import annotations

import argparse
import sys
from pathlib import Path

from cfb_system_maker.backtest import run_backtest, sign_consistency, split_holdout
from cfb_system_maker.cfbd_client import fetch_games_and_lines
from cfb_system_maker.enrich import load_features, run_enrich
from cfb_system_maker.models import BacktestResult, SystemFilter
from cfb_system_maker.normalize import normalize_games
from cfb_system_maker.sample_data import SAMPLE_GAMES_2023, SAMPLE_LINES_2023
from cfb_system_maker.scrapers import scrape
from cfb_system_maker.search import beam_search, grade_finalists
from cfb_system_maker.graphql_client import graphql_scrape, pull_game_player_stats
from cfb_system_maker.actionnetwork_client import actionnetwork_scrape
from cfb_system_maker.storage import load_processed_games, load_raw_json, load_system, save_processed_games, save_raw_json, save_system
from cfb_system_maker.upcoming import build_upcoming


def main(argv: list[str] | None = None) -> int:
    parser = _build_parser()
    args = parser.parse_args(argv)
    if args.command == "sample":
        return _sample(args)
    if args.command == "fetch":
        return _fetch(args)
    if args.command == "build":
        return _build(args)
    if args.command == "enrich":
        return _enrich(args)
    if args.command == "upcoming":
        return _upcoming(args)
    if args.command == "scrape":
        return _scrape(args)
    if args.command == "graphql":
        return _graphql(args)
    if args.command == "actionnetwork":
        return _actionnetwork(args)
    if args.command == "backtest":
        return _backtest(args)
    if args.command == "search":
        return _search(args)
    if args.command == "web":
        return _web(args)
    parser.print_help()
    return 1


def _sample(args: argparse.Namespace) -> int:
    data_dir = Path(args.data_dir)
    save_raw_json(data_dir, "games", 2023, SAMPLE_GAMES_2023)
    save_raw_json(data_dir, "lines", 2023, SAMPLE_LINES_2023)
    games = normalize_games(SAMPLE_GAMES_2023, SAMPLE_LINES_2023, provider="consensus")
    save_processed_games(data_dir, games)

    print("Sample data written.")
    print_result("Home favorites", run_backtest(games, SystemFilter(side="home", favorite=True)))
    print_result("Away underdogs", run_backtest(games, SystemFilter(side="away", underdog=True, min_spread=3)))
    return 0


def _fetch(args: argparse.Namespace) -> int:
    data = fetch_games_and_lines(args.seasons, season_type=args.season_type, provider=args.provider)
    for season, payload in data.items():
        save_raw_json(args.data_dir, "games", season, payload["games"])
        save_raw_json(args.data_dir, "lines", season, payload["lines"])
    print(f"Fetched {len(data)} season(s).")
    return 0


def _build(args: argparse.Namespace) -> int:
    records = []
    for season in args.seasons:
        games = load_raw_json(args.data_dir, "games", season)
        lines = load_raw_json(args.data_dir, "lines", season)
        records.extend(normalize_games(games, lines, provider=args.provider))
    save_processed_games(args.data_dir, records)
    print(f"Built processed table with {len(records)} game(s).")
    return 0


def _enrich(args: argparse.Namespace) -> int:
    path = run_enrich(args.data_dir)
    print(f"Wrote enriched features to {path}")
    return 0


def _upcoming(args: argparse.Namespace) -> int:
    result = build_upcoming(args.data_dir)
    meta = result.meta
    if meta["season"] is None:
        print("No upcoming data available: no week with games could be resolved.")
        return 0
    print(f"Resolved {meta['season']} {meta['season_type']} week {meta['week']} ({meta['row_count']} game(s)).")
    if meta["is_fallback"]:
        print(
            "No current week had data; fell back to the most recent week with games "
            f"({meta['season']} {meta['season_type']} week {meta['week']})."
        )
    return 0


def _scrape(args: argparse.Namespace) -> int:
    reports = scrape(
        args.seasons,
        data_dir=args.data_dir,
        season_type=args.season_type,
        include_per_game=args.include_per_game,
        include_per_player=args.include_per_player,
        only=set(args.only) if args.only else None,
        delay=args.delay,
        resume=not args.force,
        fbs_only=args.fbs_only,
    )
    ok = [r for r in reports if r.error is None]
    failed = [r for r in reports if r.error is not None]
    for report in ok:
        skip = f"  ({report.skipped} skipped)" if report.skipped else ""
        print(f"{report.name:28} {report.files:>4} file(s)  {report.rows:>7} rows{skip}")
    for report in failed:
        print(f"{report.name:28} FAILED  {report.error}")
    total_skipped = sum(r.skipped for r in reports)
    print(f"\n{len(ok)} endpoint(s) scraped, {len(failed)} failed, {total_skipped} file(s) skipped.")
    return 1 if failed and not ok else 0


def _graphql(args: argparse.Namespace) -> int:
    if args.game_player_stats:
        if not args.seasons:
            print("--game-player-stats requires --season")
            return 1
        reports = pull_game_player_stats(
            args.seasons, data_dir=args.data_dir, page_size=args.page_size, resume=not args.force
        )
    else:
        reports = graphql_scrape(
            data_dir=args.data_dir,
            seasons=args.seasons,
            page_size=args.page_size,
            only=set(args.only) if args.only else None,
        )
    ok = [r for r in reports if r.error is None]
    failed = [r for r in reports if r.error is not None]
    for report in ok:
        if report.skipped:
            print(f"{report.name:28} skipped (exists)")
        else:
            print(f"{report.name:28} {report.rows:>8} rows  {report.pages:>3} page(s)")
    for report in failed:
        print(f"{report.name:28} FAILED  {report.error}")
    print(f"\n{len(ok)} table(s) pulled, {len(failed)} failed.")
    return 1 if failed and not ok else 0


def _actionnetwork(args: argparse.Namespace) -> int:
    reports = actionnetwork_scrape(
        args.seasons,
        data_dir=args.data_dir,
        season_type=args.season_type,
        periods=tuple(args.periods),
        only=set(args.only) if args.only else None,
        delay=args.delay,
        resume=not args.force,
    )
    for report in reports:
        notes = []
        if report.skipped:
            notes.append(f"{report.skipped} skipped")
        if report.errors:
            notes.append(f"{report.errors} errors")
        note = f"  ({', '.join(notes)})" if notes else ""
        print(f"{report.name:20} {report.files:>4} file(s)  {report.events:>5} event(s){note}")
        if report.error:
            print(f"{'':20} last: {report.error}")
    total_errors = sum(r.errors for r in reports)
    print(f"\n{len(reports)} stage(s), {total_errors} per-item error(s).")
    return 0


def _backtest(args: argparse.Namespace) -> int:
    games = load_processed_games(args.data_dir)
    if args.load:
        system = load_system(args.load, args.data_dir)
    else:
        system = SystemFilter(
            bet_type=args.bet_type,
            side=args.side,
            total_side=args.total_side,
            seasons=set(args.season or []),
            weeks=set(args.week or []),
            teams=set(args.team or []),
            conferences=set(args.conference or []),
            providers=set(args.provider or []),
            favorite=args.favorite,
            underdog=args.underdog,
            home=args.home,
            away=args.away,
            fade=args.fade,
            min_spread=args.min_spread,
            max_spread=args.max_spread,
            min_total=args.min_total,
            max_total=args.max_total,
        )
    feature_map = {}
    try:
        from cfb_system_maker.enrich import load_features

        feature_map = load_features(args.data_dir)
    except FileNotFoundError:
        pass
    label = args.load or "Custom system"
    if args.holdout_seasons:
        available_seasons = {game.season for game in games}
        in_sample, holdout = split_holdout(system, set(args.holdout_seasons), available_seasons)
        in_result = run_backtest(games, in_sample, feature_map=feature_map)
        holdout_result = run_backtest(games, holdout, feature_map=feature_map)
        print_result(f"{label} (in-sample)", in_result)
        print_result(f"{label} (holdout)", holdout_result)
    else:
        result = run_backtest(games, system, feature_map=feature_map)
        print_result(label, result)
    if args.save:
        save_system(args.save, system, args.data_dir)
        print(f"Saved system as {args.save}")
    return 0


def _search(args: argparse.Namespace) -> int:
    try:
        games = load_processed_games(args.data_dir)
    except FileNotFoundError:
        print("error=missing_data", file=sys.stderr)
        print("No built games table found. Run `build` (after `fetch`) first.", file=sys.stderr)
        return 1

    # Deliberately stricter than _backtest, which silently falls back to an empty
    # feature_map on FileNotFoundError. search has no core-filter-only fallback --
    # a missing sidecar is a hard error, not a silent degrade (MVP-005 AC).
    try:
        feature_map = load_features(args.data_dir)
    except FileNotFoundError:
        print("error=missing_features", file=sys.stderr)
        print("No enriched features found. Run `enrich` first.", file=sys.stderr)
        return 1

    available_seasons = {game.season for game in games}
    if args.holdout_season not in available_seasons:
        print("error=unknown_holdout_season", file=sys.stderr)
        print(f"--holdout-season {args.holdout_season} is not present in the built data.", file=sys.stderr)
        return 1
    if args.season:
        unknown = set(args.season) - available_seasons
        if unknown:
            print("error=unknown_season", file=sys.stderr)
            print(f"--season value(s) not present in the built data: {sorted(unknown)}", file=sys.stderr)
            return 1

    # --season scope applied first, then the holdout split -- order matches spec.
    scoped_seasons = set(args.season) if args.season else available_seasons
    holdout_seasons = {args.holdout_season} & scoped_seasons
    in_sample_seasons = scoped_seasons - holdout_seasons

    in_sample_games = [g for g in games if g.season in in_sample_seasons]
    holdout_games = [g for g in games if g.season in holdout_seasons]

    # Guard on actual game membership, not just season-label sets -- a season label
    # can be non-empty while matching zero real games (e.g. --season on a season
    # with no built rows), which the label-only check would silently miss.
    if not in_sample_games:
        print("error=empty_in_sample", file=sys.stderr)
        print("No in-sample games remain after applying --season scope and the holdout split.", file=sys.stderr)
        return 1
    if not holdout_games:
        print("error=empty_holdout", file=sys.stderr)
        print(f"--holdout-season {args.holdout_season} has no games after --season scope; nothing to grade on.", file=sys.stderr)
        return 1

    for name, value in (
        ("--max-filters", args.max_filters),
        ("--beam-width", args.beam_width),
        ("--top-k", args.top_k),
        ("--min-decided-bets", args.min_decided_bets),
    ):
        if value < 1:
            print("error=invalid_search_params", file=sys.stderr)
            print(f"{name} must be at least 1 (got {value}).", file=sys.stderr)
            return 1

    in_sample_game_ids = {g.game_id for g in in_sample_games}
    holdout_game_ids = {g.game_id for g in holdout_games}
    in_sample_feature_map = {gid: row for gid, row in feature_map.items() if gid in in_sample_game_ids}
    holdout_feature_map = {gid: row for gid, row in feature_map.items() if gid in holdout_game_ids}

    seed = SystemFilter(bet_type=args.bet_type)
    try:
        beam_result = beam_search(
            in_sample_games,
            in_sample_feature_map,
            seed=seed,
            beam_width=args.beam_width,
            top_k=args.top_k,
            min_decided_bets=args.min_decided_bets,
            alpha=args.alpha,
            max_dimensions=args.max_filters,
        )
    except ValueError as exc:
        print("error=invalid_search_params", file=sys.stderr)
        print(str(exc), file=sys.stderr)
        return 1

    grading = grade_finalists(beam_result, holdout_games, holdout_feature_map, alpha=args.alpha)

    print(f"beam_width={beam_result.effective_params['beam_width']}")
    print(f"top_k={beam_result.effective_params['top_k']}")
    print(f"min_decided_bets={beam_result.effective_params['min_decided_bets']}")
    print(f"alpha={beam_result.effective_params['alpha']}")
    print(f"search_candidates_tested={beam_result.candidates_tested}")
    print(f"finalists_graded={grading.finalists_graded}")
    for finalist in grading.finalists:
        result = finalist.holdout_result
        print(
            f"  bets={result.bets} roi={result.roi:.4f} "
            f"raw_p={finalist.raw_p:.4f} corrected_p={finalist.corrected_p:.4f} "
            f"bh_significant={finalist.bh_significant}"
        )

    if args.save:
        if not grading.finalists:
            print("error=nothing_to_save", file=sys.stderr)
            print("--save requested but no finalists survived grading.", file=sys.stderr)
            return 1
        # Ranked order is preserved from beam_result.survivors -> grading.finalists,
        # i.e. by IN-SAMPLE wilson_low/roi (grade_finalists never re-ranks by holdout
        # results -- that would be leakage). The finalist saved here may not be the
        # one with the best-looking holdout roi/corrected_p printed above; naming its
        # index and holdout stats makes that explicit instead of silently implying
        # "the best line above" was picked.
        top_finalist = grading.finalists[0]
        save_system(
            args.save,
            top_finalist.system,
            args.data_dir,
            source="search",
            search_candidates_tested=beam_result.candidates_tested,
        )
        print(
            f"Saved system as {args.save} (finalist #1 of {grading.finalists_graded}, "
            f"holdout roi={top_finalist.holdout_result.roi:.4f} "
            f"corrected_p={top_finalist.corrected_p:.4f} "
            f"bh_significant={top_finalist.bh_significant})"
        )

    return 0


def _web(args: argparse.Namespace) -> int:
    from cfb_system_maker.web import create_app

    app = create_app(data_dir=args.data_dir)
    app.run(host=args.host, port=args.port, debug=args.debug)
    return 0


def print_result(name: str, result: BacktestResult) -> None:
    print(f"\n{name}")
    print(f"Bets: {result.bets}")
    print(f"Wins: {result.wins}")
    print(f"Losses: {result.losses}")
    print(f"Pushes: {result.pushes}")
    print(f"Hit rate: {result.hit_rate:.2%}")
    print(f"Profit: {result.profit:.4f} units")
    print(f"ROI: {result.roi:.2%}")
    if result.average_line is not None:
        print(f"Average line: {result.average_line:.2f}")
    if result.season_breakdown:
        print("Per-season breakdown:")
        for record in result.season_breakdown:
            print(f"  {record.season}: {record.wins}-{record.losses}-{record.pushes}  ROI {record.roi:.2%}")
        profitable, total = sign_consistency(result.season_breakdown)
        print(f"Profitable in {profitable}/{total} seasons")
    if result.stats:
        stats = result.stats
        print(f"Break-even: {stats.break_even_rate:.2%}")
        print(f"Edge: {stats.edge:.2%}")
        print(f"Wilson CI: {stats.wilson_low:.2%} - {stats.wilson_high:.2%}")
        print(f"p-value: {stats.p_value:.4f}")
        print(f"Permutation p-value: {stats.permutation_p_value:.4f}")
        print(f"Longest streaks: W{stats.max_win_streak} / L{stats.max_loss_streak}")
        if stats.low_sample:
            print("Low sample warning (<30 decided bets)")


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="cfb-system-maker")
    subparsers = parser.add_subparsers(dest="command")

    sample = subparsers.add_parser("sample")
    sample.add_argument("--data-dir", default="data")

    fetch = subparsers.add_parser("fetch")
    fetch.add_argument("--data-dir", default="data")
    fetch.add_argument("--season", dest="seasons", type=int, nargs="+", required=True)
    fetch.add_argument("--season-type", default="regular")
    fetch.add_argument("--provider")

    build = subparsers.add_parser("build")
    build.add_argument("--data-dir", default="data")
    build.add_argument("--season", dest="seasons", type=int, nargs="+", required=True)
    build.add_argument("--provider", default="consensus")

    enrich = subparsers.add_parser("enrich")
    enrich.add_argument("--data-dir", default="data")

    upcoming = subparsers.add_parser("upcoming")
    upcoming.add_argument("--data-dir", default="data")

    scrape_parser = subparsers.add_parser("scrape")
    scrape_parser.add_argument("--data-dir", default="data")
    scrape_parser.add_argument("--season", dest="seasons", type=int, nargs="+", required=True)
    scrape_parser.add_argument("--season-type", default="regular")
    scrape_parser.add_argument("--include-per-game", action="store_true")
    scrape_parser.add_argument("--include-per-player", action="store_true")
    scrape_parser.add_argument("--only", nargs="+")
    scrape_parser.add_argument("--delay", type=float, default=1.0, help="seconds between API calls")
    scrape_parser.add_argument("--force", action="store_true", help="re-scrape even if output file exists")
    scrape_parser.add_argument("--fbs-only", action="store_true", help="per-game endpoints: only FBS games")

    graphql_parser = subparsers.add_parser("graphql")
    graphql_parser.add_argument("--data-dir", default="data")
    graphql_parser.add_argument("--season", dest="seasons", type=int, nargs="+")
    graphql_parser.add_argument("--only", nargs="+")
    graphql_parser.add_argument("--page-size", type=int, default=1000)
    graphql_parser.add_argument("--game-player-stats", action="store_true",
                                help="bespoke labeled player-game stats, one file per --season")
    graphql_parser.add_argument("--force", action="store_true", help="re-pull even if season file exists")

    an = subparsers.add_parser("actionnetwork")
    an.add_argument("--data-dir", default="data")
    an.add_argument("--season", dest="seasons", type=int, nargs="+", required=True)
    an.add_argument("--season-type", default="reg")
    an.add_argument("--periods", nargs="+", default=["firsthalf", "firstquarter"],
                    help="event/firsthalf/secondhalf/firstquarter..fourthquarter")
    an.add_argument("--only", nargs="+", help="scoreboard and/or history")
    an.add_argument("--delay", type=float, default=1.0, help="seconds between API calls")
    an.add_argument("--force", action="store_true", help="re-scrape even if output file exists")

    backtest = subparsers.add_parser("backtest")
    backtest.add_argument("--data-dir", default="data")
    backtest.add_argument("--bet-type", choices=["spread", "total"], default="spread")
    backtest.add_argument("--side", choices=["home", "away"], default="home")
    backtest.add_argument("--total-side", choices=["over", "under"], default="over")
    backtest.add_argument("--season", type=int, action="append")
    backtest.add_argument("--week", type=int, action="append")
    backtest.add_argument("--team", action="append")
    backtest.add_argument("--conference", action="append")
    backtest.add_argument("--provider", action="append")
    backtest.add_argument("--favorite", action="store_true")
    backtest.add_argument("--underdog", action="store_true")
    backtest.add_argument("--home", action="store_true")
    backtest.add_argument("--away", action="store_true")
    backtest.add_argument("--fade", action="store_true")
    backtest.add_argument("--min-spread", type=float)
    backtest.add_argument("--max-spread", type=float)
    backtest.add_argument("--min-total", type=float)
    backtest.add_argument("--max-total", type=float)
    backtest.add_argument("--save")
    backtest.add_argument("--load")
    backtest.add_argument("--holdout-season", dest="holdout_seasons", type=int, action="append")

    search = subparsers.add_parser("search")
    search.add_argument("--data-dir", default="data")
    search.add_argument("--holdout-season", type=int, required=True)
    search.add_argument("--season", type=int, action="append")
    search.add_argument("--max-filters", type=int, default=4)
    search.add_argument("--bet-type", choices=["spread", "total"], default="spread")
    search.add_argument("--beam-width", type=int, default=100)
    search.add_argument("--top-k", type=int, default=20)
    search.add_argument("--min-decided-bets", type=int, default=100)
    search.add_argument("--alpha", type=float, default=0.05)
    search.add_argument("--save", help="save the top-ranked finalist under this name")

    web = subparsers.add_parser("web")
    web.add_argument("--data-dir", default="data")
    web.add_argument("--host", default="127.0.0.1")
    web.add_argument("--port", type=int, default=5000)
    web.add_argument("--debug", action="store_true")

    return parser

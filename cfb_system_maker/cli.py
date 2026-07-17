from __future__ import annotations

import argparse
from pathlib import Path

from cfb_system_maker.backtest import run_backtest, sign_consistency
from cfb_system_maker.cfbd_client import fetch_games_and_lines
from cfb_system_maker.enrich import run_enrich
from cfb_system_maker.models import BacktestResult, SystemFilter
from cfb_system_maker.normalize import normalize_games
from cfb_system_maker.sample_data import SAMPLE_GAMES_2023, SAMPLE_LINES_2023
from cfb_system_maker.scrapers import scrape
from cfb_system_maker.graphql_client import graphql_scrape, pull_game_player_stats
from cfb_system_maker.actionnetwork_client import actionnetwork_scrape
from cfb_system_maker.storage import load_processed_games, load_raw_json, load_system, save_processed_games, save_raw_json, save_system


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
    if args.command == "scrape":
        return _scrape(args)
    if args.command == "graphql":
        return _graphql(args)
    if args.command == "actionnetwork":
        return _actionnetwork(args)
    if args.command == "backtest":
        return _backtest(args)
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
    result = run_backtest(games, system, feature_map=feature_map)
    label = args.load or "Custom system"
    print_result(label, result)
    if args.save:
        save_system(args.save, system, args.data_dir)
        print(f"Saved system as {args.save}")
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
    backtest.add_argument("--min-spread", type=float)
    backtest.add_argument("--max-spread", type=float)
    backtest.add_argument("--min-total", type=float)
    backtest.add_argument("--max-total", type=float)
    backtest.add_argument("--save")
    backtest.add_argument("--load")

    web = subparsers.add_parser("web")
    web.add_argument("--data-dir", default="data")
    web.add_argument("--host", default="127.0.0.1")
    web.add_argument("--port", type=int, default=5000)
    web.add_argument("--debug", action="store_true")

    return parser

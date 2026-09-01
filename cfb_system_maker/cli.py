from __future__ import annotations

import argparse
import logging
import os
import sys
from pathlib import Path

from cfb_paths import DATA_ROOT
from cfb_system_maker.backtest import run_backtest, sign_consistency, split_holdout
from cfb_system_maker.betlog import import_betlog
from cfb_system_maker.cfbd_client import fetch_games_and_lines
from cfb_system_maker.enrich import load_features, run_enrich
from cfb_system_maker.models import BacktestResult, SystemFilter
from cfb_system_maker.normalize import normalize_games
from cfb_system_maker.sample_data import SAMPLE_GAMES_2023, SAMPLE_LINES_2023
from cfb_system_maker.scrapers import scrape
from cfb_system_maker.search import beam_search, grade_finalists
from cfb_system_maker.graphql_client import graphql_scrape, pull_game_player_stats
from cfb_system_maker.actionnetwork_client import actionnetwork_scrape
from cfb_system_maker.duckdb_core import build_core
from cfb_system_maker.duckdb_load import (
    TableLoad,
    build_duckdb,
    explode_payloads,
    explode_stg_lists,
    flatten_stg_nested,
    promote_timestamp_columns,
    rename_stg_id_columns,
    reorder_stg_columns,
)
from cfb_system_maker.storage import (
    load_processed_games,
    load_raw_json,
    load_system,
    save_processed_games,
    save_raw_json,
    save_system,
)
from cfb_system_maker.upcoming import build_upcoming
from cfb_system_maker.v1_model import fit_v1, save_v1_fit

DATA_DIR_DEFAULT = str(DATA_ROOT)


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
    if args.command == "refit-v1":
        return _refit_v1(args)
    if args.command == "upcoming":
        return _upcoming(args)
    if args.command == "scrape":
        return _scrape(args)
    if args.command == "graphql":
        return _graphql(args)
    if args.command == "actionnetwork":
        return _actionnetwork(args)
    if args.command == "betlog" and args.betlog_command == "import":
        return _betlog_import(args)
    if args.command == "backtest":
        return _backtest(args)
    if args.command == "search":
        return _search(args)
    if args.command == "web":
        return _web(args)
    if args.command == "duckdb":
        return _duckdb(args)
    parser.print_help()
    return 1


def _sample(args: argparse.Namespace) -> int:
    data_dir = Path(args.data_dir)
    save_raw_json(data_dir, "games", 2023, SAMPLE_GAMES_2023)
    save_raw_json(data_dir, "lines", 2023, SAMPLE_LINES_2023)
    games = normalize_games(SAMPLE_GAMES_2023, SAMPLE_LINES_2023, provider="consensus")
    save_processed_games(data_dir, games)

    print("Sample data written.")
    print_result(
        "Home favorites", run_backtest(games, SystemFilter(side="home", favorite=True))
    )
    print_result(
        "Away underdogs",
        run_backtest(games, SystemFilter(side="away", underdog=True, min_spread=3)),
    )
    return 0


def _fetch(args: argparse.Namespace) -> int:
    data = fetch_games_and_lines(
        args.seasons, season_type=args.season_type, provider=args.provider
    )
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


def _refit_v1(args: argparse.Namespace) -> int:
    games = load_processed_games(args.data_dir)
    fit = fit_v1(games)
    path = save_v1_fit(args.data_dir, fit)
    print(f"Fit v1 model on {fit.n_games} game(s); wrote {path}")
    print(
        "Run `enrich` (and `upcoming`, if used) again to refresh v1_over_prob with the new fit."
    )
    return 0


def _upcoming(args: argparse.Namespace) -> int:
    result = build_upcoming(args.data_dir)
    meta = result.meta
    if meta["season"] is None:
        print("No upcoming data available: no week with games could be resolved.")
        return 0
    print(
        f"Resolved {meta['season']} {meta['season_type']} week {meta['week']} ({meta['row_count']} game(s))."
    )
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
        print(
            f"{report.name:28} {report.files:>4} file(s)  {report.rows:>7} rows{skip}"
        )
    for report in failed:
        print(f"{report.name:28} FAILED  {report.error}")
    total_skipped = sum(r.skipped for r in reports)
    print(
        f"\n{len(ok)} endpoint(s) scraped, {len(failed)} failed, {total_skipped} file(s) skipped."
    )
    return 1 if failed and not ok else 0


def _graphql(args: argparse.Namespace) -> int:
    if args.game_player_stats:
        if not args.seasons:
            print("--game-player-stats requires --season")
            return 1
        reports = pull_game_player_stats(
            args.seasons,
            data_dir=args.data_dir,
            page_size=args.page_size,
            resume=not args.force,
        )
    else:
        reports = graphql_scrape(
            data_dir=args.data_dir,
            seasons=args.seasons,
            page_size=args.page_size,
            tables=args.tables,
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
        print(
            f"{report.name:20} {report.files:>4} file(s)  {report.events:>5} event(s){note}"
        )
        if report.error:
            print(f"{'':20} last: {report.error}")
    total_errors = sum(r.errors for r in reports)
    print(f"\n{len(reports)} stage(s), {total_errors} per-item error(s).")
    return 0


def _betlog_import(args: argparse.Namespace) -> int:
    summary = import_betlog(args.csv, args.data_dir)
    print(
        f"{summary.total_rows} rows in CSV, {summary.in_scope} in scope (spread/total, pre-game)"
    )
    print(f"{summary.already_imported} already imported, {summary.newly_imported} new")
    print(
        f"{summary.matched} matched to CFBD games ({len(summary.unmatched)} unmatched)"
    )
    if summary.unmatched:
        print("Unmatched:")
        for item in summary.unmatched:
            print(f"  {item}")
    if summary.malformed:
        print(f"{summary.malformed} malformed rows skipped")
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
        in_sample, holdout = split_holdout(
            system, set(args.holdout_seasons), available_seasons
        )
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
        print(
            "No built games table found. Run `build` (after `fetch`) first.",
            file=sys.stderr,
        )
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
        print(
            f"--holdout-season {args.holdout_season} is not present in the built data.",
            file=sys.stderr,
        )
        return 1
    if args.season:
        unknown = set(args.season) - available_seasons
        if unknown:
            print("error=unknown_season", file=sys.stderr)
            print(
                f"--season value(s) not present in the built data: {sorted(unknown)}",
                file=sys.stderr,
            )
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
        print(
            "No in-sample games remain after applying --season scope and the holdout split.",
            file=sys.stderr,
        )
        return 1
    if not holdout_games:
        print("error=empty_holdout", file=sys.stderr)
        print(
            f"--holdout-season {args.holdout_season} has no games after --season scope; nothing to grade on.",
            file=sys.stderr,
        )
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
    in_sample_feature_map = {
        gid: row for gid, row in feature_map.items() if gid in in_sample_game_ids
    }
    holdout_feature_map = {
        gid: row for gid, row in feature_map.items() if gid in holdout_game_ids
    }

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

    grading = grade_finalists(
        beam_result, holdout_games, holdout_feature_map, alpha=args.alpha
    )

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
            print(
                "--save requested but no finalists survived grading.", file=sys.stderr
            )
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

    if args.save_run:
        from datetime import datetime, timezone

        from cfb_system_maker.models import SearchRun, SearchRunFinalist
        from cfb_system_maker.storage import save_search_run

        run = SearchRun(
            name=args.save_run,
            saved_at=datetime.now(timezone.utc).isoformat(),
            candidates_tested=beam_result.candidates_tested,
            finalists_graded=grading.finalists_graded,
            effective_params=dict(beam_result.effective_params),
            finalists=tuple(
                SearchRunFinalist(
                    system=finalist.system,
                    wins=finalist.holdout_result.wins,
                    losses=finalist.holdout_result.losses,
                    pushes=finalist.holdout_result.pushes,
                    roi=finalist.holdout_result.roi,
                    raw_p=finalist.raw_p,
                    corrected_p=finalist.corrected_p,
                    bh_significant=finalist.bh_significant,
                )
                for finalist in grading.finalists
            ),
        )
        save_search_run(args.save_run, run, args.data_dir)
        print(f"Saved run as {args.save_run} ({grading.finalists_graded} finalists)")
        print(f"View at /search-runs/{args.save_run} (run `web` first)")

    return 0


def _duckdb(args: argparse.Namespace) -> int:
    only = set(args.only) if args.only else None

    def _progress(report: TableLoad) -> None:
        label = f"{report.schema}.{report.name}"
        if report.error:
            print(f"{label:36} FAILED  {report.error}", flush=True)
        else:
            print(
                f"{label:36} {report.files:>4} file(s)  {report.rows:>10} rows",
                flush=True,
            )

    if args.rename_ids:
        db_path = Path(args.output) if args.output else Path(args.data_dir) / "cfb.duckdb"
        if not db_path.exists():
            print(f"No DuckDB file at {db_path}. Run `duckdb` without --rename-ids first.")
            return 1
        reports = rename_stg_id_columns(db_path, progress=_progress)
        ok = [r for r in reports if r.error is None]
        failed = [r for r in reports if r.error is not None]
        rewritten = [r for r in ok if r.files]
        print(
            f"\n{len(rewritten)} table(s) renamed, "
            f"{len(ok) - len(rewritten)} unchanged, {len(failed)} failed."
        )
        print(f"Wrote id names into {db_path}")
        return 1 if failed and not ok else 0

    if args.reorder_columns:
        db_path = (
            Path(args.output) if args.output else Path(args.data_dir) / "cfb.duckdb"
        )
        if not db_path.exists():
            print(
                f"No DuckDB file at {db_path}. Run `duckdb` without --reorder-columns first."
            )
            return 1
        reports = reorder_stg_columns(db_path, progress=_progress)
        ok = [r for r in reports if r.error is None]
        failed = [r for r in reports if r.error is not None]
        rewritten = [r for r in ok if r.files]
        print(
            f"\n{len(rewritten)} table(s) reordered, {len(ok) - len(rewritten)} already ordered, {len(failed)} failed."
        )
        print(f"Wrote column order into {db_path}")
        return 1 if failed and not ok else 0

    if args.flatten_nested:
        db_path = (
            Path(args.output) if args.output else Path(args.data_dir) / "cfb.duckdb"
        )
        if not db_path.exists():
            print(
                f"No DuckDB file at {db_path}. Run `duckdb` without --flatten-nested first."
            )
            return 1
        reports = flatten_stg_nested(db_path, progress=_progress)
        ok = [r for r in reports if r.error is None]
        failed = [r for r in reports if r.error is not None]
        print(f"\n{len(ok)} table(s) flattened, {len(failed)} failed.")
        print(f"Wrote nested columns into {db_path}")
        return 1 if failed and not ok else 0

    if args.explode_lists:
        db_path = (
            Path(args.output) if args.output else Path(args.data_dir) / "cfb.duckdb"
        )
        if not db_path.exists():
            print(
                f"No DuckDB file at {db_path}. Run `duckdb` without --explode-lists first."
            )
            return 1
        reports = explode_stg_lists(db_path, only=only, progress=_progress)
        ok = [r for r in reports if r.error is None]
        failed = [r for r in reports if r.error is not None]
        print()
        print(f"{len(ok)} child table(s) written, {len(failed)} skipped.")
        print(f"Wrote nested columns into {db_path}")
        return 1 if failed and not ok else 0

    if args.promote_timestamps:
        db_path = (
            Path(args.output) if args.output else Path(args.data_dir) / "cfb.duckdb"
        )
        if not db_path.exists():
            print(
                f"No DuckDB file at {db_path}. Run `duckdb` without --promote-timestamps first."
            )
            return 1
        reports = promote_timestamp_columns(db_path, progress=_progress)
        ok = [r for r in reports if r.error is None]
        failed = [r for r in reports if r.error is not None]
        print()
        print(f"{len(ok)} column(s) retyped to TIMESTAMPTZ, {len(failed)} failed.")
        print(f"Wrote column types into {db_path}")
        return 1 if failed and not ok else 0

    if args.explode_only:
        db_path = (
            Path(args.output) if args.output else Path(args.data_dir) / "cfb.duckdb"
        )
        if not db_path.exists():
            print(
                f"No DuckDB file at {db_path}. Run `duckdb` without --explode-only first."
            )
            return 1
        reports = explode_payloads(db_path, only=only, progress=_progress)
        ok = [r for r in reports if r.error is None]
        failed = [r for r in reports if r.error is not None]
        print(f"\n{len(ok)} table(s) exploded, {len(failed)} failed.")
        print(f"Wrote stg.* into {db_path}")
        return 1 if failed and not ok else 0

    if args.core_only:
        db_path = (
            Path(args.output) if args.output else Path(args.data_dir) / "cfb.duckdb"
        )
        if not db_path.exists():
            print(f"No DuckDB file at {db_path}. Run `duckdb --explode` first.")
            return 1
        built = build_core(db_path, provider=args.provider)
        print(f"Built core Phase 1 ({', '.join(built)}) into {db_path}")
        return 0

    path, reports = build_duckdb(
        args.data_dir,
        output=args.output,
        only=only,
        include_actionnetwork=not args.skip_actionnetwork,
        explode=args.explode,
        progress=_progress,
    )
    ok = [r for r in reports if r.error is None]
    failed = [r for r in reports if r.error is not None]
    print(f"\n{len(ok)} table(s) loaded, {len(failed)} failed.")
    print(f"Wrote {path}")
    if args.core:
        built = build_core(path, provider=args.provider)
        print(f"Built core Phase 1 ({', '.join(built)}) into {path}")
    return 1 if failed and not ok else 0


def _web(args: argparse.Namespace) -> int:
    from cfb_system_maker.web import create_app

    logging.basicConfig(
        level=logging.DEBUG if args.debug else logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    )

    app = create_app(data_dir=args.data_dir)
    if args.debug:
        app.run(host=args.host, port=args.port, debug=True)
    else:
        from waitress import serve

        serve(app, host=args.host, port=args.port, threads=8)
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
            print(
                f"  {record.season}: {record.wins}-{record.losses}-{record.pushes}  ROI {record.roi:.2%}"
            )
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
    sample.add_argument("--data-dir", default=DATA_DIR_DEFAULT)

    fetch = subparsers.add_parser("fetch")
    fetch.add_argument("--data-dir", default=DATA_DIR_DEFAULT)
    fetch.add_argument("--season", dest="seasons", type=int, nargs="+", required=True)
    fetch.add_argument("--season-type", default="both")
    fetch.add_argument("--provider")

    build = subparsers.add_parser("build")
    build.add_argument("--data-dir", default=DATA_DIR_DEFAULT)
    build.add_argument("--season", dest="seasons", type=int, nargs="+", required=True)
    build.add_argument("--provider", default="consensus")

    enrich = subparsers.add_parser("enrich")
    enrich.add_argument("--data-dir", default=DATA_DIR_DEFAULT)

    refit_v1 = subparsers.add_parser("refit-v1")
    refit_v1.add_argument("--data-dir", default=DATA_DIR_DEFAULT)

    upcoming = subparsers.add_parser("upcoming")
    upcoming.add_argument("--data-dir", default=DATA_DIR_DEFAULT)

    scrape_parser = subparsers.add_parser("scrape")
    scrape_parser.add_argument("--data-dir", default=DATA_DIR_DEFAULT)
    scrape_parser.add_argument(
        "--season", dest="seasons", type=int, nargs="+", required=True
    )
    scrape_parser.add_argument(
        "--season-type",
        default="both",
        help="regular | postseason | both. season_week endpoints run one pass "
        "per type, postseason into {name}_{season}_post_wk{week}.json, "
        "because postseason week numbering restarts at 1",
    )
    scrape_parser.add_argument("--include-per-game", action="store_true")
    scrape_parser.add_argument("--include-per-player", action="store_true")
    scrape_parser.add_argument("--only", nargs="+")
    scrape_parser.add_argument(
        "--delay", type=float, default=1.0, help="seconds between API calls"
    )
    scrape_parser.add_argument(
        "--force", action="store_true", help="re-scrape even if output file exists"
    )
    scrape_parser.add_argument(
        "--fbs-only", action="store_true", help="per-game endpoints: only FBS games"
    )

    graphql_parser = subparsers.add_parser("graphql")
    graphql_parser.add_argument("--data-dir", default=DATA_DIR_DEFAULT)
    graphql_parser.add_argument("--season", dest="seasons", type=int, nargs="+")
    graphql_parser.add_argument("--only", nargs="+")
    graphql_parser.add_argument(
        "--tables",
        nargs="+",
        help="pull these root tables instead of the default list "
        "(reaches tables not in GQL_DEFAULT_TABLES)",
    )
    graphql_parser.add_argument("--page-size", type=int, default=1000)
    graphql_parser.add_argument(
        "--game-player-stats",
        action="store_true",
        help="bespoke labeled player-game stats, one file per --season",
    )
    graphql_parser.add_argument(
        "--force", action="store_true", help="re-pull even if season file exists"
    )

    an = subparsers.add_parser("actionnetwork")
    an.add_argument("--data-dir", default=DATA_DIR_DEFAULT)
    an.add_argument("--season", dest="seasons", type=int, nargs="+", required=True)
    an.add_argument("--season-type", default="reg")
    an.add_argument(
        "--periods",
        nargs="+",
        default=["firsthalf", "firstquarter"],
        help="event/firsthalf/secondhalf/firstquarter..fourthquarter",
    )
    an.add_argument("--only", nargs="+", help="scoreboard and/or history")
    an.add_argument(
        "--delay", type=float, default=1.0, help="seconds between API calls"
    )
    an.add_argument(
        "--force", action="store_true", help="re-scrape even if output file exists"
    )

    backtest = subparsers.add_parser("backtest")
    backtest.add_argument("--data-dir", default=DATA_DIR_DEFAULT)
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
    backtest.add_argument(
        "--holdout-season", dest="holdout_seasons", type=int, action="append"
    )

    search = subparsers.add_parser("search")
    search.add_argument("--data-dir", default=DATA_DIR_DEFAULT)
    search.add_argument("--holdout-season", type=int, required=True)
    search.add_argument("--season", type=int, action="append")
    search.add_argument("--max-filters", type=int, default=4)
    search.add_argument("--bet-type", choices=["spread", "total"], default="spread")
    search.add_argument("--beam-width", type=int, default=100)
    search.add_argument("--top-k", type=int, default=20)
    search.add_argument("--min-decided-bets", type=int, default=100)
    search.add_argument("--alpha", type=float, default=0.05)
    search.add_argument("--save", help="save the top-ranked finalist under this name")
    search.add_argument(
        "--save-run",
        dest="save_run",
        default=None,
        help="save the full search run under this name",
    )

    duckdb_parser = subparsers.add_parser(
        "duckdb", help="load data/raw + data/graphql JSON into a DuckDB file"
    )
    duckdb_parser.add_argument("--data-dir", default=DATA_DIR_DEFAULT)
    duckdb_parser.add_argument(
        "--output", help="DuckDB path (default: {data-dir}/cfb.duckdb)"
    )
    duckdb_parser.add_argument(
        "--only", nargs="+", help="load / explode only these table names"
    )
    duckdb_parser.add_argument(
        "--skip-actionnetwork",
        action="store_true",
        help="skip data/raw/actionnetwork/ scoreboard+history objects",
    )
    duckdb_parser.add_argument(
        "--explode",
        action="store_true",
        help="after load, explode JSON payloads into stg.* columns",
    )
    duckdb_parser.add_argument(
        "--explode-only",
        action="store_true",
        help="explode payloads in an existing DuckDB file; do not reload JSON",
    )
    duckdb_parser.add_argument(
        "--promote-timestamps",
        action="store_true",
        help="retype stg.* VARCHAR date/time columns as TIMESTAMPTZ",
    )
    duckdb_parser.add_argument(
        "--explode-lists",
        action="store_true",
        help="explode leftover LIST/JSON stg.* columns into stg.<table>__<column>",
    )
    duckdb_parser.add_argument(
        "--flatten-nested",
        action="store_true",
        help="flatten leftover STRUCT columns on existing stg.* tables",
    )
    duckdb_parser.add_argument(
        "--rename-ids",
        action="store_true",
        help="rename stg.* id/homeId/awayId columns to gameId/playId/teamId/…",
    )
    duckdb_parser.add_argument(
        "--reorder-columns",
        action="store_true",
        help="rewrite stg.* column order (gameId/season/sides first) on an existing DuckDB file",
    )
    duckdb_parser.add_argument(
        "--core",
        action="store_true",
        help="after load, build core.* Phase 1 (dims, fact_game, fact_game_line, fact_game_team)",
    )
    duckdb_parser.add_argument(
        "--core-only",
        action="store_true",
        help="build core.* Phase 1 into an existing DuckDB file; do not reload JSON",
    )
    duckdb_parser.add_argument(
        "--provider",
        default="consensus",
        help="preferred book for fact_game selected close (default: consensus)",
    )

    betlog_parser = subparsers.add_parser("betlog")
    betlog_subparsers = betlog_parser.add_subparsers(
        dest="betlog_command", required=True
    )
    betlog_import_parser = betlog_subparsers.add_parser("import")
    betlog_import_parser.add_argument("--csv", required=True)
    betlog_import_parser.add_argument("--data-dir", default=DATA_DIR_DEFAULT)

    web = subparsers.add_parser("web")
    web.add_argument(
        "--data-dir", default=os.environ.get("CFB_DATA_DIR", DATA_DIR_DEFAULT)
    )
    web.add_argument(
        "--host",
        default=os.environ.get("CFB_WEB_HOST")
        or (
            "0.0.0.0"
            if os.environ.get("PORT") or os.environ.get("FLY_APP_NAME")
            else "127.0.0.1"
        ),
    )
    web.add_argument(
        "--port",
        type=int,
        default=int(os.environ.get("CFB_WEB_PORT") or os.environ.get("PORT") or "5000"),
    )
    web.add_argument("--debug", action="store_true")

    return parser

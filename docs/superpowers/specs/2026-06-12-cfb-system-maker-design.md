# CFB System Maker Design

## Goal

Build a first command-line version of a college football betting system maker. It will fetch historical game and betting line data through the local CFBD Python client, cache the data locally, apply filter-based betting systems, and report performance metrics.

## Scope

Version 1 stays focused on a Python backtesting tool. It does not include a website yet, but the data model and command entry points should be clean enough to support a web UI later.

## Data

The tool pulls games and betting lines by season. It stores raw API responses under `data/raw/` and creates a normalized joined betting table under `data/processed/`. The normalized records include season, week, teams, conferences, scores, selected spread, selected total, selected provider, home/away side fields, and final bet outcome fields.

## Systems

Systems are filter collections. Version 1 supports filters for side, home/away, favorite/underdog, season, week, team, conference, spread range, and total range. Each matching game produces one tracked bet.

## Metrics

Backtests report bets, wins, losses, pushes, hit rate, profit, ROI, average line, and average stake. Standard spread bets use -110 American odds by default with one unit risked per bet.

## Interface

The command line supports three main flows:

- fetch historical data for one or more seasons
- run sample systems against cached data
- run a custom system from command-line filters

## Testing

Unit tests cover line normalization, filter matching, bet grading, and metric calculation. A CLI smoke test verifies the tool can run against bundled sample data without hitting the network.


# CFB System Maker

Python command-line backtester for college football betting systems.

## Try sample data

```powershell
python -m cfb_system_maker sample --data-dir data
```

## Fetch real CFBD data

The tool reads a CFBD token from `CFBD_API_KEY`, `BEARER_TOKEN`, `CFBD-API`, or `env.env`.

```powershell
python -m cfb_system_maker fetch --season 2023 2024 --provider consensus --data-dir data
python -m cfb_system_maker build --season 2023 2024 --provider consensus --data-dir data
```

## Scrape all CFBD endpoints

```powershell
python -m cfb_system_maker scrape --season 2023 2024 --data-dir data
python -m cfb_system_maker scrape --season 2023 --only games lines sp
python -m cfb_system_maker scrape --season 2023 --include-per-game --fbs-only
```

Writes raw JSON to `data/raw/`. Does not affect `build`/`backtest` (which still use `fetch`).

## Pull GraphQL tables (Patreon Tier 3)

```powershell
python -m cfb_system_maker graphql --season 2023 --data-dir data
python -m cfb_system_maker graphql --season 2023 --game-player-stats
```

Writes to `data/graphql/`.

## Scrape Action Network odds

```powershell
python -m cfb_system_maker actionnetwork --season 2023 --data-dir data
```

Writes to `data/raw/actionnetwork/`.

## Build enriched features

```powershell
python -m cfb_system_maker enrich --data-dir data
```

Writes `data/processed/features.json` joining raw/graphql sources to each game.

## Backtest filters

```powershell
python -m cfb_system_maker backtest --data-dir data --side home --favorite --min-spread -14 --max-spread -3.5
python -m cfb_system_maker backtest --data-dir data --side away --underdog --conference SEC
python -m cfb_system_maker backtest --data-dir data --bet-type total --total-side over
```

Available filters: `--bet-type`, `--side`, `--total-side`, `--season`, `--week`, `--team`, `--conference`, `--provider`, `--favorite`, `--underdog`, `--home`, `--away`, `--min-spread`, `--max-spread`, `--min-total`, and `--max-total`. Use `--save <name>` / `--load <name>` to persist systems to `data/systems/`.

## Run the web app

Build processed data first, then start Flask:

```powershell
python -m cfb_system_maker web --data-dir data --port 5000
```

Open `http://127.0.0.1:5000`.

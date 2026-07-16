# Web Feature Filters — Implementation Plan

> **Status:** Complete. See [design spec](../specs/2026-06-13-web-feature-filters-design.md).

**Goal:** Filter betting systems on enriched CFBD features (weather, lines, preseason stats, metadata) with system-quality stats and save/load.

## Delivered

| Component | Path |
|-----------|------|
| Feature registry | `cfb_system_maker/features.py` |
| Enrich build | `cfb_system_maker/enrich.py` + CLI `enrich` |
| Models | `FeatureFilter`, `SystemStats` on `BacktestResult` |
| Matching + stats | `cfb_system_maker/backtest.py` |
| System persistence | `cfb_system_maker/storage.py` (`save_system`, `load_system`, `list_systems`) |
| Web UI | `cfb_system_maker/web.py` + `templates/index.html` |
| Tests | `test_features`, `test_enrich`, `test_storage_systems`, extended `test_backtest` / `test_web` |

## Commands

```powershell
python -m cfb_system_maker build --season 2023 2024 --data-dir data
python -m cfb_system_maker enrich --data-dir data
python -m cfb_system_maker backtest --load my-system --data-dir data
python -m cfb_system_maker web --data-dir data
```

## Verification

```powershell
python -m pytest tests/ -v
```

All 26 tests pass.

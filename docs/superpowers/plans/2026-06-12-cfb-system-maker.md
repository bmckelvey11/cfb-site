# CFB System Maker Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a Python command-line college football betting backtester that fetches CFBD historical games/lines, caches them, applies filters, and reports performance.

**Architecture:** Create a small `cfb_system_maker` package outside the generated `cfbd-python` client. Keep API fetching, data normalization, filters, grading, metrics, and CLI in separate files so the same core can power a website later.

**Tech Stack:** Python 3, local `cfbd-python` client, stdlib JSON/CSV/argparse/dataclasses, pytest.

---

### Task 1: Core Domain And Metrics

**Files:**
- Create: `cfb_system_maker/models.py`
- Create: `cfb_system_maker/backtest.py`
- Test: `tests/test_backtest.py`

- [ ] **Step 1: Write failing tests for bet grading and metrics**

Create tests that prove spread bets win, lose, push, and summarize ROI.

- [ ] **Step 2: Run tests and confirm failure**

Run: `python -m pytest tests/test_backtest.py -v`
Expected: import failure because package does not exist.

- [ ] **Step 3: Implement domain models and backtest logic**

Create dataclasses for normalized games, system filters, graded bets, and result metrics. Implement filter matching, spread grading, American odds profit, and aggregate metrics.

- [ ] **Step 4: Run tests and confirm pass**

Run: `python -m pytest tests/test_backtest.py -v`
Expected: all tests pass.

### Task 2: CFBD Fetching And Cache

**Files:**
- Create: `cfb_system_maker/cfbd_client.py`
- Create: `cfb_system_maker/storage.py`
- Test: `tests/test_storage.py`

- [ ] **Step 1: Write failing storage tests**

Create tests for saving and loading raw JSON and processed CSV.

- [ ] **Step 2: Run tests and confirm failure**

Run: `python -m pytest tests/test_storage.py -v`
Expected: import failure or missing functions.

- [ ] **Step 3: Implement storage and API wrapper**

Storage writes raw JSON and normalized CSV. API wrapper loads token from env or `env.env`, imports local CFBD client, and calls `GamesApi.get_games` and `BettingApi.get_lines`.

- [ ] **Step 4: Run tests and confirm pass**

Run: `python -m pytest tests/test_storage.py -v`
Expected: all tests pass.

### Task 3: Normalization

**Files:**
- Create: `cfb_system_maker/normalize.py`
- Test: `tests/test_normalize.py`

- [ ] **Step 1: Write failing normalization tests**

Use representative game and line dictionaries. Confirm joined records include teams, scores, spread, total, provider, favorite side, and home/away sides.

- [ ] **Step 2: Run tests and confirm failure**

Run: `python -m pytest tests/test_normalize.py -v`
Expected: import failure or missing normalizer.

- [ ] **Step 3: Implement normalizer**

Convert CFBD model dictionaries into `GameRecord` objects. Pick requested provider when present, otherwise first usable line with spread or total.

- [ ] **Step 4: Run tests and confirm pass**

Run: `python -m pytest tests/test_normalize.py -v`
Expected: all tests pass.

### Task 4: CLI And Sample Data

**Files:**
- Create: `cfb_system_maker/cli.py`
- Create: `cfb_system_maker/sample_data.py`
- Create: `cfb_system_maker/__main__.py`
- Create: `README.md`
- Test: `tests/test_cli.py`

- [ ] **Step 1: Write failing CLI smoke test**

Run CLI against sample data and assert printed metrics include bets and ROI.

- [ ] **Step 2: Run test and confirm failure**

Run: `python -m pytest tests/test_cli.py -v`
Expected: import failure or missing command.

- [ ] **Step 3: Implement CLI**

Add `fetch`, `build`, `sample`, and `backtest` commands. `sample` writes bundled data and runs sample systems. `backtest` accepts filters.

- [ ] **Step 4: Run test and confirm pass**

Run: `python -m pytest tests/test_cli.py -v`
Expected: all tests pass.

### Task 5: Full Verification

**Files:**
- Modify as needed based on test failures.

- [ ] **Step 1: Run full tests**

Run: `python -m pytest -v`
Expected: all tests pass.

- [ ] **Step 2: Run representative CLI smoke**

Run: `python -m cfb_system_maker sample --data-dir .tmp-cfb-system-maker`
Expected: sample systems print completed performance metrics.

- [ ] **Step 3: Check generated files**

Confirm `.tmp-cfb-system-maker/raw/` and `.tmp-cfb-system-maker/processed/games.csv` exist and contain sample records.


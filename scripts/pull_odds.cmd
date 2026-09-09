@echo off
REM Wrapper for Windows Task Scheduler around scripts/pull_odds.py.
REM
REM Exists so the task definition stays a single command and every run is logged --
REM same reasoning as refresh_cfbd.cmd and collect_line_timing.cmd.
REM
REM   pull_odds.cmd
REM   pull_odds.cmd --markets h2h spreads totals
REM
REM Registered as scheduled task CFB-Odds-Snapshot, repeating every 6 hours: at 3
REM credits a run that is 360/month against the free plan's 500, which leaves room
REM for ad-hoc pulls. Changing the cadence here means changing the credit math --
REM see docs/oddsapi-ingest.md.
REM
REM Override PYTHON to use a different interpreter (defaults to this repo's venv).
REM CFB_DATA_ROOT is inherited from the user environment.
setlocal
set "REPO=%~dp0.."
if "%PYTHON%"=="" set "PYTHON=%REPO%\.venv\Scripts\python.exe"
if "%CFB_DATA_ROOT%"=="" set "CFB_DATA_ROOT=%REPO%\data"
set "LOGDIR=%CFB_DATA_ROOT%\logs"
if not exist "%LOGDIR%" mkdir "%LOGDIR%"
set "LOG=%LOGDIR%\odds_pull.log"

echo.>> "%LOG%"
echo ==== %DATE% %TIME% :: %* ====>> "%LOG%"
REM -u: Python block-buffers stdout when redirected, so a killed run (sleep,
REM shutdown) loses everything it had printed. Unbuffered keeps the partial trail.
"%PYTHON%" -u "%REPO%\scripts\pull_odds.py" %*>> "%LOG%" 2>&1
set RC=%ERRORLEVEL%
if not "%RC%"=="0" echo ---- exited %RC% ---->> "%LOG%"
exit /b %RC%

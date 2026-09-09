@echo off
REM Wrapper for Windows Task Scheduler around scripts/pull_oddspapi.py.
REM
REM Exists so the task definition stays a single command and every run is logged --
REM same reasoning as pull_odds.cmd and refresh_cfbd.cmd.
REM
REM   pull_oddspapi.cmd
REM   pull_oddspapi.cmd --bookmakers pinnacle,circasports
REM
REM Registered as scheduled task CFB-Pinnacle-Snapshot, daily at 08:00: one request a run
REM is ~30/month against oddspapi's free plan of 250, which leaves room for ad-hoc pulls.
REM Changing the cadence here means changing the request math -- see docs/oddsapi-ingest.md.
REM
REM Override PYTHON to use a different interpreter (defaults to this repo's venv).
REM CFB_DATA_ROOT is inherited from the user environment.
setlocal
set "REPO=%~dp0.."
if "%PYTHON%"=="" set "PYTHON=%REPO%\.venv\Scripts\python.exe"
if "%CFB_DATA_ROOT%"=="" set "CFB_DATA_ROOT=%REPO%\data"
set "LOGDIR=%CFB_DATA_ROOT%\logs"
if not exist "%LOGDIR%" mkdir "%LOGDIR%"
set "LOG=%LOGDIR%\oddspapi_pull.log"

echo.>> "%LOG%"
echo ==== %DATE% %TIME% :: %* ====>> "%LOG%"
REM -u: unbuffered so a killed run keeps its partial trail in the log.
"%PYTHON%" -u "%REPO%\scripts\pull_oddspapi.py" %*>> "%LOG%" 2>&1
set RC=%ERRORLEVEL%
if not "%RC%"=="0" echo ---- exited %RC% ---->> "%LOG%"
exit /b %RC%

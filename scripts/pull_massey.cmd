@echo off
REM Wrapper for Windows Task Scheduler around the weekly Massey pull.
REM
REM Same shape as pull_odds.cmd: one command for the task definition, every run
REM logged, one ledger row. Two steps: `massey_ranks.py update` discovers the
REM current season's edition dates and downloads any edition not yet on disk,
REM then `massey_flatten.py` rewrites data/processed/massey/*.csv, which the
REM 05:00 CFB-CFBD-Daily rebuild loads into stg.massey_*.
REM
REM   pull_massey.cmd
REM   pull_massey.cmd --season 2025
REM
REM Registered as scheduled task CFB-Massey-Weekly, Tuesday 04:30: Massey dates
REM editions on Sunday and most systems have posted by Monday night.
REM
REM Override PYTHON to use a different interpreter (defaults to this repo's venv).
REM CFB_DATA_ROOT is inherited from the user environment.
setlocal
set "REPO=%~dp0.."
if "%PYTHON%"=="" set "PYTHON=%REPO%\.venv\Scripts\python.exe"
if "%CFB_DATA_ROOT%"=="" (
  echo CFB_DATA_ROOT is not set; refusing to guess a data root. 1>&2
  exit /b 3
)
if not exist "%CFB_DATA_ROOT%\.cfb-data-root" (
  echo CFB_DATA_ROOT="%CFB_DATA_ROOT%" is not an initialized CFB data root. 1>&2
  exit /b 3
)
REM `if exist` matches directories too, so reject a marker that is one.
if exist "%CFB_DATA_ROOT%\.cfb-data-root\" (
  echo CFB_DATA_ROOT="%CFB_DATA_ROOT%" marker is a directory, not a file. 1>&2
  exit /b 3
)
set "LOGDIR=%CFB_DATA_ROOT%\logs"
if not exist "%LOGDIR%" mkdir "%LOGDIR%"
set "LOG=%LOGDIR%\massey_pull.log"

for /f %%i in ('powershell -NoProfile -NonInteractive -Command "(Get-Date).ToString('s')"') do set "START=%%i"
echo.>> "%LOG%"
echo ==== %DATE% %TIME% :: %* ====>> "%LOG%"
"%PYTHON%" -u "%REPO%\scripts\massey_ranks.py" update %*>> "%LOG%" 2>&1
set RC=%ERRORLEVEL%
if "%RC%"=="0" (
  "%PYTHON%" -u "%REPO%\scripts\massey_flatten.py">> "%LOG%" 2>&1
  set RC=%ERRORLEVEL%
)
if not "%RC%"=="0" echo ---- exited %RC% ---->> "%LOG%"
call "%REPO%\scripts\task_ledger.cmd" "massey_weekly" "%START%" %RC%
exit /b %RC%

@echo off
REM Wrapper for Windows Task Scheduler around scripts/refresh_cfbd.py.
REM
REM Exists so the task definition stays a single command and every run is logged --
REM same reasoning as research/spread/scripts/collect_line_timing.cmd.
REM
REM   refresh_cfbd.cmd
REM   refresh_cfbd.cmd --season 2026
REM
REM Override PYTHON to use a different interpreter. Defaults to .venv-cfbd, the
REM fetch venv (scripts/make_fetch_venv.cmd): the main .venv resolves pydantic to 2.x
REM for anthropic, which the vendored CFBD client cannot import. Falls back to .venv
REM so an un-built fetch venv degrades to the old behaviour instead of hard-failing.
REM CFB_DATA_ROOT is inherited from the user environment.
setlocal
set "REPO=%~dp0.."
if "%PYTHON%"=="" (
  if exist "%REPO%\.venv-cfbd\Scripts\python.exe" (
    set "PYTHON=%REPO%\.venv-cfbd\Scripts\python.exe"
  ) else (
    set "PYTHON=%REPO%\.venv\Scripts\python.exe"
  )
)
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
set "LOG=%LOGDIR%\cfbd_refresh.log"

echo.>> "%LOG%"
echo ==== %DATE% %TIME% :: %* ====>> "%LOG%"
REM -u: Python block-buffers stdout when redirected, so a killed run (sleep,
REM shutdown) loses everything it had printed. Unbuffered keeps the partial trail.
"%PYTHON%" -u "%REPO%\scripts\refresh_cfbd.py" %*>> "%LOG%" 2>&1
set RC=%ERRORLEVEL%
if not "%RC%"=="0" echo ---- exited %RC% ---->> "%LOG%"

REM Weekly offense/defense/pace rankings from whatever games and drives are now on disk
REM (scripts/weekly_rankings.py). Runs even after a partial fetch -- games with missing
REM drives are gated out and the next run fills them in -- and never changes RC.
pushd "%REPO%"
"%PYTHON%" -u -m scripts.weekly_rankings>> "%LOG%" 2>&1
if errorlevel 1 echo ---- weekly_rankings exited %ERRORLEVEL% ---->> "%LOG%"
popd
exit /b %RC%

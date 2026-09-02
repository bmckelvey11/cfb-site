@echo off
REM Wrapper for Windows Task Scheduler around scripts/refresh_cfbd.py.
REM
REM Exists so the task definition stays a single command and every run is logged --
REM same reasoning as research/spread/scripts/collect_line_timing.cmd.
REM
REM   refresh_cfbd.cmd
REM   refresh_cfbd.cmd --season 2026
REM
REM Override PYTHON to use a different interpreter (defaults to this repo's venv,
REM which has cfbd/duckdb installed -- the system Python used by collect_line_timing.cmd
REM does not). CFB_DATA_ROOT is inherited from the user environment.
setlocal
set "REPO=%~dp0.."
if "%PYTHON%"=="" set "PYTHON=%REPO%\.venv\Scripts\python.exe"
if "%CFB_DATA_ROOT%"=="" set "CFB_DATA_ROOT=%REPO%\data"
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
exit /b %RC%

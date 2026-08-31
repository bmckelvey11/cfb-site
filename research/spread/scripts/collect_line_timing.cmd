@echo off
REM Wrapper for Windows Task Scheduler around research/spread/scripts/collect_line_timing.py.
REM
REM Exists so the task definition stays a single command and every run is logged --
REM this collector has to survive a whole season unattended, and a silent failure in
REM October is only discoverable if there is a log to read.
REM
REM   collect_line_timing.cmd snapshot
REM   collect_line_timing.cmd history --season 2026 --weeks 1-16
REM
REM Override PYTHON to use a different interpreter. CFB_DATA_ROOT is inherited from the
REM user environment; the Python side resolves paths through cfb_paths.
setlocal
set "REPO=%~dp0..\..\.."
if "%PYTHON%"=="" set "PYTHON=C:\Python314\python.exe"
if "%CFB_DATA_ROOT%"=="" set "CFB_DATA_ROOT=%USERPROFILE%\data\cfb"
set "LOGDIR=%CFB_DATA_ROOT%\logs"
if not exist "%LOGDIR%" mkdir "%LOGDIR%"
set "LOG=%LOGDIR%\line_timing.log"

echo.>> "%LOG%"
echo ==== %DATE% %TIME% :: %* ====>> "%LOG%"
"%PYTHON%" "%REPO%\research\spread\scripts\collect_line_timing.py" %*>> "%LOG%" 2>&1
set RC=%ERRORLEVEL%
if not "%RC%"=="0" echo ---- exited %RC% ---->> "%LOG%"
exit /b %RC%

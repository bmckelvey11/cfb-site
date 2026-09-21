@echo off
REM One-line-per-run ledger shared by every scheduled-task wrapper.
REM
REM The per-task logs (odds_pull.log, line_timing.log, ...) hold the output but
REM answering "did everything fire last night?" meant grepping five files, and
REM Windows only keeps the single most recent LastRunTime per task. This is the
REM durable cross-task history.
REM
REM   task_ledger.cmd <label> <start-stamp> <exit-code>
REM
REM Called once per run, at the end, with the start captured by the caller --
REM a single short append keeps concurrent writers from interleaving rows.
REM Stamps come from PowerShell rather than %DATE%/%TIME%, which are locale
REM dependent and pad hours < 10 with a space.
setlocal
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
set "LEDGER=%LOGDIR%\task_runs.csv"
if not exist "%LOGDIR%" mkdir "%LOGDIR%"
if not exist "%LEDGER%" >> "%LEDGER%" echo task,started,finished,exit_code
for /f %%i in ('powershell -NoProfile -NonInteractive -Command "(Get-Date).ToString('s')"') do set "END=%%i"
>> "%LEDGER%" echo %~1,%~2,%END%,%~3
endlocal

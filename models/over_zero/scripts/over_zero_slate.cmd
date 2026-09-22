@echo off
REM Wrapper for Windows Task Scheduler around the over-zero slate.
REM
REM Same shape as scripts/refresh_cfbd.cmd: one command for the task definition,
REM every run appended to one log. Runs the slate, then rebuilds the site so
REM site/dist matches the new board. Deploying that build stays a hand job --
REM the sites remote needs your auth.
REM
REM   over_zero_slate.cmd
REM   over_zero_slate.cmd --days 3
REM
REM Override PYTHON to use a different interpreter (defaults to the repo venv).
setlocal
set "REPO=%~dp0..\..\.."
set "SITE=%REPO%\models\over_zero\site"
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
set "LOG=%LOGDIR%\over_zero_slate.log"

for /f %%i in ('powershell -NoProfile -NonInteractive -Command "(Get-Date).ToString('s')"') do set "START=%%i"
echo.>> "%LOG%"
echo ==== %DATE% %TIME% :: %* ====>> "%LOG%"
REM -u so a killed run keeps the partial trail (see refresh_cfbd.cmd).
"%PYTHON%" -u "%REPO%\models\over_zero\scripts\best_line_slate.py" --max-spread 50 --json "%SITE%\lib\board.json" %*>> "%LOG%" 2>&1
set RC=%ERRORLEVEL%
if not "%RC%"=="0" (
    echo ---- slate exited %RC%, skipping build ---->> "%LOG%"
    call "%REPO%\scripts\task_ledger.cmd" "over_zero_slate" "%START%" %RC%
exit /b %RC%
)

REM npm is npm.cmd -- without call, control never comes back here.
cd /d "%SITE%"
call npm run build>> "%LOG%" 2>&1
set RC=%ERRORLEVEL%
if not "%RC%"=="0" echo ---- build exited %RC% ---->> "%LOG%"
call "%REPO%\scripts\task_ledger.cmd" "over_zero_slate" "%START%" %RC%
exit /b %RC%

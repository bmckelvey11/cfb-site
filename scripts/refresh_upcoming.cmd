@echo off
REM Refresh processed/upcoming.csv + features + meta with this week's games and lines.
REM
REM Runs under .venv-cfbd (see scripts/make_fetch_venv.cmd); the main .venv cannot
REM import the CFBD client. Logged like refresh_cfbd.cmd so a failed run leaves a trail.
REM
REM   refresh_upcoming.cmd
setlocal
set "REPO=%~dp0.."
if "%PYTHON%"=="" set "PYTHON=%REPO%\.venv-cfbd\Scripts\python.exe"
if "%CFB_DATA_ROOT%"=="" set "CFB_DATA_ROOT=%REPO%\data"

if not exist "%PYTHON%" (
  echo Fetch venv missing. Run scripts\make_fetch_venv.cmd first.
  exit /b 1
)

set "LOGDIR=%CFB_DATA_ROOT%\logs"
if not exist "%LOGDIR%" mkdir "%LOGDIR%"
set "LOG=%LOGDIR%\upcoming_refresh.log"

echo.>> "%LOG%"
echo ==== %DATE% %TIME% :: %* ====>> "%LOG%"
"%PYTHON%" -u -m cfb_system_maker upcoming --data-dir "%CFB_DATA_ROOT%" %*>> "%LOG%" 2>&1
set RC=%ERRORLEVEL%
if not "%RC%"=="0" echo ---- exited %RC% ---->> "%LOG%"
type "%LOG%" | powershell -NoProfile -NonInteractive -Command "$input | Select-Object -Last 3"
exit /b %RC%

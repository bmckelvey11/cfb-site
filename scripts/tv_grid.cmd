@echo off
REM Refresh CFBD weather + media (the two feeds the TV grid needs fresh), then
REM render the week's grid. Same shape as pull_odds.cmd: one command, every run
REM logged.
REM
REM   tv_grid.cmd
REM   tv_grid.cmd --season 2026 --week 3
REM
REM refresh_cfbd.py needs the CFBD venv (main .venv carries pydantic 2); the grid
REM itself runs under either. Override PYTHON / PYTHON_CFBD to change interpreters.
REM CFB_DATA_ROOT is inherited from the user environment.
setlocal
set "REPO=%~dp0.."
if "%PYTHON%"=="" set "PYTHON=%REPO%\.venv\Scripts\python.exe"
if "%PYTHON_CFBD%"=="" set "PYTHON_CFBD=%REPO%\.venv-cfbd\Scripts\python.exe"
if "%CFB_DATA_ROOT%"=="" set "CFB_DATA_ROOT=%REPO%\data"
set "LOGDIR=%CFB_DATA_ROOT%\logs"
if not exist "%LOGDIR%" mkdir "%LOGDIR%"
set "LOG=%LOGDIR%\tv_grid.log"

echo.>> "%LOG%"
echo ==== %DATE% %TIME% :: %* ====>> "%LOG%"
"%PYTHON_CFBD%" -u "%REPO%\scripts\refresh_cfbd.py" --only weather media>> "%LOG%" 2>&1
set RC=%ERRORLEVEL%
if not "%RC%"=="0" echo ---- refresh exited %RC%; rendering from the existing warehouse ---->> "%LOG%"
"%PYTHON%" -u "%REPO%\scripts\tv_grid.py" %*>> "%LOG%" 2>&1
set RC=%ERRORLEVEL%
if not "%RC%"=="0" echo ---- exited %RC% ---->> "%LOG%"
exit /b %RC%

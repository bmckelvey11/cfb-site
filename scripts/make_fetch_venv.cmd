@echo off
REM Build (or rebuild) .venv-cfbd, the interpreter the CFBD network fetches run under.
REM
REM The main .venv cannot import the vendored CFBD client: cfbd-python pins
REM pydantic <2 while anthropic pins >=2, so the shared venv resolves to pydantic 2
REM and the client dies at import. See requirements-fetch.txt for the full note.
REM
REM   make_fetch_venv.cmd          rebuild from scratch
REM
REM Override PYTHON to seed it from a different base interpreter.
setlocal
set "REPO=%~dp0.."
if "%PYTHON%"=="" set "PYTHON=%REPO%\.venv\Scripts\python.exe"
set "TARGET=%REPO%\.venv-cfbd"

if exist "%TARGET%" (
  echo Removing existing %TARGET%
  rmdir /s /q "%TARGET%"
)

"%PYTHON%" -m venv "%TARGET%" || exit /b 1
"%TARGET%\Scripts\python.exe" -m pip install --upgrade pip || exit /b 1
"%TARGET%\Scripts\python.exe" -m pip install -r "%REPO%\requirements-fetch.txt" || exit /b 1

REM Fail loudly here rather than at 3am in a scheduled refresh.
"%TARGET%\Scripts\python.exe" -c "import cfb_system_maker.cfbd_client as c; c._load_cfbd_module(); print('cfbd client imports OK')" || exit /b 1
echo Fetch venv ready: %TARGET%
exit /b 0

@echo off
REM ---- Launcher for the Fresh Mart billing app ----
REM Uses the local Python 3.12 install (not on PATH).

set "PY=%LOCALAPPDATA%\Programs\Python\Python312\python.exe"

if not exist "%PY%" (
    echo Python 3.12 was not found at "%PY%".
    echo Please install Python 3.10+ from https://python.org and re-run.
    pause
    exit /b 1
)

cd /d "%~dp0"
"%PY%" -m pip install --quiet --disable-pip-version-check -r requirements.txt
"%PY%" app.py
pause

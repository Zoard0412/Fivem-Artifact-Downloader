@echo off
setlocal enabledelayedexpansion

cd /d "%~dp0"

where py >nul 2>nul
if %errorlevel%==0 (
    set "PY=py -3"
    goto :havepython
)
where python >nul 2>nul
if %errorlevel%==0 (
    set "PY=python"
    goto :havepython
)

echo Python was not found.
where winget >nul 2>nul
if not %errorlevel%==0 (
    echo This script can only auto-install Python via winget, which was not found on this system.
    echo Install Python 3.10+ manually from https://www.python.org/downloads/windows/
    echo and make sure to check "Add python.exe to PATH" during setup.
    exit /b 1
)

set /p REPLY="Install Python via winget now? [Y/n] "
if /i "%REPLY%"=="n" (
    echo Install it manually from https://www.python.org/downloads/windows/
    exit /b 1
)

winget install -e --id Python.Python.3.12 --accept-source-agreements --accept-package-agreements
if not %errorlevel%==0 (
    echo winget installation failed. Install Python manually from https://www.python.org/downloads/windows/
    exit /b 1
)

echo.
echo Python was installed. Close this window, open a NEW terminal ^(so PATH is
echo refreshed^), and run install.bat again.
exit /b 0

:havepython

echo Creating virtual environment in .venv ...
%PY% -m venv .venv

if not exist ".venv\Scripts\python.exe" (
    echo.
    echo Virtual environment creation failed.
    exit /b 1
)

echo Installing dependencies...
.venv\Scripts\python.exe -m pip install --upgrade pip
.venv\Scripts\python.exe -m pip install -r requirements.txt

echo.
echo Installation complete. Start the app with run.bat
endlocal

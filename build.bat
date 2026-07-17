@echo off
setlocal enabledelayedexpansion
REM Builds a standalone, single-file .exe of the app for the CURRENT
REM machine's Windows architecture, using PyInstaller.
REM
REM IMPORTANT: PyInstaller cannot cross-compile. It only produces a binary
REM for the architecture it is actually running on (x86_64 or arm64). To
REM get the other one, run this same script on a real or virtual machine of
REM that architecture - or use a CI matrix build (e.g. GitHub Actions
REM runners: windows-latest for x86_64, windows-11-arm for arm64). Building
REM for macOS or Linux from Windows is not possible with this script either.
REM
REM Output goes into build\<os>-<arch>\ so builds from different machines
REM can be collected together without colliding.

cd /d "%~dp0"

if not exist ".venv\Scripts\python.exe" (
    echo Virtual environment not found. Run install.bat first.
    exit /b 1
)

set "ARCH_NAME=%PROCESSOR_ARCHITECTURE%"
if /i "%ARCH_NAME%"=="AMD64" set "ARCH_NAME=x86_64"
if /i "%ARCH_NAME%"=="ARM64" set "ARCH_NAME=arm64"
set "TAG=windows-%ARCH_NAME%"

for /f "delims=" %%v in ('.venv\Scripts\python.exe -c "from version import __version__; print(__version__)"') do set "APP_VERSION=%%v"

set "BIN_NAME=fivem-artifact-downloader-%APP_VERSION%"
set "OUT_DIR=build\%TAG%-v%APP_VERSION%"
set "WORK_DIR=build\.pyinstaller-work"

echo Building for: %TAG% (v%APP_VERSION%)
echo (This machine can only build for its own architecture - see the
echo  comment at the top of build.bat for how to get the other target.)
echo.

echo Installing PyInstaller into .venv (if missing)...
.venv\Scripts\python.exe -m pip install --quiet --upgrade pyinstaller

if exist "%OUT_DIR%" rmdir /s /q "%OUT_DIR%"
if exist "%WORK_DIR%" rmdir /s /q "%WORK_DIR%"
mkdir "%OUT_DIR%"

.venv\Scripts\python.exe -m PyInstaller ^
    --onefile ^
    --name "%BIN_NAME%" ^
    --distpath "%OUT_DIR%" ^
    --workpath "%WORK_DIR%" ^
    --specpath "%WORK_DIR%" ^
    fivem_tui.py

if not %errorlevel%==0 (
    echo.
    echo Build failed.
    exit /b 1
)

if exist "%WORK_DIR%" rmdir /s /q "%WORK_DIR%"

for /f "delims=" %%v in ('.venv\Scripts\python.exe --version') do set "PY_VERSION=%%v"

(
    echo OS:           windows
    echo Architecture: %ARCH_NAME%
    echo App version:  %APP_VERSION%
    echo Built on:     %date% %time%
    echo Built with:   %PY_VERSION%
    echo.
    echo Built natively on this machine. PyInstaller does not cross-compile - a
    echo binary built here only runs on windows/%ARCH_NAME%.
) > "%OUT_DIR%\BUILD_INFO.txt"

echo.
echo Done. Output: %OUT_DIR%\
endlocal

@echo off
setlocal
cd /d "%~dp0"

echo =======================================================
echo   AppData Orphan Cleaner - Build Native App & Installer
echo =======================================================
echo.

python --version >nul 2>&1
if %errorlevel% neq 0 (
    echo [ERROR] Python is not installed or not in PATH!
    pause
    exit /b 1
)

python -m pip install pyinstaller >nul 2>&1

python scripts\build.py
if %errorlevel% neq 0 (
    echo.
    echo [BUILD FAILED] An error occurred during the build process.
    pause
    exit /b %errorlevel%
)

echo.
echo [DONE] Build completed successfully!
pause

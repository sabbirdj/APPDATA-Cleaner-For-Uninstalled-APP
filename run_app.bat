@echo off
title AppData Orphan Cleaner
cd /d "%~dp0"

echo ===================================================
echo     AppData Orphan Cleaner (Windows 11 Fluent)
echo ===================================================
echo.

echo Checking Python environment...
python --version >nul 2>&1
if %errorlevel% neq 0 (
    echo [ERROR] Python is not installed or not in PATH!
    echo Please install Python 3.10+ from python.org to run this application.
    pause
    exit /b 1
)

echo Checking dependencies...
python -c "import PyQt6, qfluentwidgets, send2trash" >nul 2>&1
if %errorlevel% neq 0 (
    echo Installing required packages...
    python -m pip install -r requirements.txt
    if %errorlevel% neq 0 (
        echo [ERROR] Package installation failed.
        pause
        exit /b 1
    )
)

echo Launching AppData Orphan Cleaner...
python main.py
if %errorlevel% neq 0 (
    echo.
    echo [WARNING] Application exited with an error.
    echo Attempting fallback to Classic UI...
    python main.py --classic
    if %errorlevel% neq 0 (
        echo.
        echo [ERROR] Both Modern and Classic interfaces failed.
        pause
    )
)

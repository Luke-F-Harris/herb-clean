@echo off
REM Windows Setup Script for OSRS Herb Cleaning Bot
REM Run from project root: scripts\windows\setup_windows.bat

cd /d "%~dp0\..\.."

echo ========================================
echo OSRS Herb Cleaning Bot - Windows Setup
echo ========================================
echo.

REM Check Python installation
python --version >nul 2>&1
if errorlevel 1 (
    echo ERROR: Python is not installed or not in PATH
    echo Please install Python 3.10+ from https://www.python.org/
    pause
    exit /b 1
)

echo [1/4] Python found
python --version

REM Create virtual environment
echo.
echo [2/4] Creating virtual environment...
python -m venv venv
if errorlevel 1 (
    echo ERROR: Failed to create virtual environment
    pause
    exit /b 1
)

REM Activate virtual environment
echo.
echo [3/4] Activating virtual environment...
call .\venv\Scripts\activate.bat
if errorlevel 1 (
    echo ERROR: Failed to activate virtual environment
    pause
    exit /b 1
)

REM Install dependencies
echo.
echo [4/4] Installing dependencies...
pip install --upgrade pip
pip install -r requirements.txt
if errorlevel 1 (
    echo ERROR: Failed to install dependencies
    pause
    exit /b 1
)

echo.
echo ========================================
echo Setup complete!
echo ========================================
echo.
echo Next steps:
echo 1. Open RuneLite
echo 2. Capture template images (see docs\README.md)
echo 3. Run: scripts\windows\run_bot.bat
echo.
echo Or activate venv and run: python main.py
echo.
pause

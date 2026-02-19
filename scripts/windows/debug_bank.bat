@echo off
REM Bank matching debug tool
REM Run from project root: scripts\windows\debug_bank.bat

cd /d "%~dp0\..\.."

echo ========================================
echo OSRS Herb Bot - Bank Matching Debug
echo ========================================
echo.

python debug\debug_bank_matching.py

echo.
echo ========================================
echo Script finished.
echo ========================================
pause

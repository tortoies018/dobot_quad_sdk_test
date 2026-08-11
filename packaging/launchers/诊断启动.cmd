@echo off
cd /d "%~dp0"
"%~dp0python.exe" "%~dp0main.py"
echo.
echo Program exited with code %ERRORLEVEL%.
pause

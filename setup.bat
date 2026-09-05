@echo off
cd /d "%~dp0"
echo Installing dependencies (one time)...
python -m pip install -r requirements.txt
echo.
echo Done. You can close this window and double-click start.bat.
pause

@echo off
cd /d "%~dp0"
echo Checking dependencies...
python -m pip install -r requirements.txt --quiet --disable-pip-version-check
echo Starting the Usertour flow builder...
python web\app.py
pause

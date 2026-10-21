@echo off
REM Start Propellant Analyzer from source.
cd /d "%~dp0"
if exist .venv\Scripts\activate.bat call .venv\Scripts\activate.bat
python run.py
if errorlevel 1 pause

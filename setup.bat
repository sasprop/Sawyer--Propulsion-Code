@echo off
REM One-time setup: creates .venv and installs everything needed to run and build.
cd /d "%~dp0"
if not exist .venv (
    echo Creating virtual environment in .venv ...
    python -m venv .venv || goto :error
)
call .venv\Scripts\activate.bat
python -m pip install --upgrade pip
python -m pip install -r requirements-dev.txt || goto :error
echo.
echo Setup complete. Use run.bat to start the app or build.bat to make the .exe.
pause
exit /b 0
:error
echo.
echo Setup failed - see the messages above.
pause
exit /b 1

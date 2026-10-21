@echo off
REM Build the standalone app into dist\PropellantAnalyzer\PropellantAnalyzer.exe
REM   build.bat          one-folder build (fast start-up)
REM   build.bat onefile  single PropellantAnalyzer.exe
cd /d "%~dp0"
if exist .venv\Scripts\activate.bat call .venv\Scripts\activate.bat
if /i "%1"=="onefile" (set ONEFILE=1) else (set ONEFILE=0)
python -m PyInstaller --noconfirm --clean packaging\PropellantAnalyzer.spec || goto :error
for /f "delims=" %%v in ('python -c "import sys; sys.path.insert(0,'src'); import propellant_analyzer as p; print(p.__version__)"') do set VER=%%v
if "%ONEFILE%"=="1" (
    copy /y dist\PropellantAnalyzer.exe "dist\PropellantAnalyzer-%VER%.exe" >nul
    echo Built dist\PropellantAnalyzer-%VER%.exe
) else (
    powershell -NoProfile -Command "Compress-Archive -Force -Path 'dist\PropellantAnalyzer\*' -DestinationPath 'dist\PropellantAnalyzer-%VER%-win64.zip'"
    echo Built dist\PropellantAnalyzer\PropellantAnalyzer.exe
    echo Zipped dist\PropellantAnalyzer-%VER%-win64.zip
)
pause
exit /b 0
:error
echo.
echo Build failed - see the messages above.
pause
exit /b 1

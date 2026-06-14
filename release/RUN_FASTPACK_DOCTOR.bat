@echo off
setlocal
cd /d "%~dp0"
echo Zomboid FastPack Doctor 0.1.0
echo.
FastPackDoctor.exe scan --safe-mode
set EXIT_CODE=%ERRORLEVEL%
echo.
echo Reports: %CD%\outputs\fastpack-report
echo Exit code: %EXIT_CODE%
echo.
pause
exit /b %EXIT_CODE%


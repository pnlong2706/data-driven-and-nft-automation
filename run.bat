@echo off
REM Run all feature suites. One line per feature.
setlocal EnableDelayedExpansion
cd /d "%~dp0"
set "EXITCODE=0"

call Feature_002_Login\run.bat
if errorlevel 1 set "EXITCODE=1"

REM call Feature_XXX\run.bat
REM if errorlevel 1 set "EXITCODE=1"

echo.
if "%EXITCODE%"=="0" (
    echo ALL FEATURES PASSED.
) else (
    echo ONE OR MORE FEATURES FAILED.
)
exit /b %EXITCODE%

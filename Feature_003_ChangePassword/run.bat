@echo off
REM Run Feature 003 (Change Password) suites.
REM   run.bat              -> setup + all three suites
REM   run.bat level1       -> setup + only Level 1
REM   run.bat level2       -> setup + only Level 2
REM   run.bat nf           -> setup + only Non-Functional
setlocal EnableDelayedExpansion
cd /d "%~dp0"

set "PYTHON=..\.venv\Scripts\python.exe"
if not exist "%PYTHON%" set "PYTHON=python"

set "TARGET=%~1"
if "%TARGET%"=="" set "TARGET=all"
set "EXITCODE=0"

call :run_setup
if errorlevel 1 (
    echo.
    echo Setup failed. Aborting test run.
    exit /b 1
)

if /i "%TARGET%"=="all"    call :run_level1 & call :run_level2 & call :run_nf
if /i "%TARGET%"=="level1" call :run_level1
if /i "%TARGET%"=="level2" call :run_level2
if /i "%TARGET%"=="nf"     call :run_nf

echo.
if "%EXITCODE%"=="0" (
    echo ALL SUITES PASSED.
) else (
    echo ONE OR MORE SUITES FAILED.
)
exit /b %EXITCODE%

:run_setup
echo.
echo ========================================================
echo  Setup - Ensure test account is ready
echo ========================================================
"%PYTHON%" -m unittest setup_feature003.SetupFeature003 -v
if errorlevel 1 exit /b 1
exit /b 0

:run_level1
echo.
echo ========================================================
echo  Level 1 - Data-Driven (hard-coded locators)
echo ========================================================
"%PYTHON%" -m unittest Level_1.test_level1_change_password -v
if errorlevel 1 set "EXITCODE=1"
exit /b 0

:run_level2
echo.
echo ========================================================
echo  Level 2 - Fully Data-Driven (config-driven locators)
echo ========================================================
"%PYTHON%" -m unittest Level_2.test_level2_change_password -v
if errorlevel 1 set "EXITCODE=1"
exit /b 0

:run_nf
echo.
echo ========================================================
echo  Non-Functional - Usability and Compatibility
echo ========================================================
"%PYTHON%" -m unittest Non_Functional.test_non_functional_change_password -v
if errorlevel 1 set "EXITCODE=1"
exit /b 0

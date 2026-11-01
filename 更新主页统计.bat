@echo off
setlocal
cd /d "%~dp0"

rem One-click refresh of assets/stats.svg, committed with the owner identity.
rem Interpreter lookup: PROFILE_PYTHON -> py -3 -> python

set "PYCMD="
if defined PROFILE_PYTHON set "PYCMD=%PROFILE_PYTHON%"
if not defined PYCMD (
    where py >nul 2>nul
    if not errorlevel 1 set "PYCMD=py -3"
)
if not defined PYCMD set "PYCMD=python"

echo [1/2] interpreter: %PYCMD%
echo [2/2] regenerating stats card and pushing...
"%PYCMD%" tools\update_stats.py --push
if errorlevel 1 (
    echo.
    echo Refresh failed, see the output above.
    pause
    exit /b 1
)

echo.
echo latest commit:
git log -1 --format="%%h %%an <%%ae>  %%s"
echo.
pause

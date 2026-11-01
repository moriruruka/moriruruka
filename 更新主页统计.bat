@echo off
chcp 65001 >nul
setlocal
cd /d "%~dp0"

rem 一键刷新主页统计卡：重新生成 assets/stats.svg，用维护者身份提交并推送。
rem 解释器查找顺序：环境变量 PROFILE_PYTHON → py -3 → python

set "PYCMD="
if defined PROFILE_PYTHON set "PYCMD=%PROFILE_PYTHON%"
if not defined PYCMD (
    where py >nul 2>nul
    if not errorlevel 1 set "PYCMD=py -3"
)
if not defined PYCMD set "PYCMD=python"

echo [1/2] 解释器：%PYCMD%
echo [2/2] 重新生成统计卡并推送……
%PYCMD% tools\update_stats.py --push
if errorlevel 1 (
    echo.
    echo 刷新失败，请查看上面的输出。
    pause
    exit /b 1
)

echo.
echo 最近一次提交：
git log -1 --format="%%h %%an <%%ae>  %%s"
echo.
pause

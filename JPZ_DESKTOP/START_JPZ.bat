@echo off
chcp 65001 >nul
pushd "%~dp0"
where pythonw >nul 2>&1
if errorlevel 1 goto use_py
start "" pythonw "%~dp0Startprogram.py"
goto done
:use_py
py "%~dp0Startprogram.py"
if errorlevel 1 pause
:done
popd

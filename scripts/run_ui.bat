@echo off
rem Launch the quant desktop UI.
rem usage:  scripts\run_ui.bat            start the UI
rem         scripts\run_ui.bat 000001     open a symbol directly
setlocal
set "ROOT=%~dp0.."
cd /d "%ROOT%"

set "PY=%ROOT%\.venv\Scripts\pythonw.exe"
if not exist "%PY%" set "PY=%ROOT%\.venv\Scripts\python.exe"
if not exist "%PY%" goto novenv

start "" "%PY%" -m quant ui %*
exit /b 0

:novenv
echo [FAIL] .venv not found. Run scripts\bootstrap.bat first.
pause
exit /b 1

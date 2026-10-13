@echo off
rem Rebuild the quant virtual environment.
rem Works with Windows PowerShell 5.1 (no pwsh required) or PowerShell 7 if present.
setlocal
set "SCRIPT_DIR=%~dp0"
set "PS=powershell.exe"
where pwsh.exe >nul 2>nul && set "PS=pwsh.exe"
"%PS%" -NoProfile -ExecutionPolicy Bypass -File "%SCRIPT_DIR%bootstrap.ps1" %*
set "RC=%ERRORLEVEL%"
echo.
if "%RC%"=="0" (echo [OK] bootstrap finished) else (echo [FAIL] bootstrap exit code %RC%)
pause
exit /b %RC%

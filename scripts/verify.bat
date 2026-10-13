@echo off
rem quant environment self-check: config + dependencies + data dir + unit tests
setlocal
set "ROOT=%~dp0.."
pushd "%ROOT%"
set "PY=%ROOT%\.venv\Scripts\python.exe"

if not exist "%PY%" (
  echo [FAIL] .venv\Scripts\python.exe not found
  echo        Run scripts\bootstrap.bat first.
  popd
  pause
  exit /b 1
)

echo ==== quant info ====
"%PY%" -m quant info
echo.
echo ==== quant check ====
"%PY%" -m quant check
echo.
echo ==== pytest ====
"%PY%" -m pytest
set "RC=%ERRORLEVEL%"
echo.
if "%RC%"=="0" (echo [OK] all checks passed) else (echo [FAIL] exit code %RC%)
popd
pause
exit /b %RC%

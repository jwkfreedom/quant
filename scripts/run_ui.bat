@echo off
rem Launch the quant desktop UI.
setlocal
set "ROOT=%~dp0.."
pushd "%ROOT%"
set "PY=%ROOT%\.venv\Scripts\pythonw.exe"
if not exist "%PY%" set "PY=%ROOT%\.venv\Scripts\python.exe"
if not exist "%PY%" (
  echo [FAIL] .venv not found. Run scripts\bootstrap.bat first.
  popd
  pause
  exit /b 1
)
start "" "%PY%" -m quant ui %*
popd
exit /b 0

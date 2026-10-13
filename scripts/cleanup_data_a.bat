@echo off
rem Delete data\a (already migrated to SQLite + archived to data/original).
rem Run by double-click, or from PowerShell: cmd /c scripts\cleanup_data_a.bat
setlocal enabledelayedexpansion
pushd "%~dp0.."

if not exist "data\a" (
  echo [OK] data\a does not exist, nothing to do.
  popd
  pause
  exit /b 0
)

echo Target: %CD%\data\a
echo.
echo This deletes the leftover CSV tree. Its content is already:
echo   - archived under data\original\
echo   - imported into data\quant.db
echo.
for /f "tokens=3" %%a in ('dir /s /-c "data\a" ^| findstr /c:"File(s)"') do set BYTES=%%a
set /a MB=%BYTES%/1048576
echo Size to free: about %MB% MB
echo.

set /p ANSWER="Delete now? [y/N] "
if /i not "%ANSWER%"=="y" (
  echo Cancelled.
  popd
  pause
  exit /b 0
)

rd /s /q "data\a"
if exist "data\a" (
  echo [FAIL] data\a still exists. Try running this file from a normal cmd window.
  popd
  pause
  exit /b 1
)

echo [OK] data\a deleted.
echo Remaining under data:
dir /b data
popd
pause
exit /b 0

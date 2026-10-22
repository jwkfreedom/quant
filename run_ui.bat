@echo off
rem Shortcut at repo root: launch the quant desktop UI.
rem usage:  run_ui             start the UI
rem         run_ui 000001      open a symbol directly
call "%~dp0scripts\run_ui.bat" %*

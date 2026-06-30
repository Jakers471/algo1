@echo off
REM Standalone NQ chart window (TradingView lightweight-charts). Uses the project venv.
set "PY=%~dp0..\..\Launcher\bin\Debug\.venv311\Scripts\python.exe"
cd /d "%~dp0.."
"%PY%" -m tv_chart.serve %*

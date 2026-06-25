@echo off
REM Launch the algoproj web Analyzer (Flask + PyWebView) with the project's Python 3.11 venv.
set "PY=%~dp0..\..\Launcher\bin\Debug\.venv311\Scripts\python.exe"
cd /d "%~dp0.."
"%PY%" -m webui.server %*

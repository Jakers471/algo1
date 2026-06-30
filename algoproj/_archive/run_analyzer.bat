@echo off
REM [ARCHIVED] Old Streamlit Strategy Analyzer UI. Superseded by webui/ (run_webui.bat).
REM Kept for reference; launches with the project's Python 3.11 venv.
set "PY=%~dp0..\..\Launcher\bin\Debug\.venv311\Scripts\python.exe"
"%PY%" -m streamlit run "%~dp0app\analyzer.py"

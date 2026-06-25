@echo off
REM Launch the Strategy Analyzer UI with the project's Python 3.11 venv.
set "PY=%~dp0..\Launcher\bin\Debug\.venv311\Scripts\python.exe"
"%PY%" -m streamlit run "%~dp0app\analyzer.py"

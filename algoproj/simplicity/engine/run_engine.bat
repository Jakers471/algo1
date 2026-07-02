@echo off
REM Fire up the SIMPLICITY engine. Usage:  run_engine.bat  [--debug]
setlocal
set "PY=C:\Users\jakers\Desktop\algo\Launcher\bin\Debug\.venv311\Scripts\python.exe"
if not exist "%PY%" set "PY=python"
"%PY%" "%~dp0run_simplicity.py" %*
endlocal

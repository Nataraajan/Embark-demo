@echo off
cd /d "%~dp0"
set "DEMO_PY=%~dp0..\..\work\venv\Scripts\python.exe"
if not exist "%DEMO_PY%" set "DEMO_PY=python"
"%DEMO_PY%" -m streamlit run app.py --server.port 8507 --server.address 127.0.0.1
pause

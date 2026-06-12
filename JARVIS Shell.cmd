@echo off
setlocal
set "ROOT=%~dp0"
set "JARVIS_PROJECT=%ROOT%jarvis"
set "PYTHONPATH=%JARVIS_PROJECT%;%PYTHONPATH%"

if not exist "%ROOT%.venv\Scripts\python.exe" (
  echo JARVIS launcher could not find Python at "%ROOT%.venv\Scripts\python.exe".
  pause
  exit /b 1
)

"%ROOT%.venv\Scripts\python.exe" -m agenthub shell-window --project "%JARVIS_PROJECT%"
endlocal
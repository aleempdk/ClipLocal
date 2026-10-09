@echo off
cd /d "%~dp0"
if not exist ".venv\Scripts\python.exe" (
  call "%~dp0Setup ClipLocal.cmd"
  if errorlevel 1 (
    pause
    exit /b 1
  )
)
".venv\Scripts\python.exe" app.py
pause

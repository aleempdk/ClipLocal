@echo off
cd /d "%~dp0"
set "CLIP_PY=%~dp0.venv\Scripts\python.exe"
if exist "%CLIP_PY%" goto ready
py -3.12 -c "import sys" >nul 2>nul
if not errorlevel 1 (
  py -3.12 "%~dp0setup.py" %*
  goto finish
)
set "CLIP_PY=%LOCALAPPDATA%\Programs\Python\Python312\python.exe"
if exist "%CLIP_PY%" goto ready
echo Installing Python 3.12 using Windows Package Manager. Review installer prompts.
winget install --id Python.Python.3.12 --exact --source winget
if errorlevel 1 goto failure
if not exist "%CLIP_PY%" (
  echo Close this window and rerun setup to refresh the installed Python launcher.
  goto failure
)
:ready
"%CLIP_PY%" "%~dp0setup.py" %*
:finish
if errorlevel 1 goto failure
pause
exit /b 0
:failure
echo Setup did not finish. Read the message above and rerun when the issue is resolved.
pause
exit /b 1

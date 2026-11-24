@echo off
setlocal
set "AGENT_PYTHON=%USERPROFILE%\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe"
if exist "%AGENT_PYTHON%" (
  "%AGENT_PYTHON%" -E -s -B -c "import tkinter" >nul 2>nul
  if not errorlevel 1 goto bundled
)
python -E -s -B "%~dp0agent\install_desktop.py" %*
goto finish
:bundled
"%AGENT_PYTHON%" -E -s -B "%~dp0agent\install_desktop.py" %*
:finish
set "RESULT=%ERRORLEVEL%"
pause
exit /b %RESULT%

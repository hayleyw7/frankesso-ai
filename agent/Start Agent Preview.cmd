@echo off
setlocal
cd /d "%~dp0"
set "AGENT_PYTHON=%USERPROFILE%\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe"
if exist "%AGENT_PYTHON%" (
  "%AGENT_PYTHON%" -B run_agent.py
) else (
  python -B run_agent.py
)
pause
endlocal

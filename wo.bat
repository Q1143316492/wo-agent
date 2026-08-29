@echo off
setlocal
set "PYTHON=%~dp0.venv\Scripts\python.exe"
if not exist "%PYTHON%" (
    echo [wo-agent] .venv not found. Run:
    echo   python -m venv .venv
    echo   .venv\Scripts\pip install -e ".[cli]"
    exit /b 1
)
"%PYTHON%" -m cli %*
endlocal

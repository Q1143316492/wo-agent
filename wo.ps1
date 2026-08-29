$ErrorActionPreference = 'Stop'
$root = Split-Path -Parent $MyInvocation.MyCommand.Path
$python = Join-Path $root '.venv\Scripts\python.exe'

if (-not (Test-Path $python)) {
    Write-Host '[wo-agent] .venv not found. Run:' -ForegroundColor Red
    Write-Host '  python -m venv .venv' -ForegroundColor Red
    Write-Host '  .venv\Scripts\pip install -e ".[cli]"' -ForegroundColor Red
    exit 1
}

& $python -m cli @args
exit $LASTEXITCODE

# start.ps1 — Windows production launcher
# Usage: .\start.ps1
# Requires: uv, node/npm

$ErrorActionPreference = "Stop"
$ProjectRoot = $PSScriptRoot

Write-Host "Setting up Python environment..." -ForegroundColor Cyan
Set-Location $ProjectRoot

# uv sync reads pyproject.toml, creates .venv, installs all deps
uv sync

$activate = Join-Path $ProjectRoot ".venv\Scripts\Activate.ps1"
if (Test-Path $activate) { & $activate }

Write-Host "Building frontend..." -ForegroundColor Cyan
Set-Location (Join-Path $ProjectRoot "frontend")
npm install --silent
npm run build
Set-Location $ProjectRoot

Write-Host "Starting bot..." -ForegroundColor Green
$python = Join-Path $ProjectRoot ".venv\Scripts\python.exe"
& $python -m uvicorn backend.main:app --host 0.0.0.0 --port 8000 --workers 1

Write-Host "Bot running at http://localhost:8000" -ForegroundColor White

# dev.ps1 - Windows development launcher
# Usage: .\dev.ps1
# Opens backend and frontend each in their own PowerShell window.

$ErrorActionPreference = "Stop"
$ProjectRoot = $PSScriptRoot

# ── 1. Python deps via uv ─────────────────────────────────────────────────────
Write-Host "[1/3] Syncing Python dependencies..." -ForegroundColor Cyan
Set-Location $ProjectRoot
uv sync

# ── 2. Frontend deps ──────────────────────────────────────────────────────────
Write-Host "[2/3] Installing frontend dependencies..." -ForegroundColor Cyan
Set-Location (Join-Path $ProjectRoot "frontend")
npm install --silent
Set-Location $ProjectRoot

# ── 3. Launch servers in separate windows ─────────────────────────────────────
Write-Host "[3/3] Launching servers..." -ForegroundColor Cyan

$python = Join-Path $ProjectRoot ".venv\Scripts\python.exe"

# Backend window
Start-Process powershell -ArgumentList "-NoExit", "-Command", `
    "Set-Location '$ProjectRoot'; Write-Host 'Backend starting...' -ForegroundColor Green; & '$python' -m uvicorn backend.main:app --reload --port 8000"

# Frontend window
Start-Process powershell -ArgumentList "-NoExit", "-Command", `
    "Set-Location '$ProjectRoot\frontend'; Write-Host 'Frontend starting...' -ForegroundColor Magenta; npm run dev -- --port 5173"

Write-Host ""
Write-Host "Two windows opened:" -ForegroundColor White
Write-Host "  Backend  -->  http://localhost:8000" -ForegroundColor Blue
Write-Host "  Frontend -->  http://localhost:5173" -ForegroundColor Magenta
Write-Host "  API docs -->  http://localhost:8000/docs" -ForegroundColor DarkGray
Write-Host ""
Write-Host "Close those windows to stop the servers." -ForegroundColor Yellow

# dev.ps1 — Windows development launcher (hot reload)
# Usage: .\dev.ps1
# Requires: uv (Python), node/npm (frontend), Python 3.11+

$ErrorActionPreference = "Stop"
$ProjectRoot = $PSScriptRoot

# ── 1. Python virtual environment via uv ─────────────────────────────────────
Write-Host "Setting up Python environment with uv..." -ForegroundColor Cyan
Set-Location $ProjectRoot

# uv sync reads pyproject.toml, creates .venv, installs all deps + dev deps
uv sync --extra dev

# Activate venv for this session
$activate = Join-Path $ProjectRoot ".venv\Scripts\Activate.ps1"
if (Test-Path $activate) { & $activate }

# ── 2. Frontend dependencies ──────────────────────────────────────────────────
Write-Host "Installing frontend dependencies..." -ForegroundColor Cyan
Set-Location (Join-Path $ProjectRoot "frontend")
npm install --silent
Set-Location $ProjectRoot

# ── 3. Start backend (hot reload) ────────────────────────────────────────────
Write-Host ""
Write-Host "Starting backend on http://localhost:8000 (hot reload)..." -ForegroundColor Green
$backendJob = Start-Job -ScriptBlock {
    param($root, $venv)
    Set-Location $root
    $python = Join-Path $venv "Scripts\python.exe"
    & $python -m uvicorn backend.main:app --reload --port 8000
} -ArgumentList $ProjectRoot, (Join-Path $ProjectRoot ".venv")

# ── 4. Start frontend dev server ──────────────────────────────────────────────
Write-Host "Starting frontend on http://localhost:5173 ..." -ForegroundColor Green
$frontendJob = Start-Job -ScriptBlock {
    param($root)
    Set-Location (Join-Path $root "frontend")
    npm run dev -- --port 5173
} -ArgumentList $ProjectRoot

Write-Host ""
Write-Host "─────────────────────────────────────────" -ForegroundColor DarkGray
Write-Host "  Backend  →  http://localhost:8000      " -ForegroundColor White
Write-Host "  Frontend →  http://localhost:5173      " -ForegroundColor White
Write-Host "─────────────────────────────────────────" -ForegroundColor DarkGray
Write-Host "Press Ctrl+C to stop both servers." -ForegroundColor Yellow
Write-Host ""

# ── 5. Stream combined output and wait ───────────────────────────────────────
try {
    while ($true) {
        Receive-Job $backendJob  2>&1 | ForEach-Object { Write-Host "[backend]  $_" -ForegroundColor Blue }
        Receive-Job $frontendJob 2>&1 | ForEach-Object { Write-Host "[frontend] $_" -ForegroundColor Magenta }
        Start-Sleep -Milliseconds 500

        if ($backendJob.State -eq "Failed" -or $frontendJob.State -eq "Failed") {
            Write-Host "A server process failed. Check output above." -ForegroundColor Red
            break
        }
    }
}
finally {
    Write-Host "Stopping servers..." -ForegroundColor Yellow
    Stop-Job  $backendJob, $frontendJob -ErrorAction SilentlyContinue
    Remove-Job $backendJob, $frontendJob -Force -ErrorAction SilentlyContinue
    Write-Host "Done." -ForegroundColor Gray
}

# OmokGosu 개발 실행기
# - uvicorn(8000) + vite(5173)을 별개 PowerShell 창에서 병렬 실행
# - 두 창 모두 닫으면 자동 종료

$ErrorActionPreference = "Stop"
$root = Split-Path -Parent $PSScriptRoot
$venvPython = Join-Path $root ".venv\Scripts\python.exe"

if (-not (Test-Path $venvPython)) {
    Write-Error "venv not found at $venvPython. Run .\scripts\bootstrap.ps1 first."
}

Write-Host "[dev] Starting uvicorn on http://localhost:8000" -ForegroundColor Cyan
$serverDir = Join-Path $root "server"
Start-Process powershell -ArgumentList @(
    "-NoExit",
    "-Command",
    "cd `"$serverDir`"; & `"$venvPython`" -m uvicorn omok_server.main:app --reload --port 8000"
)

Write-Host "[dev] Starting vite on http://localhost:5173" -ForegroundColor Cyan
$webDir = Join-Path $root "web"
$pnpm = (Get-Command pnpm -ErrorAction SilentlyContinue)
$cmd = if ($pnpm) { "pnpm dev" } else { "npm run dev" }
Start-Process powershell -ArgumentList @(
    "-NoExit",
    "-Command",
    "cd `"$webDir`"; $cmd"
)

Write-Host "[dev] Servers launched in separate windows. Open http://localhost:5173." -ForegroundColor Green

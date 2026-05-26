# OmokGosu 부트스트랩
# - Python venv 생성 / 활성화
# - omok_core (C++ pybind11) 빌드 + editable install
# - server 패키지 editable install
# - web 의존성 설치 (pnpm 우선, npm 폴백)

$ErrorActionPreference = "Stop"
$root = Split-Path -Parent $PSScriptRoot

. (Join-Path $PSScriptRoot "_vsenv.ps1")

Write-Host "[bootstrap] Project root: $root" -ForegroundColor Cyan

# --- Python ---
$venvPath = Join-Path $root ".venv"
if (-not (Test-Path $venvPath)) {
    Write-Host "[bootstrap] Creating Python venv at $venvPath" -ForegroundColor Cyan
    & python -m venv $venvPath
}

$python = Join-Path $venvPath "Scripts\python.exe"
$pip = Join-Path $venvPath "Scripts\pip.exe"

function Invoke-Checked {
    param([scriptblock]$Block, [string]$Stage)
    & $Block
    if ($LASTEXITCODE -ne 0) {
        Write-Host "[bootstrap] FAILED at: $Stage (exit $LASTEXITCODE)" -ForegroundColor Red
        exit $LASTEXITCODE
    }
}

Write-Host "[bootstrap] Upgrading pip / wheel / scikit-build-core / pybind11" -ForegroundColor Cyan
Invoke-Checked { & $python -m pip install --upgrade pip wheel setuptools } "pip upgrade"
Invoke-Checked { & $pip install "scikit-build-core>=0.9" "pybind11>=2.12" } "scikit-build-core + pybind11"

Write-Host "[bootstrap] Installing omok_core (editable, builds C++ via CMake)" -ForegroundColor Cyan
Push-Location $root
try {
    Invoke-Checked { & $pip install -e . --no-build-isolation -v } "omok_core build"
} finally {
    Pop-Location
}

Write-Host "[bootstrap] Installing omok-server (editable, with dev extras)" -ForegroundColor Cyan
Push-Location (Join-Path $root "server")
try {
    Invoke-Checked { & $pip install -e ".[dev]" } "omok-server install"
} finally {
    Pop-Location
}

# --- web ---
Write-Host "[bootstrap] Installing web dependencies" -ForegroundColor Cyan
Push-Location (Join-Path $root "web")
try {
    $pnpm = (Get-Command pnpm -ErrorAction SilentlyContinue)
    if ($pnpm) {
        & pnpm install
    } else {
        Write-Warning "pnpm not found; falling back to npm install"
        & npm install
    }
} finally {
    Pop-Location
}

Write-Host "[bootstrap] Done. Run .\scripts\dev.ps1 to start dev servers." -ForegroundColor Green

# OmokGosu — build the Windows .exe installer.
#
# Output: D:\OmokGosu\dist-electron\OmokGosu-Setup-<version>.exe (~80MB NSIS installer)
#
# Prereqs:
#   - Node 18+ (`node --version`)
#   - electron/assets/icon.ico exists
#   - electron/ npm deps installed (script auto-runs npm install if missing)
#
# Usage:
#   .\scripts\build_electron.ps1

$ErrorActionPreference = "Continue"
$root = Split-Path -Parent $PSScriptRoot

# 1. Verify VERSION matches all propagation targets — including electron/package.json
& (Join-Path $PSScriptRoot "sync_version.ps1") -Verify
if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }

# 2. Ensure electron deps are installed
$electronDir = Join-Path $root "electron"
if (-not (Test-Path (Join-Path $electronDir "node_modules"))) {
    Write-Host "[build_electron] npm install (first time)" -ForegroundColor Cyan
    Push-Location $electronDir
    try {
        & npm install
        if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }
    } finally {
        Pop-Location
    }
}

# 3. Build installer
Write-Host "[build_electron] electron-builder --win --x64" -ForegroundColor Cyan
Push-Location $electronDir
try {
    & npm run dist
    $code = $LASTEXITCODE
} finally {
    Pop-Location
}

if ($code -ne 0) {
    Write-Host "[build_electron] FAILED (exit $code)" -ForegroundColor Red
    exit $code
}

$outDir = Join-Path $root "dist-electron"
$installer = Get-ChildItem -Path $outDir -Filter "OmokGosu-Setup-*.exe" -ErrorAction SilentlyContinue |
             Sort-Object LastWriteTime -Descending | Select-Object -First 1

if ($installer) {
    $sizeMb = [math]::Round($installer.Length / 1MB, 1)
    Write-Host ""
    Write-Host ("[build_electron] DONE: {0} ({1} MB)" -f $installer.FullName, $sizeMb) -ForegroundColor Green
} else {
    Write-Host "[build_electron] WARNING: installer not found in $outDir" -ForegroundColor Yellow
}

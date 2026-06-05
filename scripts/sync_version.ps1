# OmokGosu — VERSION 파일을 모든 곳으로 propagate
#
# 사용:
#   .\scripts\sync_version.ps1           # 실제 변경
#   .\scripts\sync_version.ps1 -DryRun   # 변경 예정 출력만
#   .\scripts\sync_version.ps1 -Verify   # 일치 여부 검사 (CI/사전체크용, 종료코드 0=일치, 1=불일치)

param(
    [switch]$DryRun,
    [switch]$Verify
)

$ErrorActionPreference = "Stop"
$root = Split-Path -Parent $PSScriptRoot

$versionFile = Join-Path $root "VERSION"
if (-not (Test-Path $versionFile)) {
    Write-Host "[sync_version] VERSION file not found: $versionFile" -ForegroundColor Red
    exit 1
}

$version = (Get-Content $versionFile -Raw).Trim()
if ($version -notmatch '^\d+\.\d+\.\d+$') {
    Write-Host "[sync_version] Invalid semver: '$version' (expected like 1.0.0)" -ForegroundColor Red
    exit 1
}

# Path -> (pattern to match current value, replacement text)
$targets = @(
    @{
        Path    = Join-Path $root "pyproject.toml"
        Pattern = '(?m)^version\s*=\s*"[^"]*"'
        Replace = "version = `"$version`""
    },
    @{
        Path    = Join-Path $root "server\pyproject.toml"
        Pattern = '(?m)^version\s*=\s*"[^"]*"'
        Replace = "version = `"$version`""
    },
    @{
        Path    = Join-Path $root "web\package.json"
        Pattern = '"version"\s*:\s*"[^"]*"'
        Replace = "`"version`": `"$version`""
    },
    @{
        Path    = Join-Path $root "server\omok_server\__init__.py"
        Pattern = '__version__\s*=\s*"[^"]*"'
        Replace = "__version__ = `"$version`""
    },
    @{
        Path    = Join-Path $root "CMakeLists.txt"
        Pattern = 'project\(omok_core\s+LANGUAGES\s+CXX\s+VERSION\s+\d+\.\d+\.\d+\)'
        Replace = "project(omok_core LANGUAGES CXX VERSION $version)"
    }
    # electron/package.json is auto-added below if it exists (created in Phase D-5)
)

$electronPkg = Join-Path $root "electron\package.json"
if (Test-Path $electronPkg) {
    $targets += @{
        Path    = $electronPkg
        Pattern = '"version"\s*:\s*"[^"]*"'
        Replace = "`"version`": `"$version`""
    }
}

$mismatches = 0
$changes = 0

foreach ($t in $targets) {
    $path = $t.Path
    $relPath = $path.Substring($root.Length + 1)
    if (-not (Test-Path $path)) {
        Write-Host ("[sync_version] missing: {0}" -f $relPath) -ForegroundColor Yellow
        continue
    }
    $raw = Get-Content $path -Raw
    if ($raw -notmatch $t.Pattern) {
        Write-Host ("[sync_version] pattern not matched in {0}" -f $relPath) -ForegroundColor Red
        $mismatches++
        continue
    }
    $current = ([regex]$t.Pattern).Match($raw).Value
    $new = $t.Replace

    if ($current -eq $new) {
        if (-not $Verify) {
            Write-Host ("[sync_version] {0} : already at {1}" -f $relPath, $version) -ForegroundColor DarkGray
        }
        continue
    }

    if ($Verify) {
        Write-Host ("[sync_version] FAIL {0} : {1} -> {2} expected" -f $relPath, $current, $new) -ForegroundColor Red
        $mismatches++
        continue
    }

    if ($DryRun) {
        Write-Host ("[sync_version] DRY {0} : {1} -> {2}" -f $relPath, $current, $new) -ForegroundColor Cyan
        $changes++
        continue
    }

    $updated = $raw -replace $t.Pattern, $new
    Set-Content -Path $path -Value $updated -NoNewline
    Write-Host ("[sync_version] {0} : {1} -> {2}" -f $relPath, $current, $new) -ForegroundColor Green
    $changes++
}

if ($Verify) {
    if ($mismatches -gt 0) {
        Write-Host ("[sync_version] VERIFY FAILED — {0} mismatches (VERSION = {1})" -f $mismatches, $version) -ForegroundColor Red
        exit 1
    }
    Write-Host ("[sync_version] VERIFY OK — all files at {0}" -f $version) -ForegroundColor Green
    exit 0
}

if ($mismatches -gt 0) {
    Write-Host ("[sync_version] pattern match failed in {0} files" -f $mismatches) -ForegroundColor Red
    exit 1
}

if ($DryRun) {
    Write-Host ("[sync_version] DRY RUN — {0} files would change (VERSION = {1})" -f $changes, $version) -ForegroundColor Cyan
} else {
    Write-Host ("[sync_version] DONE — {0} files updated (VERSION = {1})" -f $changes, $version) -ForegroundColor Green
}

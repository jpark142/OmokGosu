# OmokGosu — 원샷 테스트 러너
#
# C++ 단위 테스트(doctest)와 Python 테스트(pytest)를 모두 실행.
# VS 개발 환경은 자동 로드되므로 그냥 일반 PowerShell에서 호출하면 됨.
#
# 옵션:
#   -SkipPython     pytest 건너뜀
#   -SkipCpp        C++ 빌드/테스트 건너뜀

param(
    [switch]$SkipPython,
    [switch]$SkipCpp
)

# 네이티브 exe (cmake, cl, doctest)의 stderr 한 줄이 ErrorRecord로 둔갑해
# 스크립트를 죽이지 않도록 Continue로 둠. 실패는 $LASTEXITCODE로 직접 체크.
$ErrorActionPreference = "Continue"

$root = Split-Path -Parent $PSScriptRoot
$cppOk = $true
$pyOk  = $true

if (-not $SkipCpp) {
    . (Join-Path $PSScriptRoot "_vsenv.ps1")

    $buildDir = Join-Path $root "build\cpp-tests"
    Write-Host ""
    Write-Host "[test] [C++] Configuring + building" -ForegroundColor Cyan
    & cmake -S $root -B $buildDir -DOMOK_BUILD_TESTS=ON -DOMOK_BUILD_PYBIND=OFF
    if ($LASTEXITCODE -ne 0) { $cppOk = $false }

    if ($cppOk) {
        & cmake --build $buildDir --config Release --parallel
        if ($LASTEXITCODE -ne 0) { $cppOk = $false }
    }

    if ($cppOk) {
        $exe = Join-Path $buildDir "cpp\Release\omok_tests.exe"
        Write-Host ""
        Write-Host "[test] [C++] Running $exe" -ForegroundColor Cyan
        & $exe
        if ($LASTEXITCODE -ne 0) { $cppOk = $false }
    }
}

if (-not $SkipPython) {
    $python = Join-Path $root ".venv\Scripts\python.exe"
    if (-not (Test-Path $python)) {
        Write-Host ""
        Write-Host "[test] [PY ] venv 없음 — pytest 건너뜀 (.\scripts\bootstrap.ps1 먼저 실행)" -ForegroundColor Yellow
    } else {
        Push-Location (Join-Path $root "server")
        try {
            Write-Host ""
            Write-Host "[test] [PY ] pytest -q" -ForegroundColor Cyan
            & $python -m pytest -q
            if ($LASTEXITCODE -ne 0) { $pyOk = $false }
        } finally {
            Pop-Location
        }
    }
}

Write-Host ""
if ($cppOk -and $pyOk) {
    Write-Host "[test] ALL GREEN" -ForegroundColor Green
    exit 0
} else {
    Write-Host "[test] FAILED  (C++: $cppOk, Python: $pyOk)" -ForegroundColor Red
    exit 1
}

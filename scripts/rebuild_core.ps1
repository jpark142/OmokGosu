# OmokGosu — omok_core (pybind11 모듈) 재빌드만 빠르게
#
# C++ 코드를 바꾼 뒤 Python 서버가 새 클래스/함수를 보게 만들 때 사용.
# uvicorn이 떠 있으면 .pyd 파일이 잠겨 실패하므로 먼저 끄세요.

$ErrorActionPreference = "Stop"
$root = Split-Path -Parent $PSScriptRoot

. (Join-Path $PSScriptRoot "_vsenv.ps1")

$python = Join-Path $root ".venv\Scripts\python.exe"
if (-not (Test-Path $python)) {
    Write-Host "[rebuild_core] venv가 없습니다. 먼저 .\scripts\bootstrap.ps1 을 실행하세요." -ForegroundColor Red
    exit 1
}

Push-Location $root
try {
    Write-Host "[rebuild_core] pip install -e . --no-build-isolation" -ForegroundColor Cyan
    & $python -m pip install -e . --no-build-isolation
} finally {
    Pop-Location
}
exit $LASTEXITCODE

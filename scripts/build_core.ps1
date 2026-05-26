# OmokGosu — C++ 코어 빌드 + 테스트 실행
#
# 사용: .\scripts\build_core.ps1
#       (일반 PowerShell에서 바로 OK — VS 환경 자동 로드)

$ErrorActionPreference = "Continue"
$root = Split-Path -Parent $PSScriptRoot

. (Join-Path $PSScriptRoot "_vsenv.ps1")

$buildDir = Join-Path $root "build\cpp-tests"

Write-Host "[build_core] Configuring CMake at $buildDir" -ForegroundColor Cyan
& cmake -S $root -B $buildDir -DOMOK_BUILD_TESTS=ON -DOMOK_BUILD_PYBIND=OFF
if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }

Write-Host "[build_core] Building" -ForegroundColor Cyan
& cmake --build $buildDir --config Release --parallel
if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }

$exe = Join-Path $buildDir "cpp\Release\omok_tests.exe"
Write-Host "[build_core] Running $exe" -ForegroundColor Cyan
& $exe
exit $LASTEXITCODE

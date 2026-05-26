# OmokGosu — VS Dev Shell 자동 로더
#
# cmake.exe가 현재 PATH에 없으면 Visual Studio 2022의 Launch-VsDevShell.ps1을
# 자동 실행해 환경변수를 채워줌. 이미 있으면 no-op.
#
# 사용법: 다른 스크립트 상단에서  . (Join-Path $PSScriptRoot "_vsenv.ps1")
# 처럼 dot-source. 환경변수는 $env:PATH 등 프로세스 단위라 호출 후에도 유지됨.

function Ensure-VsEnv {
    if (Get-Command cmake -ErrorAction SilentlyContinue) {
        return
    }

    $candidates = @(
        "C:\Program Files\Microsoft Visual Studio\2022\Community\Common7\Tools\Launch-VsDevShell.ps1",
        "C:\Program Files\Microsoft Visual Studio\2022\Professional\Common7\Tools\Launch-VsDevShell.ps1",
        "C:\Program Files\Microsoft Visual Studio\2022\Enterprise\Common7\Tools\Launch-VsDevShell.ps1",
        "C:\Program Files\Microsoft Visual Studio\2022\BuildTools\Common7\Tools\Launch-VsDevShell.ps1",
        "C:\Program Files (x86)\Microsoft Visual Studio\2022\BuildTools\Common7\Tools\Launch-VsDevShell.ps1"
    )
    $found = $candidates | Where-Object { Test-Path $_ } | Select-Object -First 1
    if (-not $found) {
        Write-Host "[vsenv] Visual Studio 2022 Dev Shell 스크립트를 못 찾았습니다." -ForegroundColor Red
        Write-Host "        설치 위치 후보:" -ForegroundColor Red
        $candidates | ForEach-Object { Write-Host "          $_" -ForegroundColor DarkGray }
        Write-Host "        VS 2022 (또는 Build Tools)의 'C++ 데스크톱 개발' 워크로드를 설치하세요." -ForegroundColor Red
        exit 1
    }

    Write-Host "[vsenv] Loading VS Dev Shell from: $found" -ForegroundColor DarkGray
    # vswhere.exe 부재 시 한국어 경고가 노이즈로 떠서 stderr만 버림.
    & $found -Arch amd64 -HostArch amd64 -SkipAutomaticLocation 2>$null | Out-Null

    if (-not (Get-Command cmake -ErrorAction SilentlyContinue)) {
        Write-Host "[vsenv] Launch-VsDevShell 실행 후에도 cmake가 PATH에 없습니다." -ForegroundColor Red
        exit 1
    }
}

Ensure-VsEnv

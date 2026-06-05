# OmokGosu — Electron 데스크탑 앱 빌드 가이드

`electron/` 디렉토리는 OmokGosu 웹 앱을 감싸는 **얇은 Chromium shell**.
실제 UI/로직은 클라우드(`https://omokgosu.fly.dev`)에서 받아옴.
새 기능 배포는 서버에 `flyctl deploy`만 하면 되고, `.exe` 자체는 거의 안 바꿈.

## 1. 사전 준비 (1회)

```powershell
# Node 확인
node --version    # 18+ 필요

# electron 의존성 설치
cd D:\OmokGosu\electron
npm install
```

`npm install`은 ~5분 (Electron 자체가 100MB+ 다운로드). 한 번만.

### 아이콘 만들기

`electron/assets/icon.ico` 가 있어야 빌드 가능. 256x256 권장.
임시로 적당한 PNG → https://www.icoconverter.com 같은 변환기로 .ico 생성.
같이 `icon.png`도 두면 향후 Mac/Linux 빌드에 사용.

## 2. 로컬 테스트 (실제 빌드 전)

```powershell
cd D:\OmokGosu\electron
# 클라우드 서버 사용 (기본)
npm start

# 또는 로컬 dev 서버
$env:OMOKGOSU_URL = "http://localhost:8000"
npm start
```

Electron 창이 열리고 OmokGosu UI 로드되면 OK.

## 3. .exe installer 빌드

```powershell
cd D:\OmokGosu
.\scripts\build_electron.ps1
```

스크립트가:
1. `sync_version.ps1 -Verify`로 모든 버전 일치 확인
2. `electron/node_modules` 없으면 `npm install`
3. `electron-builder --win --x64`로 NSIS installer 생성
4. 결과 경로 출력

결과물:
```
D:\OmokGosu\dist-electron\OmokGosu-Setup-1.0.0.exe  (~80MB)
```

## 4. 코워커에게 배포

- **사내 파일 공유**: 사내 NAS / SharePoint / 메신저 첨부로 .exe 전송
- **GitHub Releases** (선택): 매 버전 tag → release 만들어서 .exe 첨부. 코워커는 stable 링크로 다운로드
- **자체 호스팅**: Fly 서버에 `/downloads/` 경로 추가해 .exe 호스팅 (선택)

코워커는 .exe 더블클릭:
1. SmartScreen 경고 ("알 수 없는 게시자") — "추가 정보" → "실행" 한 번
2. NSIS 마법사 — 설치 경로 선택 (기본값 `%LOCALAPPDATA%\Programs\OmokGosu`)
3. 시작 메뉴 + 바탕화면 아이콘 자동 생성
4. 아이콘 더블클릭 → 독립 창에서 OmokGosu 실행

## 5. 새 버전 배포 워크플로

대부분의 변경(UI, 로직, 버그 수정)은 **Electron .exe 재빌드 불필요**:

```powershell
# 1. VERSION bump
"1.0.1" | Set-Content VERSION
.\scripts\sync_version.ps1

# 2. 서버 + frontend 코드 변경

# 3. Fly에 배포
flyctl deploy

# 4. 코워커: 다음 60초 안에 Electron 창에서 배너 → "지금 새로고침" → 새 버전
```

**Electron shell 자체를 바꿔야 하는 경우** (드뭄):
- 새 시스템 통합 (트레이 아이콘, 알림, 단축키)
- Electron 보안 업데이트
- 창 크기/타이틀 같은 외관 변경
- APP_URL 도메인 변경

이런 경우만:
```powershell
# 위 1-3 + 추가로
.\scripts\build_electron.ps1
# → dist-electron/OmokGosu-Setup-1.0.1.exe
# → 코워커에게 재배포
```

## 6. 자동 업데이트 (향후 옵션)

현재는 `.exe` 자체는 수동 재설치. 자동화하려면 `electron-updater` + GitHub Releases:

```js
// main.cjs에 추가
const { autoUpdater } = require("electron-updater");
app.whenReady().then(() => {
  createWindow();
  autoUpdater.checkForUpdatesAndNotify();
});
```

+ `package.json`의 `build`에 `publish` 설정. 미구현 — 필요해지면 추가.

## 7. 코드 서명 (SmartScreen 경고 제거)

현재는 코드 서명 안 함 → Windows SmartScreen이 "알 수 없는 게시자" 경고 표시.
코워커가 한 번만 "추가 정보" → "실행" 누르면 그 다음부터는 안 뜸.

회사 정책상 차단되거나 신뢰감을 높이고 싶으면:
- EV Code Signing Certificate (~$300/년, DigiCert/Sectigo)
- `electron-builder`의 `win.certificateFile` + 비번 설정
- 빌드 후 자동으로 서명됨

## 8. 트러블슈팅

- **`npm install` 실패 (Electron 다운로드)**: 회사 프록시 환경. `$env:ELECTRON_MIRROR = "https://npmmirror.com/mirrors/electron/"` 시도
- **빌드 시 "icon.ico not found"**: `electron/assets/icon.ico` 만들기 (위 1번 섹션)
- **`.exe` 실행 시 흰 화면**: APP_URL 잘못된 경우. `OMOKGOSU_URL=http://localhost:8000 npm start`로 dev에서 먼저 검증
- **80MB가 너무 큼**: Tauri로 가면 ~10MB. 다만 Rust 빌드 환경 + 별도 작업 필요. 향후 옵션
- **Mac/Linux도 빌드하려면**: `electron-builder --mac --linux` (각 OS에서 빌드 필요)

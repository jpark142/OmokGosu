# OmokGosu — Fly.io 배포 가이드

OmokGosu를 Fly.io에 도커 이미지로 배포해 `https://omokgosu.fly.dev` 같은 공개 URL로
서비스한다. HTTPS / WSS / 인증서는 Fly가 알아서 처리.

## 1. 사전 준비 (1회)

### Fly CLI 설치 (Windows PowerShell)

```powershell
iwr https://fly.io/install.ps1 -useb | iex
```

설치 후 새 PowerShell 창에서 `flyctl version`이 동작하는지 확인.

### Fly 계정 + 결제카드 등록

```powershell
flyctl auth signup
```

브라우저가 열림 → 계정 만들고 결제 카드 등록 (2024년부터 무료 티어 폐지, 단 OmokGosu 트래픽
수준이면 월 $2-5 수준의 최소 청구).

## 2. 앱 생성 + 볼륨 (1회)

```powershell
cd D:\OmokGosu

# fly.toml은 이미 작성돼있으므로 launch는 --copy-config로 그대로 사용
flyctl launch --name omokgosu --region nrt --no-deploy --copy-config

# SQLite를 위한 영속 볼륨 (1GB로 시작; SQLite는 가벼움)
flyctl volumes create omokgosu_data --region nrt --size 1

# JWT 시크릿 생성 + 등록 (서버 측만 알아야 함)
$secret = & D:\OmokGosu\.venv\Scripts\python.exe -c "import secrets;print(secrets.token_urlsafe(32))"
flyctl secrets set OMOK_JWT_SECRET=$secret
```

`omokgosu` 이름이 이미 사용 중이면 다른 이름 (예: `omokgosu-jpark142`)으로 시도하고
`fly.toml`의 `app = ...`도 같이 수정.

## 3. 배포

```powershell
flyctl deploy
```

도커 이미지를 Fly의 빌더에서 빌드 (`Dockerfile` 사용) → Tokyo 리전에 배포.
최초 빌드는 C++ 컴파일 때문에 3-5분 걸림. 이후 incremental 빌드는 빠름 (Docker 레이어 캐시).

배포 완료되면 `https://omokgosu.fly.dev` (또는 너가 정한 앱 이름) 접속.

## 4. 운영 명령어

```powershell
flyctl status              # 머신 상태
flyctl logs                # 실시간 로그
flyctl ssh console         # 컨테이너 안에 셸
flyctl ssh sftp shell      # 파일 전송 (SQLite 백업용)
flyctl scale show          # 현재 사양
flyctl secrets list        # secret 이름 목록 (값은 안 보임)
```

### SQLite 백업

```powershell
flyctl ssh sftp shell
# sftp> get /data/omok.sqlite ./omok-backup-$(Get-Date -Format yyyyMMdd).sqlite
```

cron이나 작업 스케줄러로 주기적으로 돌리면 좋음.

## 5. 새 버전 배포

```powershell
# 1. 버전 bump
"1.0.1" | Set-Content VERSION
.\scripts\sync_version.ps1

# 2. (MINOR/MAJOR면) server/omok_server/version.py의 MIN_CLIENT_VERSION 같이 bump

# 3. 로컬 검증
.\scripts\test.ps1

# 4. 배포
flyctl deploy
```

배포 후 사용자에게 알릴 필요 없음 — 열린 탭들이 60초 안에 새 버전 감지하고
soft 배너 또는 hard 모달 표시.

## 6. 트러블슈팅

- **빌드 실패 (C++ 단계)**: `flyctl logs --no-tail` 로 빌드 출력 확인. `requirements`에 빠진 게 있으면 `Dockerfile`의 apt 패키지에 추가 (예: `gfortran`은 필요 없을 듯).
- **`/api/health`가 502/503**: `flyctl logs`로 uvicorn 에러 확인. 가장 흔한 건 `OMOK_JWT_SECRET` 미설정 → `flyctl secrets list`로 확인.
- **WS 연결 실패**: Fly는 HTTP/HTTPS만 자동으로 라우팅하지만 WSS는 HTTPS 위에 정상 동작함. `wss://omokgosu.fly.dev/ws/...` 로 접속되는지 브라우저 콘솔 확인.
- **DB 데이터 사라짐**: 배포 시점에 컨테이너는 새 머신에 올라가지만 `/data` 볼륨은 그대로 attach. 볼륨이 다른 region에 있으면 못 붙음 → `flyctl volumes list`로 확인.
- **콜드 스타트가 느림**: `min_machines_running = 1`로 항상 켜둠. 그래도 첫 요청 1-2초 늦으면 `[[vm]] memory_mb`를 1024로 올려보기.

## 7. 비용 예측

OmokGosu 트래픽 수준 (코워커 ~30명, 게임 1-2개 동시):
- shared-cpu-1x / 512MB / 1GB volume / 1 always-on machine = **월 $3-6** 정도
- 사용 안 할 때 `flyctl scale count 0`로 머신 멈추면 청구 안 됨 (단 콜드 스타트 발생)
- 정확한 가격은 https://fly.io/docs/about/pricing/

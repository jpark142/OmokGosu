# OmokGosu

> **한국식 렌주룰 오목** 멀티플레이어 + AI 대국 플랫폼
> C++20 룰 엔진 · Python FastAPI 서버 · React 웹 클라이언트 · Electron Windows 앱

🌐 **지금 바로 플레이**: **https://omokgosu.fly.dev**

---

## 무엇인가요

15×15 보드, 흑에게 3-3 / 4-4 / 장목(6목 이상) 금수가 강제되는 정식 **렌주(連珠)룰** 오목 게임입니다.
회원가입만 하면 친구와 방을 만들어 대국하거나, 휴리스틱 AI(easy/medium/hard)와 한 판 둘 수 있어요.

### 주요 기능

| | |
|---|---|
| 🏠 **로비 + 방** | 방 생성/입장/Ready/시작, 방장 강퇴, 라이브 채팅(시스템 메시지 + 한글 IME 대응) |
| 👥 **멀티플레이** | JWT 인증, 단일 세션 로그인(다른 곳 로그인 시 즉시 끊김), 같은 계정 다중 탭 차단 |
| 🤖 **AI 대국** | Random / Minimax(α-β + TT) / Heuristic(VCF mate-search + 패턴 가중치) — easy/medium/hard 난이도 |
| ⏱ **공식 시계** | 5분 본시간 + 10초 byo-yomi × 3, 250 ms tick |
| 📜 **기보 / 전적** | 모든 매치는 SQLite에 영구 보존, 슬라이더로 수순 재생, 사용자 프로필에 최근 50판 표시 |
| 🏆 **리더보드** | 총 승수 기준 랭킹, 승무패 + 승률 표시 |
| 👁 **라이브 관전** | 방에 들어가면 두 명 차고 있으면 자동 관전자로 입장, 채팅 가능 |
| 🌐 **데스크탑 앱** | Windows용 NSIS installer (~75 MB) — 본질은 웹 앱을 띄우는 Chromium 셸 |
| 🔄 **버전 게이트** | 클라이언트가 서버 최소 버전보다 낮으면 426 / soft banner / hard modal |

## 빠르게 한 판 두기

1. **https://omokgosu.fly.dev** 접속
2. 닉네임 + 비밀번호 4자 이상으로 회원가입 (10초)
3. 로비에서 "방 만들기" → 친구가 같은 방에 입장, 또는 "AI와 두기"

(Windows 데스크탑 앱이 필요하면 [Releases](https://github.com/jpark142/OmokGosu/releases)에서 `.exe` installer 다운로드 — 기능은 웹과 동일)

## 아키텍처 한눈에

```
┌──────────────┐    HTTPS/WSS    ┌────────────────────────────┐
│  React SPA   │ ──────────────► │  FastAPI (uvicorn)         │
│  Vite + TS   │ ◄────────────── │  + WebSocket game/room/lobby│
│  Tailwind    │                 │  + JWT auth, SQLite        │
└──────────────┘                 └──────────────┬─────────────┘
       ▲                                        │ pybind11
       │ Electron shell                         ▼
       │ (Chromium)                  ┌────────────────────────┐
       │                             │  omok_core (C++20)      │
       │                             │  Board · Rules · AI     │
       │                             │  Minimax · Heuristic    │
       │                             └────────────────────────┘
```

모두 Fly.io 도쿄 리전에 단일 컨테이너로 배포되어 있어요.

### 디렉토리

```
cpp/        C++20 omok_core 엔진 (pybind11로 Python 노출)
server/     FastAPI 앱 (REST + WS), JWT, SQLite, AI 어댑터
web/        React + Vite + TS + Tailwind + shadcn/ui 프론트
electron/   Thin Chromium shell + assets + NSIS 빌드 설정
docs/       PLAN / ROADMAP / ARCHITECTURE / RULES / AI / DEPLOY_*
scripts/    bootstrap / dev / test / sync_version / build_electron
fly.toml    Fly.io 배포 설정 (nrt 리전, 1GB 볼륨)
Dockerfile  멀티스테이지 (C++ → web → slim runtime)
```

## 진행 단계

| Phase | 상태 | 내용 |
|---|---|---|
| 1 — 엔진 + UI | ✅ | C++ 룰 엔진(흑 금수 포함) + WS 기반 단일 대국 |
| 2 — Minimax | ✅ | α-β + 전치표 + 패턴 평가 |
| 3 — 멀티유저 | ✅ | JWT 인증, 로비/방/채팅, 전적, 리더보드, 관전, 무승부 |
| H — Heuristic | ✅ | VCF mate-search + 패턴 가중치 |
| R — Replay | ✅ | 기보 슬라이더 + 화살표 키 |
| L — Leaderboard | ✅ | 총 승수 랭킹 |
| D-4 — Fly.io 배포 | ✅ | https://omokgosu.fly.dev |
| D-5 — Electron | ✅ | Windows `.exe` installer |
| **4 — AlphaZero** | 🔜 | ResNet 10×128 + MCTS PUCT + 자가대국 워커 |

자세한 마일스톤은 [`docs/ROADMAP.md`](docs/ROADMAP.md), 설계는 [`docs/ARCHITECTURE.md`](docs/ARCHITECTURE.md), 룰 정의는 [`docs/RULES.md`](docs/RULES.md).

## 기술 스택

- **엔진**: C++20 / MSVC 2022 / CMake / pybind11 / scikit-build-core
- **서버**: Python 3.11 · FastAPI · uvicorn · SQLModel · bcrypt · PyJWT · pytest
- **클라이언트**: React 18 · Vite · TypeScript · Tailwind CSS · shadcn/ui · React Router
- **데스크탑**: Electron 31 · electron-builder (NSIS)
- **배포**: Fly.io · Docker (멀티스테이지) · SQLite + 영속 볼륨
- **AI(예정)**: PyTorch · ResNet · MCTS (PUCT)

## 로컬에서 띄우기 (개발자용)

### 필요한 것
- Windows 10/11
- Visual Studio 2022 Build Tools (C++ 워크로드 + CMake)
- Python 3.11+ (uv 또는 venv + pip)
- Node 20+
- (선택) CUDA 12.x GPU — Phase 4 학습용

### 부트스트랩 → 실행

```powershell
cd D:\OmokGosu
.\scripts\bootstrap.ps1   # 최초 1회: venv, C++ 빌드, npm install
.\scripts\dev.ps1         # FastAPI :8000 + Vite :5173 동시 실행
# 브라우저: http://localhost:5173
```

### 테스트

```powershell
.\scripts\test.ps1        # pytest + tsc --noEmit + C++ doctest
```

### Electron 빌드 (선택)

```powershell
.\scripts\build_electron.ps1
# → D:\OmokGosu\dist-electron\OmokGosu-Setup-1.0.0.exe
```

## 배포

`flyctl deploy` 한 번이면 끝. 자세한 가이드는 [`docs/DEPLOY_CLOUD.md`](docs/DEPLOY_CLOUD.md).

```powershell
flyctl status      # 머신 상태
flyctl logs        # 실시간 로그
flyctl ssh console # 컨테이너 셸
```

## 만든 사람

[**jypark**](https://github.com/jpark142) — 2026

## 라이선스

미정 (개인 학습/포트폴리오 프로젝트)

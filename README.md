# OmokGosu

**렌주룰 오목 (Korean Renju Gomoku) AI** — 15×15 보드, 흑 금수 (3-3 / 4-4 / 장목), 5분 + 10초 byo-yomi × 3.

C++ 코어 엔진 + Python FastAPI 서버 + React 웹 UI. 최종 목표는 AlphaZero 스타일 강화학습 AI.

## 구조

```
cpp/        C++20 코어 엔진 (Board, Rules, MCTS) + pybind11 모듈
server/     Python FastAPI 서버 (REST + WebSocket)
training/   Phase 4 자가대국 / PyTorch 학습 파이프라인
web/        React + Vite + TS 프론트엔드
docs/       프로젝트 문서 (PLAN / ARCHITECTURE / RULES / AI / ROADMAP)
scripts/    개발 환경 부트스트랩 & 실행 스크립트
```

자세한 내용은 [`docs/PLAN.md`](docs/PLAN.md)부터 시작하세요.

## 빠른 시작

```powershell
# Windows / PowerShell, VS 2022 Build Tools 필요
cd D:\OmokGosu
.\scripts\bootstrap.ps1     # 최초 1회: venv 생성, C++ 빌드, pnpm install
.\scripts\dev.ps1            # uvicorn:8000 + vite:5173 병렬 실행
# 브라우저: http://localhost:5173
```

## 필수 환경

- Windows 10/11
- **Visual Studio 2022 Build Tools** (C++ 워크로드, CMake)
- **Python 3.11+** + `uv` (또는 venv + pip)
- **Node 20+** + `pnpm`
- (Phase 4) CUDA 12.x 호환 GPU + PyTorch CUDA 빌드

## 단계별 진행

| Phase | 상태 | 내용 |
|---|---|---|
| 1 | 진행중 | 룰 엔진 + 웹 UI, 사람 vs 사람 |
| 2 | 미시작 | Minimax + Alpha-Beta AI |
| 3 | 미시작 | 패턴 휴리스틱 + VCF/VCT |
| 4 | 미시작 | AlphaZero 스타일 ResNet + MCTS |

자세한 마일스톤은 [`docs/ROADMAP.md`](docs/ROADMAP.md).

## 라이선스

(미정)

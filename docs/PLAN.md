# OmokGosu — 프로젝트 플랜

> 본 문서는 프로젝트 전체 개요와 단계별 로드맵 요약입니다.
> 상세는 sibling 문서를 참고: [ARCHITECTURE.md](./ARCHITECTURE.md) · [RULES.md](./RULES.md) · [AI.md](./AI.md) · [ROADMAP.md](./ROADMAP.md)

## 무엇을 만드는가

15×15 보드의 **렌주룰 오목** 게임 + **AlphaZero 스타일 AI**.
브라우저에서 사람 vs 사람 / 사람 vs AI 대국이 가능한 단일 머신 앱으로 시작하여, 동일한 서버 인터페이스를 후일 원격 호스팅으로 확장한다.

## 핵심 결정

| 항목 | 결정 |
|---|---|
| 보드 | 15×15 |
| 룰 | 한국식 렌주 — 흑에게만 3-3 / 4-4 / 장목 금수, 흑은 정확히 5목 승리, 백은 5목 이상 승리 |
| 색 배정 | 매 게임 무작위, 흑 선착 |
| 시간제 | 주 시간 5분 + byo-yomi 10초 × 3회 (일본식: 시간 내 두면 period 리프레시) |
| 코어 언어 | C++20 (MSVC, VS 2022) |
| 파이썬 바인딩 | pybind11 + scikit-build-core |
| 서버 | Python FastAPI + uvicorn + WebSocket |
| 프론트 | React 18 + TypeScript + Vite + Tailwind + shadcn/ui + sonner |
| 보드 렌더 | HTML5 Canvas (DPR 대응, 단일 React 컴포넌트) |
| 신경망 | PyTorch (학습/추론 Python, C++ MCTS는 콜백 인터페이스로 호출) |

## 단계별 로드맵 (요약)

| Phase | 목표 | 산출물 |
|---|---|---|
| **1** | 룰 엔진 + 웹 UI, AI 없음 | 사람 vs 사람 풀 렌주 + 시계, 두 브라우저 탭으로 즉시 대국 |
| **2** | 클래식 AI | Minimax + alpha-beta + TT, 사람 vs AI 모드 |
| **3** | 휴리스틱 강화 | 패턴 평가 + VCF/VCT 위협 공간 탐색 |
| **4** | AlphaZero 신경망 | ResNet(10×128) + MCTS-PUCT + self-play 학습 파이프라인 |

자세한 마일스톤과 수용 기준은 [ROADMAP.md](./ROADMAP.md) 참조.

## 디렉터리 한눈에 보기

```
D:/OmokGosu/
├── cpp/         # C++ 코어 엔진 + pybind11 모듈
├── server/      # Python FastAPI 서버
├── training/    # Phase 4 self-play / training (PyTorch)
├── models/      # NN 체크포인트
├── web/         # React + Vite + TS 프론트
├── docs/        # 본 문서들
└── scripts/     # 부트스트랩 / 개발 실행 스크립트
```

상세 모듈 구조는 [ARCHITECTURE.md](./ARCHITECTURE.md) 참조.

## 트레이드오프

1. **Phase 4 Python측 NN 추론**: C++ MCTS leaf마다 Python 콜백 → 배칭에도 오버헤드. byo-yomi 10초 내 ~500-1000 sim/move 정도가 현실적. 더 빠르게 가려면 후일 libtorch로 C++ 추론 전환 — `cpp/include/omok/nn_eval_iface.hpp`가 그 seam.
2. **무작위 색 배정 + 흑만 금수**: 렌주는 본래 흑이 불리한 비대칭 룰. Home 화면에 안내 문구를 둔다.
3. **단일 네트워크 + 흑 금수 mask 채널**: 색마다 별도 네트워크 대신 단일 + mask 평면. Phase 4 평가에서 흑이 약하면 분리 검토.

# OmokGosu — 아키텍처

## 데이터 흐름

```
┌─────────────┐     WebSocket / REST     ┌──────────────────┐
│  React/Vite │ ◀──────────────────────▶ │  FastAPI server  │
│  (web/)     │                          │  (server/)       │
└─────────────┘                          └────────┬─────────┘
                                                  │ pybind11
                                         ┌────────▼─────────┐
                                         │   omok_core      │
                                         │   (cpp/)         │
                                         │  Board, Rules,   │
                                         │  Patterns,       │
                                         │  Minimax, MCTS   │
                                         └────────┬─────────┘
                                                  │ (Phase 4)
                                         ┌────────▼─────────┐
                                         │  PyTorch model   │
                                         │  (PyTorch GPU)   │
                                         └──────────────────┘
```

- **서버가 권위(authoritative)**: 게임 상태, 시계, 금수 판정, 승부 결정 모두 서버. 프론트는 표시 + 입력만.
- **C++ 코어는 순수**: I/O 없음, 결정론적. Python에서 호출되어 결과를 반환.
- **신경망은 Python**: PyTorch eager 또는 TorchScript. C++ MCTS는 `nn_eval_iface.hpp`의 콜백을 통해 leaf 평가 요청.

## 디렉터리 레이아웃

```
D:/OmokGosu/
├── CMakeLists.txt              # top-level
├── pyproject.toml              # scikit-build-core 드라이버
├── README.md
├── .gitignore, .clang-format, .editorconfig
│
├── cpp/                        # C++ 코어
│   ├── CMakeLists.txt
│   ├── include/omok/
│   │   ├── types.hpp           # Color, Move, BOARD_SIZE=15
│   │   ├── board.hpp           # 비트보드 + 수 스택
│   │   ├── zobrist.hpp
│   │   ├── rules.hpp           # 금수/승리 판정
│   │   ├── pattern.hpp         # 패턴 테이블 + 평가
│   │   ├── move_generator.hpp
│   │   ├── minimax.hpp         # Phase 2
│   │   ├── vcf_vct.hpp         # Phase 3
│   │   ├── mcts.hpp            # Phase 4
│   │   └── nn_eval_iface.hpp   # NN 평가 콜백 인터페이스
│   ├── src/                    # 각 헤더 대응 .cpp
│   ├── bindings/pybind_module.cpp
│   └── tests/                  # doctest + fixtures/forbidden_positions.json
│
├── server/                     # Python FastAPI
│   ├── pyproject.toml
│   ├── omok_server/
│   │   ├── main.py             # FastAPI app
│   │   ├── schemas.py          # pydantic 모델 (WS/HTTP 페이로드)
│   │   ├── api/
│   │   │   ├── games.py        # REST endpoints
│   │   │   └── ws.py           # WebSocket handler
│   │   ├── game/
│   │   │   ├── engine.py       # omok_core 래퍼
│   │   │   ├── session.py      # GameSession 상태머신
│   │   │   ├── clock.py        # 5분 + 3×10초 시계
│   │   │   └── manager.py      # in-memory 게임 레지스트리
│   │   ├── ai/
│   │   │   ├── base.py         # AIPlayer 프로토콜
│   │   │   ├── random_ai.py    # Phase 1 smoke
│   │   │   ├── minimax_ai.py   # Phase 2
│   │   │   ├── heuristic_ai.py # Phase 3
│   │   │   └── alphazero_ai.py # Phase 4
│   │   └── nn/
│   │       ├── model.py        # ResNet (PyTorch)
│   │       ├── encoder.py      # board → tensor planes
│   │       ├── inference.py    # batched eval server
│   │       └── checkpoints.py
│   └── tests/
│
├── training/                   # Phase 4
│   ├── selfplay.py
│   ├── train.py
│   ├── arena.py
│   ├── replay_buffer.py
│   ├── config/
│   │   ├── selfplay.yaml
│   │   └── train.yaml
│   └── scripts/
│
├── models/                     # 체크포인트 (gitignore)
│
├── web/                        # React + Vite + TS
│   ├── package.json
│   ├── vite.config.ts
│   ├── tailwind.config.ts
│   ├── tsconfig.json
│   ├── index.html
│   └── src/
│       ├── main.tsx, App.tsx
│       ├── routes/{Home,Game}.tsx
│       ├── components/
│       │   ├── Board.tsx          # canvas 보드
│       │   ├── Clock.tsx
│       │   ├── PlayerCard.tsx
│       │   ├── MoveList.tsx
│       │   ├── GameOverDialog.tsx
│       │   └── NewGameDialog.tsx
│       ├── components/ui/         # shadcn 생성
│       ├── hooks/{useGameSocket,useGameState}.ts
│       ├── lib/{api,ws,boardMath}.ts
│       └── types/protocol.ts      # 서버 schemas.py 미러
│
├── docs/                       # 이 폴더
└── scripts/                    # bootstrap.ps1, dev.ps1, build_core.ps1
```

## C++ 모듈 책임

| 헤더 | 클래스 | 책임 | 사용 Phase |
|---|---|---|---|
| `types.hpp` | `Color`, `Move`, `BOARD_SIZE` | 공통 프리미티브 | 전 단계 |
| `board.hpp` | `Board` | 비트보드 페어 + 수 스택, `play()`, `undo()`, `at()`, `hash()` | 전 단계 |
| `zobrist.hpp` | `Zobrist` | 64-bit zobrist 키, 점진 업데이트 | Phase 2~4 |
| `rules.hpp` | `RuleChecker` | 렌주 금수 판정, 5목 승리 판정, 장목 판정 | 전 단계 |
| `pattern.hpp` | `PatternTable`, `PatternEvaluator` | 9칸 1-D 윈도우 패턴 룩업, 점수 평가 | Phase 2~4 (RuleChecker도 패턴 정의 재사용) |
| `move_generator.hpp` | `MoveGenerator` | 기존 돌 인접 후보 생성, 합법수 필터링 | Phase 2~4 |
| `minimax.hpp` | `Minimax` | alpha-beta + 반복심화 + TT | Phase 2 |
| `vcf_vct.hpp` | `ThreatSearch` | VCF/VCT 위협 공간 DFS | Phase 3 |
| `mcts.hpp` | `MCTSNode`, `MCTS` | PUCT 트리 + virtual loss + 배칭 leaf | Phase 4 |
| `nn_eval_iface.hpp` | `EvalFn = std::function<...>` | NN 평가 콜백 추상 | Phase 4 (libtorch 교체 seam) |

## 빌드

- **CMake ≥ 3.26**, **C++20** (concepts, `<bit>`, `std::span`).
- **MSVC** (VS 2022 Build Tools) on Windows.
- `pyproject.toml`에 `scikit-build-core` 드라이버 → `pip install -e .`이 CMake로 `omok_core*.pyd`를 빌드해 venv의 site-packages에 설치.
- C++ 테스트는 `cpp/tests/`에서 별도 실행 파일로 빌드, **doctest** 사용.
- PyTorch C++(libtorch)는 지금은 링크하지 않음. 추후 `-DOMOK_WITH_LIBTORCH=ON` 가드로 옵션 추가 가능 — `nn_eval_iface.hpp`가 seam.

## API 표면 요약

REST:
- `POST /api/games` body `{mode, ai_level?, player_name?}` → `{game_id, your_color, ws_url}`
- `GET /api/games/{id}` → 전체 GameState (재접속)
- `POST /api/games/{id}/resign`
- `POST /api/games/{id}/rematch`
- `GET /api/health`

WebSocket `/ws/games/{id}`:
- C→S: `move{r,c}`, `resign`, `ping`
- S→C: `state`(스냅샷), `timer_tick`, `move_applied`, `forbidden_move_rejected`, `game_over`, `error`

상세 페이로드는 `server/omok_server/schemas.py` (실제 정의) 및 `web/src/types/protocol.ts` (TS 미러) 참조.

## 동시성/스레딩

- FastAPI는 단일 프로세스 asyncio. 게임당 1개 asyncio 태스크가 250ms 주기로 `timer_tick` 푸시 및 시간 초과 감시.
- C++ 호출은 GIL 해제 가능한 긴 호출에 대해 pybind11 `py::gil_scoped_release` 적용 (Phase 2부터).
- 게임 상태는 in-memory `Manager` 단일 인스턴스. 동시성 안전을 위해 게임별 `asyncio.Lock` 사용.

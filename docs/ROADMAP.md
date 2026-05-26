# OmokGosu — 로드맵 & 수용 기준

## Phase 1 — 룰 엔진 + 웹 UI (AI 없음)

### 산출물 체크리스트
- [ ] 톱레벨 `CMakeLists.txt`, `pyproject.toml`, `README.md`, `.gitignore`
- [ ] C++ 코어:
  - [ ] `cpp/include/omok/types.hpp` — Color, Move, BOARD_SIZE
  - [ ] `cpp/include/omok/board.hpp` + `src/board.cpp`
  - [ ] `cpp/include/omok/zobrist.hpp` + `src/zobrist.cpp`
  - [ ] `cpp/include/omok/pattern.hpp` + `src/pattern.cpp` (패턴 룩업 테이블)
  - [ ] `cpp/include/omok/rules.hpp` + `src/rules.cpp` (렌주 금수 + 승리)
  - [ ] `cpp/bindings/pybind_module.cpp` (Board, RuleChecker, enums 노출)
- [ ] C++ 테스트 (doctest):
  - [ ] `cpp/tests/test_board.cpp`
  - [ ] `cpp/tests/test_pattern.cpp`
  - [ ] `cpp/tests/test_rules.cpp` (golden-file 기반)
  - [ ] `cpp/tests/fixtures/forbidden_positions.json` (**100+ 케이스**)
- [ ] Python 서버:
  - [ ] `server/pyproject.toml`
  - [ ] `server/omok_server/main.py` (FastAPI app)
  - [ ] `server/omok_server/schemas.py` (pydantic)
  - [ ] `server/omok_server/game/{engine,session,clock,manager}.py`
  - [ ] `server/omok_server/api/{games,ws}.py`
  - [ ] `server/omok_server/ai/{base,random_ai}.py` (인터페이스 + 더미)
- [ ] Python 테스트 (pytest):
  - [ ] `server/tests/test_clock.py`
  - [ ] `server/tests/test_engine.py`
  - [ ] `server/tests/test_session.py`
  - [ ] `server/tests/test_rules_parity.py` (C++ 동일 fixture 검증)
  - [ ] `server/tests/test_api.py` (FastAPI TestClient + WS)
- [ ] React 프론트:
  - [ ] `web/package.json`, vite/tailwind/tsconfig 설정
  - [ ] `web/src/main.tsx`, `App.tsx`
  - [ ] `web/src/routes/{Home,Game}.tsx`
  - [ ] `web/src/components/{Board,Clock,PlayerCard,MoveList,GameOverDialog,NewGameDialog}.tsx`
  - [ ] `web/src/components/ui/` (shadcn 생성)
  - [ ] `web/src/hooks/{useGameSocket,useGameState}.ts`
  - [ ] `web/src/lib/{api,ws,boardMath}.ts`
  - [ ] `web/src/types/protocol.ts`
- [ ] Scripts:
  - [ ] `scripts/bootstrap.ps1`
  - [ ] `scripts/dev.ps1`
  - [ ] `scripts/build_core.ps1`

### 수용 기준 (End-to-End)

`scripts/bootstrap.ps1` 한 번, `scripts/dev.ps1` 한 번이면 게임 가능 상태.

1. **금수 거부 동작**:
   - 흑이 3-3 자리에 둠 → 토스트 "금수: 삼삼", 보드 상태 변화 없음.
   - 흑이 4-4 자리에 둠 → 토스트 "금수: 사사".
   - 흑이 장목 자리에 둠 → 토스트 "금수: 장목".
   - 흑이 그 외 합법 수 → 정상 착수.
2. **백은 제약 없음**: 백은 어떤 빈 칸에든 둘 수 있고, 6목 두면 백 승.
3. **승리 처리**:
   - 흑 정확히 5목 → 게임 종료 다이얼로그 "흑 승 / 5목".
   - 백 5목 또는 그 이상 → 게임 종료 다이얼로그 "백 승".
4. **시간제**:
   - 시계가 250ms마다 갱신, 양쪽 시계 모두 정확하게 차감.
   - 주 시간 0초 도달 → 자동으로 byo-yomi 진입 (`[10] [10] [10]` 표시).
   - byo-yomi 10초 안에 두면 period 그대로, 초과하면 1개 소비.
   - 3개 모두 소진 + 시간 초과 → 게임 종료 "시간패".
5. **재접속**: 게임 중 새로고침 → 같은 game_id로 자동 재연결, 보드/시계 즉시 복원.
6. **금수 미리보기**: 흑 차례일 때 보드 위에 금수 자리 표시 (작은 빨간 ✕).
7. **두 탭 멀티플레이**: 같은 게임에 두 탭 접속 → 한 쪽에서 둔 수가 즉시 다른 쪽에 반영.

### 검증 절차
```powershell
cd D:\OmokGosu
.\scripts\bootstrap.ps1       # 최초 1회
.\scripts\dev.ps1             # uvicorn:8000 + vite:5173 병렬 실행
# 별도 터미널:
pytest server\tests           # 전체 green
ctest --test-dir build        # C++ 전체 green
# 브라우저:
# http://localhost:5173 두 탭으로 같은 게임 접속 후 위 수용 기준 1~7 수동 확인
```

---

## Phase 2 — Minimax + Alpha-Beta (구현 완료, 게임 검증 단계)

### 산출물
- [x] `cpp/include/omok/eval.hpp` + `src/eval.cpp` — 정적 평가
- [x] `cpp/include/omok/movegen.hpp` + `src/movegen.cpp` — 후보 생성/정렬
- [x] `cpp/include/omok/search.hpp` + `src/search.cpp` — Negamax + α-β + TT + ID + killer/history
- [x] `cpp/bindings/pybind_module.cpp` 업데이트 (Searcher, SearchLimits, SearchResult, evaluate)
- [x] `cpp/tests/test_search.cpp` (정적 평가, mate-in-1, 강제 차단, 시간 예산, 빈 보드)
- [x] `server/omok_server/ai/minimax_ai.py` — `MinimaxAI` 파이썬 래퍼 (Easy/Medium/Hard 난이도)
- [x] `server/omok_server/game/session.py` — get_ai_for에서 "minimax[:diff]" 디스패치
- [x] `server/omok_server/schemas.py` — `ai_difficulty` 필드 추가
- [x] `web/src/routes/Home.tsx` — AI 종류 + 난이도 선택 UI

### 수용 기준
- [x] C++ 테스트 33개 모두 green (`omok_tests.exe`).
- [x] Python `omok_core.Searcher`로 빈 보드 탐색 → depth 4, center 반환, < 10ms.
- [x] `MinimaxAI` 인스턴스 생성 + choose_move 정상.
- [ ] **수동 게임 검증**: 사람 vs Minimax(Medium) 한 판 — AI가 합리적인 위치에 두고, mate 받으면 막고, 자기 mate 잡으면 둠.
- [ ] AI vs RandomAI 100판 (자동) → 95%+ 승.
- [ ] Mate-in-3 포지션 (외부 fixture) 정답률 측정.

---

## Phase 3 — 휴리스틱 강화 + VCF/VCT

### 산출물
- [ ] `cpp/include/omok/vcf_vct.hpp` + `src/vcf_vct.cpp`
- [ ] `cpp/src/pattern.cpp` 평가 함수 정교화
- [ ] `cpp/tests/test_vcf.cpp` (VCF 테스트 포지션)
- [ ] `server/omok_server/ai/heuristic_ai.py` (HeuristicAI)
- [ ] 난이도에 "Expert" 추가

### 수용 기준
- HeuristicAI(Expert) vs MinimaxAI(Hard) 50판 → HeuristicAI 60% 이상 승.
- 알려진 VCF 포지션 10개에서 모두 강제승 발견.
- 사람 강아마추어가 졌다고 인정할 수준.

---

## Phase 4 — AlphaZero

### 산출물
- [ ] `cpp/include/omok/mcts.hpp` + `src/mcts.cpp` (PUCT + virtual loss + leaf 배칭)
- [ ] `cpp/include/omok/nn_eval_iface.hpp`
- [ ] `cpp/bindings/pybind_module.cpp` 업데이트 (MCTS 노출, EvalFn 콜백)
- [ ] `server/omok_server/nn/model.py` (ResNet 10×128)
- [ ] `server/omok_server/nn/encoder.py` (board → 14×15×15 tensor)
- [ ] `server/omok_server/nn/inference.py` (배칭 추론 서버)
- [ ] `server/omok_server/nn/checkpoints.py`
- [ ] `server/omok_server/ai/alphazero_ai.py` (AlphaZeroAI)
- [ ] `training/selfplay.py`, `train.py`, `arena.py`, `replay_buffer.py`
- [ ] `training/config/{selfplay.yaml,train.yaml}`
- [ ] `training/scripts/{run_selfplay.ps1,run_train.ps1}`
- [ ] `models/champion/README.md`, `models/candidates/README.md`

### 수용 기준
- Self-play 워커 16개 + GPU 추론 서버 1개 안정 동작, GPU 사용률 80%+.
- 학습 50K 게임 후 AlphaZeroAI vs HeuristicAI(Expert) arena 40판 → AlphaZeroAI 60%+.
- 게임 중 byo-yomi 10초 안에 ~500-1000 sim/move 수행 가능.
- 챔피언 교체 자동화 (≥55% 승률 시 promote).

---

## Phase 5+ (Optional)

- 서버 도커화 + 원격 배포 (Render / Fly.io / 자체 VM).
- 멀티유저 매칭 / 룸 시스템.
- 기보 저장 + 리뷰 기능.
- libtorch C++ 추론 전환 (`OMOK_WITH_LIBTORCH=ON`).
- 모바일 UI (responsive Canvas) 또는 React Native 포팅.

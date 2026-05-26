# OmokGosu — AI 설계

> Phase 2~4의 AI 알고리즘과 신경망 설계. Phase 1에서는 AI 없음 (사람 vs 사람).

## Phase 2 — Minimax + Alpha-Beta (구현 완료)

### 코어 파일
- `cpp/include/omok/eval.hpp` + `src/eval.cpp` — 전판 정적 평가
- `cpp/include/omok/movegen.hpp` + `src/movegen.cpp` — 후보 생성 + 정렬
- `cpp/include/omok/search.hpp` + `src/search.cpp` — Negamax + α-β + TT + ID
- `cpp/tests/test_search.cpp` — 정적 평가 / mate-in-1 / 강제 차단 / 시간 예산 / 빈 보드 대응
- `server/omok_server/ai/minimax_ai.py` — `omok_core.Searcher` 파이썬 래퍼

### 알고리즘 요지
1. **Iterative deepening** depth 1 → 2 → ... → `max_depth`. 매 깊이 끝나면 best move를 갱신, 시간 초과 시 직전 완료 depth의 best 사용.
2. **Negamax + Alpha-beta**: 한쪽 점수만 다루고 부호 반전으로 양측 동시 처리. β-cut 발생 시 그 수를 killer로 기록 + history 가산.
3. **Transposition Table**: zobrist 키 → `{score, depth, flag, best_move}`. flag는 Exact / LowerBound (β-cut) / UpperBound (α 갱신 실패). Mate score는 `score_to_tt/score_from_tt`로 ply 정규화.
4. **Move ordering**: candidate score (자신 + 0.9 × 상대 위협) → TT best → killer → history. Root 1-depth 첫 패스는 candidate score만 사용.
5. **시간 예산**: `std::chrono::steady_clock` 데드라인. nodes & 0x3FF마다 체크 → 초과 시 abort 플래그 + 즉시 반환.
6. **종료 단축**: |score| ≥ WIN_THRESHOLD면 더 깊이 안 들어감 (이미 강제승/패).
7. **흑 금수**: movegen에서 사전 필터링. 금수 자리는 후보에서 빠지므로 흑 AI는 절대 금수에 두지 않음.

### 평가 함수 (`omok::eval::evaluate`)
- 4 방향 × 모든 라인 (행 15 + 열 15 + 대각 29 + 역대각 29) 스캔.
- 각 라인에서 한쪽 색의 연속 run을 (길이, 양끝 개방) 키로 분류:
  | 형태 | 가중치 |
  |---|---|
  | Five (정확히 5) | 1,000,000 |
  | Open four (`_XXXX_`) | 50,000 |
  | Four (한쪽 차단) | 10,000 |
  | Open three (`_XXX_`) | 5,000 |
  | Closed three | 500 |
  | Open two | 100 |
  | Closed two | 10 |
  | 흑 overline (6+) | −100,000 (금수 페널티) |
  | 백 overline (6+) | +1,000,000 (5와 동일 승) |
- 최종 점수 = `score_for(to_move) - score_for(opp)`, `[-WIN, +WIN]`로 클립.

### 노출 (pybind11)
```python
import omok_core
s = omok_core.Searcher(tt_size_mb=32)
lim = omok_core.SearchLimits()
lim.max_depth = 6; lim.budget_ms = 1200; lim.root_width = 16; lim.child_width = 10
r = s.search(board, omok_core.Color.Black, rules, lim)
# r.best_r, r.best_c, r.score, r.depth, r.nodes, r.tt_hits, r.elapsed_ms, r.aborted
```
GIL은 `search()` 진입 시 해제 → 서버 이벤트 루프 블로킹 없음.

### 난이도 매핑 (서버 ↔ UI)
| 난이도 | max_depth | 기본 예산(ms) | root_width | child_width |
|---|---|---|---|---|
| easy   | 4 | 400  | 12 | 8  |
| medium | 6 | 1200 | 16 | 10 |
| hard   | 8 | 2500 | 20 | 12 |

UI는 `ai_level=minimax`와 `ai_difficulty=easy|medium|hard`를 보냄 → 서버는 `players[color].name = "minimax:hard"` 형태로 저장 → `session.get_ai_for`가 difficulty suffix를 파싱해 `MinimaxAI(difficulty=...)` 인스턴스 생성.

### 알려진 한계 (Phase 3에서 다룰 부분)
- 정적 평가가 single-line 패턴만 봄 → broken three/four (예: `X_XX`, `XX_XX`) 미검출.
- VCF(연속 4) / VCT(4+열린3) 강제 수순 미실장 → 깊이 안 닿는 long-range 강제승 놓침.
- 흑 금수 평가 가중치는 라인 단위 overline만 페널티, 3-3/4-4 자체 페널티는 movegen 필터로만 다룸.

## Phase 3 — 휴리스틱 강화 + VCF/VCT

### 패턴 평가 정밀화
- 두 색 동시 평가 (자기 + 상대 위협), 자기 점수 - 상대 점수 × α.
- 페턴 충돌 보정 (한 빈 칸이 두 패턴에 동시 기여하는 경우 중복 카운트 방지).

### VCF (Victory by Continuous Fours)
- 자기가 4를 연속 두면 상대는 반드시 막아야 함 → 강제 수순.
- DFS로 4-만드는 수만 확장. 5목으로 끝나면 VCF 성공.
- 깊이 제한 (16수 정도) + 트랜스포지션 테이블.

### VCT (Victory by Continuous Threats)
- 4 또는 열린-3을 만드는 수를 모두 시도. VCF의 일반화.
- 흑은 금수가 큰 가지치기 요인 → 평균 분기 적음.

### 통합
`HeuristicAI`는 매 수마다:
1. 즉승 수 있나? → 둠.
2. 상대 즉승 막을 수 있나? → 막음.
3. VCF 시도 → 성공 시 둠.
4. VCT 시도 (시간 여유 시) → 성공 시 둠.
5. 그 외엔 Minimax 결과 사용.

## Phase 4 — AlphaZero 스타일

### 네트워크 입력 (14 평면, 15×15)

| # | 평면 | 설명 |
|---|---|---|
| 1 | own_stones | 현재 차례 색의 돌 |
| 2 | opp_stones | 상대 색의 돌 |
| 3 | side_to_move | 흑 차례면 1로 가득, 백 차례면 0 |
| 4-7 | history_own_last4 | 자기 마지막 4수 위치 |
| 8-11 | history_opp_last4 | 상대 마지막 4수 위치 |
| 12 | legal_mask | 합법수 마스크 |
| 13 | forbidden_mask_black | 흑 차례일 때 금수 자리 (백 차례는 0) |
| 14 | move_number | 수 번호 / 225 (정규화) 가득 |

### 네트워크 구조

- **ResNet, 10 블록 × 128 필터**.
- 입력: 14×15×15
- Stem: Conv3×3 (128) → BN → ReLU
- ResBlock × 10: [Conv3×3(128) → BN → ReLU → Conv3×3(128) → BN → +skip → ReLU]
- **Policy head**: Conv1×1(2) → BN → ReLU → Flatten → FC(225) → softmax (illegal/forbidden은 -∞ mask 후 renormalize)
- **Value head**: Conv1×1(1) → BN → ReLU → Flatten → FC(64) → ReLU → FC(1) → tanh

총 파라미터 ~1.1M. RTX 4090 학습 batch 512에 ~3 GB VRAM (옵티마이저 상태 포함).

### MCTS (PUCT)

선택:
```
U(s,a) = c_puct × P(s,a) × √(Σ_b N(s,b)) / (1 + N(s,a))
a* = argmax_a [Q(s,a) + U(s,a)]
```
- `c_puct = 1.5` 초기값, arena에서 튜닝.
- Root에 Dirichlet noise: α=0.15, ε=0.25 (탐색 다양성).
- **Virtual loss = 3**: 동시에 같은 leaf 선택 방지 (배칭 시).
- Leaf 배칭: 16~32개 leaf를 모은 뒤 한 번에 NN 추론. 2ms 타임아웃 후 부족하면 패딩.
- Backup: 부모 노드들에 가치 전파 + virtual loss 제거.

### 자가대국 파이프라인

```
┌──────────────┐   batched eval requests   ┌────────────────┐
│ Selfplay     │ ───────────────────────▶  │ GPU Inference  │
│ Worker × 16  │ ◀───────────────────────  │ Server (1 GPU) │
└──────┬───────┘   batched eval results    └────────────────┘
       │ (state, π, z) tuples
       ▼
┌──────────────┐                           ┌────────────────┐
│ Replay       │ ──── sample mini-batch ─▶ │ Training       │
│ Buffer 500K  │       (8x sym augment)    │ Loop (PyTorch) │
└──────────────┘                           └────────┬───────┘
                                                    │ checkpoint
                                                    ▼
                                           ┌────────────────┐
                                           │ Arena Eval     │
                                           │ 40 games vs    │
                                           │ champion       │
                                           └────────┬───────┘
                                                    │ ≥55%?
                                                    ▼ promote
                                           ┌────────────────┐
                                           │ models/        │
                                           │ champion/      │
                                           └────────────────┘
```

### 학습 하이퍼파라미터

| 항목 | 값 |
|---|---|
| Self-play workers | 16 (RTX 4090 단일) |
| MCTS sims per move | 400~800 |
| Temperature | τ=1.0 (첫 20수), 이후 τ→0 |
| Replay buffer | 500K 포지션, FIFO |
| Symmetry aug | 8-fold (4 회전 × 2 반사) sampling-time |
| Batch size | 512 |
| Optimizer | SGD, momentum=0.9, weight_decay=1e-4 |
| LR schedule | 1e-2 → 1e-3 → 1e-4 (stage drop) |
| Loss | MSE(value) + CE(policy) + L2 reg |
| Training step | 1000 SGD steps / 1000 새 게임 |
| Arena | 40판, MCTS sim=400, no temperature |
| Promote 기준 | candidate 승률 ≥ 55% |

### 추정 학습 비용

- 800 sims × ~80 수/게임 × 1 ms/sim ≈ 64s/게임/워커.
- 16 워커 → 900 게임/시간.
- 50K 게임 ≈ 55시간.
- 학습 step 오버헤드 포함 **3~7일 연속 학습**으로 Phase 3 대비 명확히 강해질 전망.

### 추론 시 시간 예산 (게임 중)
```python
if not in_byoyomi:
    expected_moves_left = max(20, 100 - state.move_number)
    budget_ms = min(main_remaining_ms / expected_moves_left * 1.5, 8000)
else:
    budget_ms = 10000 * 0.85  # 8500ms, 안전 마진
```
MCTS는 `run_until(deadline=now+budget_ms)`로 사고.

### C++ ↔ Python 호출 경로

```cpp
// cpp/include/omok/nn_eval_iface.hpp
struct NNEvalRequest {
    std::array<float, 14*15*15> input_planes;
    // ...
};
struct NNEvalResult {
    std::array<float, 225> policy;
    float value;
};
using EvalFn = std::function<void(std::span<NNEvalRequest> reqs,
                                  std::span<NNEvalResult> outs)>;
```

Python 쪽에서 PyTorch 모델 호출하는 람다를 `MCTS`에 주입. C++ MCTS는 leaf 배치를 모아 `eval_fn`을 호출, GIL은 호출 직전 잡고 호출 후 해제.

장래에 libtorch로 옮기고 싶으면 `nn_eval_iface.hpp`만 동일 시그니처로 C++ 구현 → MCTS 코드 변경 없음.

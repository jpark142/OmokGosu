# OmokGosu — 렌주 룰 명세

> 본 문서는 `cpp/src/rules.cpp`와 테스트 코퍼스 `cpp/tests/fixtures/forbidden_positions.json`의 단일 진실 공급원이다.

## 기본

- 보드: **15×15**
- 두 색: 흑(BLACK), 백(WHITE). **흑이 항상 선착**.
- 한 번에 한 수씩 교대로 빈 칸에 자기 색 돌을 놓는다.
- 가로 / 세로 / 두 대각 중 어느 한 방향으로 자기 색 돌이 **연속 5개** 이상 늘어서면 승리.
  - **흑은 정확히 5개일 때만 승리**. 6개 이상 (장목)은 금수(=패배 또는 무효).
  - **백은 5개 이상 모두 승리**. 6목도 승리.

## 흑의 금수 (3가지)

| 이름 | 영문 | 정의 |
|---|---|---|
| **3-3 (삼삼)** | double-three | 한 수로 동시에 **열린 3 (open three)** 을 2개 이상 만들 때 |
| **4-4 (사사)** | double-four | 한 수로 동시에 **4 (four)** 를 2개 이상 만들 때 (열린/막힌 무관) |
| **장목** | overline | 한 수로 6목 이상을 만들 때 |

백에게는 위 제약이 **모두 없다**. 백은 무엇이든 둘 수 있고, 6목이면 그대로 승리한다.

## 핵심 패턴 용어

기호: `B`=흑, `_`=빈칸, `X`=벽 또는 백 돌.

- **5 (Five)**: `BBBBB` — 정확히 5개 연속. 흑의 승리.
- **Overline (장목)**: `BBBBBB` 이상 — 흑에게는 금수, 백에게는 승리.
- **Open four (열린 4, 활사)**: `_BBBB_` — 양쪽 끝이 빈칸. 한 수로 즉승.
- **Four (4, 사)**: 다음 한 수로 5를 만들 수 있는 모든 형태. 다음 모두 포함:
  - 열린 4: `_BBBB_`
  - 막힌 4: `XBBBB_`, `_BBBBX`
  - 점프 4: `BB_BB`, `B_BBB`, `BBB_B`
- **Open three (열린 3, 활삼)**: 한 수를 더해 **열린 4가 될 수 있는** 3의 형태.
  - 표준 예: `_BBB_` (양쪽 빈칸이 충분히 여유 있을 때), `_BB_B_`, `_B_BB_`
  - **중요**: 그 "한 수"가 그 자체로 금수면 (3-3/4-4/장목 유발) 원래의 3은 열린 3으로 **카운트하지 않는다** — 실제로 열린 4가 될 수 없으므로.
- **Three (3, 삼)**: 한 수로 4가 되는 형태. 3-3 판정에서는 **오직 열린 3만** 카운트.

## 판정 알고리즘 (의사코드)

```
is_forbidden(board, move, BLACK):
    place black at move (tentatively)
    if creates_five(): return false         # 5목은 금수보다 우선 (승리수)
    if creates_overline(): return true      # 장목 금수
    fours = count_fours_through(move)       # 4를 만드는 "다음 수" 자리 수 카운트
    if fours >= 2: return true              # 4-4 금수
    open_threes = count_open_threes_through(move)
    if open_threes >= 2: return true        # 3-3 금수
    return false
```

방향별로 4번 (가로 / 세로 / 좌상-우하 대각 / 우상-좌하 대각) 스캔.

## 재귀 트랩 (반드시 정확히)

가장 흔한 버그 포인트: `_BBB_`이 "열린 3"인지 판단할 때, **그 패턴을 열린 4로 만드는 수가 흑에게 합법인지** 다시 검사해야 한다.

예시 시나리오:
- 흑 A 자리에 두면 한 방향으로 `_BBB_`, 다른 방향으로 `_BBB_`이 생긴다 → "3-3"으로 보일 수 있다.
- 그러나 각 `_BBB_`을 `_BBBB_`(열린 4)로 만드는 단 하나의 수가 **이미 다른 흑 패턴 때문에 4-4 금수**라면, 그 3은 실제로는 열린 4가 될 수 없다 → 열린 3이 **아니다** → 3-3이 **아니다**.

구현:
- `count_open_threes_through(board, move)`는 각 후보 3마다 그 "완성 수"가 자리에 대해 `is_forbidden(board, completion_move, BLACK)`을 재귀 호출.
- **종료 보장**: 재귀할 때마다 가상 돌이 하나 더 놓이므로 상태가 단조 증가, 사이클 없음. 깊이 cap=8에 debug assert.
- **메모화**: 같은 top-level 호출 안에서 zobrist 해시 → bool 캐시.
- **5 우선 규칙**: 재귀 호출에서도 `creates_five()` 체크가 가장 먼저. 5를 만드는 수는 절대 금수가 아니다.

## 패턴 매칭 구현

- 각 위치에 대해 4 방향 × 길이-9 윈도우를 추출.
- 윈도우의 각 칸은 2비트로 인코딩: `00`=빈, `01`=흑, `10`=백, `11`=벽(off-board).
- 9칸 × 2비트 = **18비트** 키 → 262,144 엔트리 룩업 테이블.
- 테이블은 시작 시 `PatternTable::init()`이 모든 가능 윈도우를 분류하여 `{is_five, is_overline, four_count, is_open_three_naive}` 비트필드로 저장.
- "재귀 트랩이 반영된 열린 3"은 룩업이 아니라 위 `is_forbidden` 재귀로 최종 판정.

## 시간제

- **주 시간**: 각 색 **5분 (300초)**.
- 주 시간을 다 쓰면 **byo-yomi 진입**: 10초짜리 period 3개 보유.
- 한 수를 **10초 이내**에 두면 현재 period **리프레시** (일본식).
- 10초를 초과하면 period 1개 소비. 다음 수도 10초 안에 두어야 함.
- **3개를 모두 소진하고도 시간 초과**시 **시간패**.

서버 권위. 클라이언트는 `server_time_ms`로 동기화한 후 표시만 보간한다.

## 승부/종료 사유

| 사유 | 코드 | 설명 |
|---|---|---|
| 5목 완성 | `FIVE` | 정확히 5목(흑) 또는 5목 이상(백) |
| 장목 승 | `OVERLINE_WIN` (백만) | 백이 6목 이상 만들었을 때 |
| 기권 | `RESIGN` | resign 메시지 수신 |
| 시간패 | `TIMEOUT` | 모든 byo-yomi 소진 |
| 금수패 | (의도적 정책 결정) | **현재 정책: 금수 시도는 거부만 하고 게임 종료시키지 않음.** 사용자가 다시 두게 함 (UX 친화). |

> **메모**: 일부 대회 룰은 흑이 금수를 실수로 두면 즉시 패배 처리. OmokGosu는 학습/연습 친화 UI를 위해 거부 + 토스트만 한다. 추후 옵션으로 토글 가능.

## 테스트 코퍼스

`cpp/tests/fixtures/forbidden_positions.json`은 다음 형식의 케이스 배열:

```json
[
  {
    "name": "simple double-three at center",
    "to_move": "BLACK",
    "stones": [{"r":7,"c":7,"color":"BLACK"}, ...],
    "candidate": {"r":7,"c":8},
    "expected": "DOUBLE_THREE"
  }
]
```

`expected` 값: `LEGAL` | `DOUBLE_THREE` | `DOUBLE_FOUR` | `OVERLINE` | `FIVE_WIN`.

C++ doctest (`test_rules.cpp`)와 Python pytest (`test_rules_parity.py`)가 **동일 파일**을 읽어 검증 → 바인딩 드리프트 방지.

목표: **Phase 1 종료 시점에 100개 이상**의 케이스 (RIF 공식 예시 + 재귀 트랩 + 한국식 오목 교재 예시).

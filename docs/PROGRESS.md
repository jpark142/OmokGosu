# OmokGosu — 진행 현황 스냅샷

> 마지막 업데이트: 2026-06-08
> 다음 세션 진입용 컨텍스트. 새 세션을 시작하면 이 문서부터 읽고 `git log`로 보강.

---

## 현재 상태 한 줄 요약

15×15 렌주 룰 엔진 + Minimax/Heuristic AI + 멀티유저 방 시스템 + 채팅 + 전적/기보/랭킹 + 무승부 + AI 게임 비전적 처리 + 단일 세션 로그인까지 완료. 다음 자연스러운 큰 단계는 **Phase D-4 (Fly.io 배포)** 또는 **Phase 4 (AlphaZero)**.

`pytest -q` 111 green, `tsc --noEmit` clean, C++ doctest green. DB는 `server/data/omok.sqlite`, `PRAGMA user_version=2`.

---

## 완료된 단계 (커밋 기준)

### Phase 1 — Renju 룰 엔진 + 웹 UI (`6379f9f`)
- C++20 board / rules / pattern table via pybind11
- 흑 금수 (3-3, 4-4, overline) 판정 + 재귀 트랩
- FastAPI WS 서버 + React/Vite 클라이언트
- 시계: 5분 주시간 + 3×10초 byo-yomi, 250ms timer_tick
- Phase 2 (Minimax + alpha-beta + TT) 동시 포함

### Phase 3A — Auth + Stats (`6bc2403`)
- JWT (HS256, 7일) + bcrypt
- SQLite + SQLModel (`User`, `Match`)
- `/api/auth/{register,login,me,logout}`
- 게임 종료 시 `services.stats.record_match`로 Match INSERT + User wins/losses UPDATE

### Phase 3B — Rooms (`63416ca`)
- In-memory `Room` + `RoomManager` 싱글톤 (재시작 시 소실 OK)
- WS 채널 3개: `/ws/lobby`, `/ws/rooms/{id}`, `/ws/games/{id}`
- 방장 + 게스트 + Ready → Start → 게임 → 자동 방 복귀 흐름
- 로비 "AI와 두기" 별도 진입점

### Phase 3C polish + Phase D-1~3 (`0e8faaa`)
- 버전 SSoT (`VERSION` 파일 + `scripts/sync_version.ps1` 5곳 propagate)
- `GET /api/version` + `X-Client-Version` HTTP 미들웨어 + `?client_version=` WS 검사
- 클라이언트 60초 폴링 + soft 배너 / hard 모달
- 426 / WS 4426 처리

### Phase H — Heuristic AI + VCF (`d9250a4`)
- VCF mate-search (강제 사목 시퀀스 탐색)
- 패턴 가중치 평가 + Minimax 통합
- AI 셀렉터를 difficulty-only (easy/medium/hard)로 단순화

### Phase R — Match replay (`2024ae4`)
- `Match.moves_json` (인라인 마이그레이션으로 추가)
- `GET /api/matches/{id}` + 참가자 인증
- `MatchReplay` 스크럽 UI (슬라이더, 화살표 키)

### Phase L — Leaderboard (`dc36e2d`)
- `GET /api/users/leaderboard` (총 wins desc)
- `/leaderboard` 랭킹 페이지

### Phase P + R + L + C + IM bundle (`ab14c9c`)
- 사용자 프로필 `/users/{id}` (전적 카드 + 최근 50 매치)
- `UserHoverCard` (호버 → 최근 매치 + 프로필 링크)
- Chat 3채널 (lobby/room/game) + 채널별 deque 히스토리 + 시스템 메시지 + 한글 IME composition fix + 채널별 레이트 리밋
- 인게임 → 홈 이탈 시 기권 경고 모달
- 로비/방/인게임 채팅창 높이 차별화 + 시각 인디케이터

---

## 이번 세션 묶음 (5 commits)

### Phase K — Host kick (`fa4ffc3`)
- `room_manager.kick_guest(room_id, host_user_id)` — host & LOBBY & guest-exists 검증 후 슬롯 비움
- WS `kick` 핸들러: `room_state` (게스트 빈 칸) → `kicked{user_id}` broadcast → `lobby_update` → 시스템 메시지
- 클라: `canKick = isHost && room?.guest && room.status === "LOBBY"` 일 때만 "강퇴" 버튼. 대상 user_id 일치 시 "방장에 의해 강퇴되었습니다." 모달 + 확인 → `/lobby`
- Drive-by: `useLobbySocket` / `useRoomSocket` / `useGameSocket`이 chat 라이브 핸들러에서 `is_system` 필드를 누락하던 버그. 라이브 시스템 메시지가 일반 채팅처럼 "시스템: ..." 으로 렌더되던 문제 해결

### 단일 세션 로그인 (`dff48d0`)
- `User.token_version: int = 0` 컬럼 + 인라인 마이그레이션
- JWT에 `ver` claim. 로그인마다 `user.token_version += 1` 후 새 값으로 토큰 발급
- HTTP `get_current_user` / WS `get_current_user_ws` 둘 다 `payload.ver != user.token_version` → 401 / 4401 ("session displaced")
- 구버전 토큰 (no `ver`) 은 ver=0 fallback → 기존 사용자 backward-compat
- 프론트 `fetcher.ts`가 401 body의 detail을 peek → `omok:unauthorized` 이벤트에 reason 첨부. `AuthProvider`가 "session displaced" 일 때만 "다른 곳에서 로그인되어 자동 로그아웃되었습니다." 토스트
- **알려진 gap**: 이미 열려있는 WS 연결은 즉시 끊지 않음. 다음 REST 콜에서 401 받고 정리됨

### AI 게임 → 전적 제외, 히스토리만 유지 (`7f0da43`)
- `services/stats.py`: `is_ai_game=True` 분기에서 wins/losses 손대지 않음. Match 행은 그대로 INSERT
- `stats_updates`도 빈 리스트 (옛 client에 stale 데이터 안 보냄)
- 1회 백필 (`PRAGMA user_version=1`): `Match.is_ai_game=0` 행만으로 `User.wins/losses` 재계산
- 프론트: 매치 히스토리에 amber `vs AI` 칩으로 명확히 표시 (이전: 그냥 "AI" 텍스트)

### 무승부 (`159da1f`)
- `GameOverReason.DRAW` enum 값
- `session.apply_move`: 마지막 수가 5목이 아니면서 `engine.move_number >= 225` → `status=OVER, winner=None, over_reason=DRAW`
- `User.draws: int = 0` 컬럼 + 마이그레이션 + `PRAGMA user_version=2` 백필 (HVH DRAW 행 카운트)
- `services/stats.py`: 무승부 시 양쪽 `user.draws += 1`, wins/losses 불변. `StatsUpdate.draws` 포함
- `fetch_user_stats`가 `(wins, losses, draws)` 튜플 반환. `session.to_state_msg`에서 draws hydrate
- 모든 stats-bearing schema에 draws 추가: `UserSummary`, `LeaderboardEntry`, `RoomMemberSummary`, `PlayerInfo`, `StatsUpdate`
- 프론트 표시 (Lobby 헤더 / Room MemberCard / Leaderboard / UserProfile 전적 카드 / Game PlayerLine / RoomCard / UserHoverCard): draws > 0 일 때만 "N무" 끼워넣음
- **승률 정책**: `wins / (wins + losses)` — 무 분모에서 제외

### 내 전적 + 기보 진입 정돈 (`526ea86`)
- 로비 헤더 우상단에 "🎯 내 전적" 버튼 → `/users/{user.id}`
- `UserProfile` 매치 행 재디자인:
  - 행 전체 `<Link>` 제거 → 우측 "기보 →" 버튼만 클릭 대상 (의도 명확)
  - 행 중앙에 `PlayerChip` × 2: `[돌 색][이름][결과]` vs `[돌 색][이름][결과]`
  - 승자 초록, 패자 빨강, 무 회색. AI는 amber 칩 유지. 본인 이름은 굵게
- 정렬은 backend가 이미 `Match.ended_at.desc()` 사용 중

---

## 현재 코드 구조 (요약)

```
D:/OmokGosu/
├── cpp/                    # C++20 omok_core (pybind11)
├── server/
│   ├── omok_server/
│   │   ├── main.py         # FastAPI app + startup hooks
│   │   ├── schemas.py      # Pydantic — 프로토콜 SSoT
│   │   ├── api/            # REST + WS endpoints
│   │   │   ├── auth.py, users.py, rooms.py, matches.py
│   │   │   ├── ws.py (game), ws_lobby.py, ws_rooms.py
│   │   │   └── chat.py (helpers)
│   │   ├── auth/           # JWT + bcrypt
│   │   ├── db/             # SQLModel + engine + inline migrations
│   │   ├── game/           # session, clock, manager, room, room_manager, engine
│   │   ├── ai/             # random/smart/minimax/heuristic
│   │   └── services/stats.py
│   └── tests/              # pytest 111개
├── web/
│   └── src/
│       ├── routes/         # Login, Lobby, Room, Game, UserProfile, MatchReplay, Leaderboard
│       ├── components/     # Board, Chat, RoomCard, UserHoverCard, AIPlayDialog, ...
│       ├── hooks/          # useGameSocket, useLobbySocket, useRoomSocket, useVersionCheck
│       ├── lib/            # api, fetcher, auth, version
│       └── types/protocol.ts  # 서버 schemas.py 미러
├── docs/                   # 본 문서들
├── scripts/                # bootstrap.ps1, test.ps1, dev.ps1, sync_version.ps1, etc.
└── VERSION                 # 단일 진실 (1.0.0)
```

---

## DB 마이그레이션 히스토리

| Version | 적용 | 설명 |
|---|---|---|
| 0 (initial) | Phase 3A | User / Match 테이블 생성 |
| inline | Phase R | `match.moves_json TEXT DEFAULT '[]'` |
| inline | 이번 세션 | `user.token_version INTEGER DEFAULT 0` |
| inline | 이번 세션 | `user.draws INTEGER DEFAULT 0` |
| `user_version=1` | 이번 세션 | wins/losses 백필 — HVH 매치만 카운트 (AI 게임 제외) |
| `user_version=2` | 이번 세션 | draws 백필 — HVH DRAW 매치 카운트 |

마이그레이션 진입점: `server/omok_server/db/engine.py:_run_inline_migrations`.

---

## 미진행 작업 후보

### 소규모 (반나절~1일)
- **로비 방 검색바** — 3C polish 잔여. 제목/방장 이름 필터
- **WS 세션 즉시 끊기** — 로그인 시 유저별 active WS 등록부에서 force-close. 현재는 옛 WS가 다음 REST 콜 전까지 살아있음
- **인게임 기보 스크럽** — 진행 중인 게임에서 슬라이더로 과거 수 돌아보기 (서버 변경 0, 클라만)

### 중규모 (1~2일)
- **라이브 관전 모드** — 진행 중 게임에 listen-only WS로 붙기
- **렌주 흑 무수(無手) 규칙** — 흑이 둘 수 있는 칸이 모두 금수면 백 승. 현재는 무한 진행 가능성
- **Rematch UX 정돈** — 게임 끝나고 방 복귀 후 자동 카운트다운 / "한 판 더" 강조

### 대규모 (며칠~)
- **Phase D-4 — Fly.io + Docker 배포** (`docs/DEPLOY_CLOUD.md` 참조). 외부 노출, HTTPS, 모바일 접속
- **Phase D-5 — Electron Windows installer** (`docs/DEPLOY_ELECTRON.md`)
- **Phase 4 — AlphaZero 인프라** (`docs/AI.md` 참조). ResNet 10×128 + MCTS PUCT + 자가대국 워커

---

## 알려진 한계 / 트레이드오프 (재시작 시 알아두면 좋은 것)

- **WS 인증**: query param token, 1회 검증, per-message 재검증 안 함. 7일 만료라 게임 중 만료 가능성 낮음
- **단일 worker 고정** (`--workers 1`) — in-memory game/room 상태 때문. 동시 ~30명 이하 권장
- **HTTPS 없음** — 로컬/사내 LAN 신뢰 모델. 배포 단계(D-4)에서 Fly.io가 자동 처리
- **DB 백업** — 수동. `data/omok.sqlite` 파일 복사가 전부. 필요해지면 OneDrive 동기화 폴더 검토
- **token_version 미완성 부분**: 이미 열린 WS는 force-close 안 됨 (위 미진행 항목 참조)
- **C++ omok_core 빌드**: MSVC 2022 필요. `scripts/rebuild_core.ps1` 또는 `bootstrap.ps1` 사용

---

## 다음 세션 시작 시 권장 흐름

1. `git log --oneline -10` 으로 최근 커밋 확인 (이 문서 갱신 이후 추가 작업 있을 수 있음)
2. 본 문서 + `docs/ROADMAP.md` + `docs/PLAN.md` 빠르게 스캔
3. 진행할 작업 선택 → 새 TaskList → 구현 → `scripts/test.ps1`로 회귀 확인 → 커밋
4. 큰 작업 마치고 본 문서 업데이트 (커밋 해시 + 한 줄 설명 추가)

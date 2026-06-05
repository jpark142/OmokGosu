# OmokGosu — 버전 정책

## 단일 진실(SSoT)

루트의 `VERSION` 파일 한 줄이 전체 프로젝트의 버전. `scripts/sync_version.ps1`이
이 값을 다음 위치로 propagate:

| 파일 | 패턴 |
|---|---|
| `pyproject.toml` | `[project] version = "X.Y.Z"` |
| `server/pyproject.toml` | `[project] version = "X.Y.Z"` |
| `web/package.json` | `"version": "X.Y.Z"` |
| `server/omok_server/__init__.py` | `__version__ = "X.Y.Z"` |
| `CMakeLists.txt` | `project(omok_core LANGUAGES CXX VERSION X.Y.Z)` |
| `electron/package.json` (D-5 이후) | `"version": "X.Y.Z"` |

서버는 `from omok_server import __version__`을 통해 런타임에 읽고, 프론트는 vite
`define`이 빌드 시점에 `__OMOK_VERSION__` 상수로 번들에 박는다.

## semver 의미와 클라이언트 대응

```
MAJOR.MINOR.PATCH
```

| 변경 종류 | 예시 | 와이어 호환 | 클라이언트 알림 | `MIN_CLIENT_VERSION` |
|---|---|---|---|---|
| **MAJOR** (1.x.x → 2.0.0) | WS 메시지 스키마 변경, REST 응답 필드 제거 | ❌ 깨짐 | **hard 모달** | **반드시 동반 bump** |
| **MINOR** (1.0.x → 1.1.0) | 새 기능 / 새 필드 추가, 구버전과 wire-호환 OK | ⚠️ 호환되지만 신기능 누락 | **hard 모달** | **동반 bump** (= 새 minor의 .0) |
| **PATCH** (1.0.0 → 1.0.1) | 버그 수정만, 동작/스키마 변화 없음 | ✅ 완전 호환 | **soft 배너** (dismiss 가능) | 유지 |

### `MIN_CLIENT_VERSION` 운영

`server/omok_server/version.py:MIN_CLIENT_VERSION`은 "이 버전 이상의 클라이언트만
받겠다"는 서버 측 하한선. 항상 `<현재 server minor>.0` 형식.

예시:
- 서버가 `1.0.5`일 때 → `MIN_CLIENT_VERSION = "1.0.0"` (같은 minor 안의 모든 patch 허용)
- 서버를 `1.1.0`으로 bump → `MIN_CLIENT_VERSION = "1.1.0"`으로 동반 bump
  → 구버전 `1.0.x` 클라이언트는 426 / 4426 받고 hard 모달

위반 시:
- HTTP `/api/*`: `426 Upgrade Required` + body `{detail, min_client_version, server_version}`
- WS: `close(4426)`

## bump 체크리스트

다음 순서로 한다:

1. **버전 결정**: 어떤 종류의 변경인가? 위 표 보고 MAJOR/MINOR/PATCH 결정.
2. **`VERSION` 수정**:
   ```powershell
   "1.0.1" | Set-Content VERSION
   ```
3. **propagate**:
   ```powershell
   .\scripts\sync_version.ps1
   ```
4. **MINOR/MAJOR면 `MIN_CLIENT_VERSION`도 같이 bump** (잊지 말 것):
   ```python
   # server/omok_server/version.py
   MIN_CLIENT_VERSION = "1.1.0"  # 새 minor에 맞춰 수정
   ```
5. **로컬 검증**:
   ```powershell
   .\scripts\test.ps1
   ```
6. **빌드 + 배포**:
   ```powershell
   .\scripts\build_release.ps1   # 또는 flyctl deploy (D-4 이후)
   ```

`build_release.ps1`은 시작 시 `sync_version.ps1 -Verify`를 호출해서 5(또는 6)곳
모두 `VERSION`과 일치하는지 검사. 누락된 변경이 있으면 빌드 중단.

## 자동 업데이트 흐름

배포 후:
1. 서버가 `__version__`을 갱신해서 부팅
2. 모든 클라이언트는 60초마다 `/api/version` 폴링 + window focus 시 즉시
3. `lib/version.ts:classify(server, minClient, client)`:
   - `client < minClient` → **hard**
   - `server <= client` → **ok** (변화 없음)
   - `server > client`이고 major/minor 차이 → **hard**
   - 그 외 (patch만 차이) → **soft**
4. **soft**: 화면 상단 amber 배너 — "새 버전 X.Y.Z 사용 가능. [지금 새로고침]"
5. **hard**: 전체 화면 모달 (ESC/오버레이/X 차단) — "새로고침해 주세요. [지금 새로고침]"

`window.location.reload()`로 새 번들 받아옴. Vite asset hashing 덕에 캐시 충돌 없음.
`index.html`만 응답 헤더 `Cache-Control: no-store`로 강제 새로 다운로드.

## 참고

- 출범 버전: **1.0.0** (2026-06, Phase 3C까지 완료 시점)
- 0.x.y 시기엔 "beta"로 간주, semver 정책을 엄격히 적용하지 않았음
- 1.0.0 이후로는 위 정책 엄수

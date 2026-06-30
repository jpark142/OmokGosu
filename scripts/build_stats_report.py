#!/usr/bin/env python3
"""Generate docs/STATS.md from the live usage-analytics endpoint.

Fetches GET {STATS_URL} with the shared `X-Stats-Token` header and renders a
Markdown report (summary + daily table + retention cohorts). Designed to run
unattended from CI (see .github/workflows/stats.yml) on a daily cron, but also
runnable by hand:

    OMOK_STATS_TOKEN=<secret> python scripts/build_stats_report.py

Env:
  STATS_URL         endpoint to read (default: prod /api/admin/stats)
  OMOK_STATS_TOKEN  shared secret matching the server's OMOK_STATS_TOKEN

Stdlib only (urllib) so CI needs no pip install.
"""
from __future__ import annotations

import json
import os
import sys
import urllib.error
import urllib.request
from pathlib import Path

DEFAULT_URL = "https://omokgosu.fly.dev/api/admin/stats"
OUT = Path(__file__).resolve().parent.parent / "docs" / "STATS.md"


def fetch() -> dict:
    url = os.environ.get("STATS_URL", DEFAULT_URL)
    token = os.environ.get("OMOK_STATS_TOKEN", "").strip()
    if not token:
        sys.exit("OMOK_STATS_TOKEN is not set — cannot authenticate to the stats endpoint.")
    req = urllib.request.Request(url, headers={"X-Stats-Token": token})
    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            return json.loads(resp.read().decode("utf-8"))
    except urllib.error.HTTPError as e:
        sys.exit(f"stats endpoint returned {e.code}: {e.read().decode('utf-8', 'replace')[:200]}")
    except urllib.error.URLError as e:
        sys.exit(f"could not reach stats endpoint: {e}")


def _pct(rate: float | None) -> str:
    return "—" if rate is None else f"{round(rate * 100)}%"


def render(s: dict) -> str:
    lines: list[str] = []
    lines.append("# 접속 통계 (Usage Stats)")
    lines.append("")
    lines.append(
        "> 자동 생성 파일 — 직접 수정하지 마세요. "
        "`scripts/build_stats_report.py`가 매일 갱신합니다."
    )
    lines.append("")
    lines.append(f"- 생성 시각(UTC): `{s.get('generated_at', '?')}`")
    lines.append(f"- 집계 기준: {s.get('timezone', '?')}")
    lines.append(f"- 데이터 시작: `{s.get('data_since') or '—'}` · 최신: `{s.get('today', '?')}`")
    lines.append("")

    # Summary
    lines.append("## 요약")
    lines.append("")
    lines.append("| 지표 | 값 |")
    lines.append("|---|---|")
    lines.append(f"| 누적 유저 | {s.get('total_users', 0)} |")
    lines.append(f"| 오늘 DAU | {s.get('dau_today', 0)} |")
    lines.append(f"| WAU (7일) | {s.get('wau', 0)} |")
    lines.append(f"| MAU (30일) | {s.get('mau', 0)} |")
    lines.append(f"| 평균 D+1 리텐션 | {_pct(s.get('overall_d1_rate'))} |")
    lines.append(f"| 평균 D+7 리텐션 | {_pct(s.get('overall_d7_rate'))} |")
    lines.append("")

    # Daily (newest first)
    lines.append("## 일별 접속")
    lines.append("")
    lines.append("| 날짜 | DAU | 신규 | 누적 | 동접 피크 |")
    lines.append("|---|--:|--:|--:|--:|")
    for r in reversed(s.get("daily", [])):
        new = f"+{r['new_users']}" if r["new_users"] else "—"
        lines.append(
            f"| {r['day']} | {r['dau']} | {new} | {r['cumulative_users']} | {r['peak_concurrent']} |"
        )
    lines.append("")

    # Retention cohorts (newest first)
    lines.append("## 리텐션 (첫 접속일 코호트별)")
    lines.append("")
    lines.append("| 코호트(첫 접속) | 인원 | D+1 | D+7 |")
    lines.append("|---|--:|--:|--:|")
    for c in reversed(s.get("cohorts", [])):
        d1 = _pct(c.get("d1_rate"))
        if c.get("d1_retained") is not None:
            d1 += f" ({c['d1_retained']})"
        d7 = _pct(c.get("d7_rate"))
        if c.get("d7_retained") is not None:
            d7 += f" ({c['d7_retained']})"
        lines.append(f"| {c['cohort_day']} | {c['size']} | {d1} | {d7} |")
    lines.append("")
    lines.append(
        "_\"—\"는 아직 기간 미경과로 측정 불가(D+7은 7일 경과 필요). "
        "첫 접속일은 접속 로깅 시작 이후 기준._"
    )
    lines.append("")
    return "\n".join(lines)


def main() -> None:
    s = fetch()
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(render(s), encoding="utf-8")
    print(f"wrote {OUT}")


if __name__ == "__main__":
    main()

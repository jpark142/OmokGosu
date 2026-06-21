"""POST /api/bug-reports: in-app bug report endpoint.

Logged-in users hit this from the frontend dialog. Each report is stored
in SQLite (source of truth) and mirrored to a GitHub Issue when the API
token is configured. Anonymity is per-report — a reporter can hide their
username from the public Issue while we still record their identity
locally for de-spamming / follow-up.

Rate-limited at 5 reports per hour per user, enforced in-process; this is
"my friend isn't a spammer" territory, not industrial abuse defense.
"""
from __future__ import annotations

import time
from typing import Annotated, Literal

from fastapi import APIRouter, Depends, HTTPException, Request, status
from pydantic import BaseModel, Field
from sqlmodel import Session

from omok_server.auth.deps import get_current_user, get_db_session
from omok_server.db.models import BugReport, User
from omok_server.services import github_issues
from omok_server.version import SERVER_VERSION

router = APIRouter(prefix="/api/bug-reports", tags=["bug-reports"])


_RATE_LIMIT = 5
_RATE_WINDOW_S = 60 * 60.0
# user_id → list of unix-ts of recent reports. Cleared on process restart;
# acceptable since this is anti-fat-finger, not abuse defense.
_rate_state: dict[int, list[float]] = {}


def _check_rate(user_id: int, *, now: float | None = None) -> bool:
    if now is None:
        now = time.time()
    cutoff = now - _RATE_WINDOW_S
    bucket = _rate_state.setdefault(user_id, [])
    bucket[:] = [t for t in bucket if t >= cutoff]
    if len(bucket) >= _RATE_LIMIT:
        return False
    bucket.append(now)
    return True


def _reset_rate_state() -> None:
    """Test-only helper: wipe the per-user rate buckets."""
    _rate_state.clear()


class BugReportRequest(BaseModel):
    description: str = Field(min_length=1, max_length=4000)
    url: str = Field(default="", max_length=512)
    user_agent: str = Field(default="", max_length=512)
    anonymous: bool = False


class BugReportResponse(BaseModel):
    id: int
    github_issue_number: int | None = None
    github_issue_url: str | None = None
    # Used by the frontend to render the success toast variant.
    mirrored: Literal["github", "local_only"] = "local_only"


def _build_issue_title(description: str, reporter: str) -> str:
    # GitHub titles cap at 256 chars. We keep ours short: first sentence
    # or up to 60 chars, prefixed so the inbox is scannable.
    first_line = description.strip().splitlines()[0]
    snippet = first_line[:60].rstrip()
    if len(first_line) > 60:
        snippet += "…"
    return f"[버그] {snippet}  (by {reporter})"


def _build_issue_body(
    *,
    report: BugReport,
    reporter: str,
) -> str:
    # The reporter line distinguishes 익명 from a named report. Anonymity is
    # an honesty signal to other readers, not a privacy guarantee — we still
    # tell the reporter in the dialog that we keep their identity locally.
    lines = [
        f"**제보자**: {reporter}",
        f"**서버 버전**: `{report.version}`",
        f"**URL**: `{report.url or '(none)'}`",
        f"**브라우저**: `{report.user_agent or '(none)'}`",
        "",
        "---",
        "",
        report.description,
        "",
        "<sub>이 이슈는 인앱 버그 제보로 자동 생성되었습니다.</sub>",
    ]
    return "\n".join(lines)


@router.post("", response_model=BugReportResponse, status_code=status.HTTP_201_CREATED)
async def create_bug_report(
    body: BugReportRequest,
    request: Request,
    user: Annotated[User, Depends(get_current_user)],
    db: Annotated[Session, Depends(get_db_session)],
) -> BugReportResponse:
    if not _check_rate(user.id):
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail="제보가 너무 많습니다. 잠시 후 다시 시도하세요.",
        )

    # Take user_agent from the request header if the client didn't send one
    # in the body — saves the frontend from having to wire it up explicitly.
    ua = body.user_agent or request.headers.get("user-agent", "")[:512]

    report = BugReport(
        user_id=user.id,
        anonymous=body.anonymous,
        version=SERVER_VERSION,
        url=body.url,
        user_agent=ua,
        description=body.description,
    )
    db.add(report)
    db.commit()
    db.refresh(report)

    reporter = "익명 사용자" if body.anonymous else f"@{user.username} (id={user.id})"
    issue = await github_issues.create_bug_issue(
        title=_build_issue_title(body.description, reporter),
        body=_build_issue_body(report=report, reporter=reporter),
        labels=["bug", "in-app-report"],
    )

    if issue is not None:
        report.github_issue_number = issue.number
        report.github_issue_url = issue.html_url
        db.add(report)
        db.commit()
        db.refresh(report)
        return BugReportResponse(
            id=report.id,
            github_issue_number=issue.number,
            github_issue_url=issue.html_url,
            mirrored="github",
        )

    return BugReportResponse(id=report.id, mirrored="local_only")

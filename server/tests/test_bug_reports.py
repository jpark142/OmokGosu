"""POST /api/bug-reports — happy path, anonymity, rate limit, auth, and
GitHub-API outage handling. The GitHub Issues API is mocked at the
`services.github_issues.create_bug_issue` boundary so tests don't need
network access."""
from __future__ import annotations

import pytest
from sqlmodel import Session, select

from omok_server.api import bug_reports as bug_reports_api
from omok_server.db.engine import engine
from omok_server.db.models import BugReport
from omok_server.services import github_issues


@pytest.fixture(autouse=True)
def _reset_rate_state():
    bug_reports_api._reset_rate_state()
    yield
    bug_reports_api._reset_rate_state()


@pytest.fixture
def fake_github_ok(monkeypatch):
    """Stub create_bug_issue to return a synthetic CreatedIssue."""
    calls: list[dict] = []

    async def _fake(*, title: str, body: str, labels=None):
        calls.append({"title": title, "body": body, "labels": labels})
        return github_issues.CreatedIssue(
            number=99,
            html_url=f"https://github.com/jpark142/OmokGosu/issues/{99}",
        )

    monkeypatch.setattr(github_issues, "create_bug_issue", _fake)
    return calls


@pytest.fixture
def fake_github_down(monkeypatch):
    """Stub create_bug_issue to return None with NO token configured —
    simulates the mirror being intentionally off. The endpoint should still
    201 with mirrored='local_only' and stay quiet about it."""
    async def _fake(*, title: str, body: str, labels=None):
        return None
    monkeypatch.setattr(github_issues, "create_bug_issue", _fake)
    monkeypatch.setattr(github_issues, "is_configured", lambda: False)


@pytest.fixture
def fake_github_misfire(monkeypatch):
    """Stub create_bug_issue to return None WHILE a token is configured —
    simulates a real mirror failure (bad token, API 4xx/5xx, network). The
    endpoint should 201 with mirrored='github_failed' so the reporter learns
    their report didn't reach GitHub."""
    async def _fake(*, title: str, body: str, labels=None):
        return None
    monkeypatch.setattr(github_issues, "create_bug_issue", _fake)
    monkeypatch.setattr(github_issues, "is_configured", lambda: True)


def test_report_creates_row_and_mirrors_to_github(auth_client, fake_github_ok) -> None:
    client, _, user = auth_client
    r = client.post(
        "/api/bug-reports",
        json={"description": "전적보기 후 돌아오니 본인이 사라져요"},
    )
    assert r.status_code == 201, r.text
    body = r.json()
    assert body["mirrored"] == "github"
    assert body["github_issue_number"] == 99
    assert "/issues/99" in body["github_issue_url"]

    # DB row mirrors the response.
    with Session(engine) as db:
        row = db.exec(select(BugReport).where(BugReport.id == body["id"])).one()
        assert row.user_id == user["id"]
        assert row.anonymous is False
        assert row.github_issue_number == 99
        assert "전적보기" in row.description

    # Issue body contains the reporter's @username and the description.
    assert len(fake_github_ok) == 1
    call = fake_github_ok[0]
    assert user["username"] in call["title"] or user["username"] in call["body"]
    assert "전적보기" in call["body"]
    assert call["labels"] == ["bug", "in-app-report"]


def test_report_anonymous_hides_username_in_issue(auth_client, fake_github_ok) -> None:
    client, _, user = auth_client
    r = client.post(
        "/api/bug-reports",
        json={"description": "익명으로 알리고 싶어요", "anonymous": True},
    )
    assert r.status_code == 201
    body = r.json()
    assert fake_github_ok[0]["body"].count(user["username"]) == 0
    assert "익명" in fake_github_ok[0]["body"]

    # But the local row still records the user_id for follow-up.
    with Session(engine) as db:
        row = db.exec(select(BugReport).where(BugReport.id == body["id"])).one()
        assert row.user_id == user["id"]
        assert row.anonymous is True


def test_report_with_github_down_returns_local_only(auth_client, fake_github_down) -> None:
    client, _, _ = auth_client
    r = client.post("/api/bug-reports", json={"description": "github 죽어도 저장돼야 해요"})
    assert r.status_code == 201
    body = r.json()
    assert body["mirrored"] == "local_only"
    assert body["github_issue_number"] is None
    assert body["github_issue_url"] is None

    # Row exists in DB regardless.
    with Session(engine) as db:
        row = db.exec(select(BugReport).where(BugReport.id == body["id"])).one()
        assert row.github_issue_number is None


def test_report_mirror_failure_reports_github_failed(
    auth_client, fake_github_misfire
) -> None:
    client, _, _ = auth_client
    r = client.post(
        "/api/bug-reports",
        json={"description": "토큰은 있는데 미러가 깨졌어요"},
    )
    assert r.status_code == 201
    body = r.json()
    # Configured mirror that failed must NOT be silently downgraded to
    # local_only — the reporter needs to know it didn't reach GitHub.
    assert body["mirrored"] == "github_failed"
    assert body["github_issue_number"] is None
    assert body["github_issue_url"] is None

    # Still persisted locally.
    with Session(engine) as db:
        row = db.exec(select(BugReport).where(BugReport.id == body["id"])).one()
        assert row.github_issue_number is None


def test_report_requires_auth(client) -> None:
    r = client.post("/api/bug-reports", json={"description": "anon attempt"})
    assert r.status_code == 401


def test_report_validates_empty_description(auth_client) -> None:
    client, _, _ = auth_client
    r = client.post("/api/bug-reports", json={"description": ""})
    assert r.status_code == 422  # Pydantic min_length=1


def test_report_validates_description_too_long(auth_client) -> None:
    client, _, _ = auth_client
    r = client.post("/api/bug-reports", json={"description": "x" * 5000})
    assert r.status_code == 422  # Pydantic max_length=4000


def test_report_captures_url_and_user_agent_from_body(auth_client, fake_github_ok) -> None:
    client, _, _ = auth_client
    r = client.post(
        "/api/bug-reports",
        json={
            "description": "with context",
            "url": "/lobby",
            "user_agent": "Mozilla/Test",
        },
    )
    assert r.status_code == 201
    body = fake_github_ok[0]["body"]
    assert "/lobby" in body
    assert "Mozilla/Test" in body


def test_rate_limit_caps_at_5_per_hour(auth_client, fake_github_ok) -> None:
    client, _, _ = auth_client
    for i in range(5):
        r = client.post("/api/bug-reports", json={"description": f"report {i}"})
        assert r.status_code == 201, f"#{i} unexpectedly rejected"
    # 6th attempt is throttled.
    r = client.post("/api/bug-reports", json={"description": "one too many"})
    assert r.status_code == 429
    assert "너무 많" in r.json()["detail"]

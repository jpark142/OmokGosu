"""Create GitHub Issues from in-app bug reports.

Authentication: fine-grained Personal Access Token in OMOK_GITHUB_TOKEN
secret, scoped to Issues:write on jpark142/OmokGosu only. If the secret is
missing, the function is a no-op — the bug report still lands in our
SQLite for follow-up; we just don't mirror to GitHub.

The repo is hard-coded; this isn't reusable infrastructure, it's a
one-deployment escape hatch. If the project ever ships under a different
slug, override via OMOK_GITHUB_REPO.
"""
from __future__ import annotations

import logging
import os
from dataclasses import dataclass

import httpx

_log = logging.getLogger(__name__)

_DEFAULT_REPO = "jpark142/OmokGosu"
_API_BASE = "https://api.github.com"
_REQUEST_TIMEOUT_S = 8.0


@dataclass
class CreatedIssue:
    number: int
    html_url: str


def _token() -> str | None:
    tok = os.environ.get("OMOK_GITHUB_TOKEN", "").strip()
    return tok or None


def _repo() -> str:
    return os.environ.get("OMOK_GITHUB_REPO", _DEFAULT_REPO).strip() or _DEFAULT_REPO


def is_configured() -> bool:
    """True if the env supplies a token we can hit GitHub with. Used by the
    bug-report endpoint to decide whether to attempt the mirror and what
    message to return to the client."""
    return _token() is not None


async def create_bug_issue(
    *,
    title: str,
    body: str,
    labels: list[str] | None = None,
) -> CreatedIssue | None:
    """POST /repos/{repo}/issues. Returns the new issue's number + URL, or
    None when (a) no token is configured, (b) the API rejected the request,
    or (c) the network was unreachable. The caller treats None as "GitHub
    mirror failed; SQLite is authoritative."""
    token = _token()
    if token is None:
        _log.info("github_issues: no OMOK_GITHUB_TOKEN — skipping mirror")
        return None

    url = f"{_API_BASE}/repos/{_repo()}/issues"
    headers = {
        "Authorization": f"Bearer {token}",
        "Accept": "application/vnd.github+json",
        "X-GitHub-Api-Version": "2022-11-28",
        "User-Agent": "omokgosu-bug-reporter",
    }
    payload: dict = {"title": title, "body": body}
    if labels:
        payload["labels"] = labels

    try:
        async with httpx.AsyncClient(timeout=_REQUEST_TIMEOUT_S) as client:
            resp = await client.post(url, json=payload, headers=headers)
    except httpx.HTTPError as e:
        _log.warning("github_issues: network error creating issue: %s", e)
        return None

    if resp.status_code not in (200, 201):
        _log.warning(
            "github_issues: API returned %s — %s",
            resp.status_code,
            resp.text[:200],
        )
        return None

    data = resp.json()
    return CreatedIssue(
        number=int(data["number"]),
        html_url=str(data["html_url"]),
    )

"""Version comparison utilities + client compatibility gate.

`SERVER_VERSION` mirrors `omok_server.__version__` (which is propagated from the
root `VERSION` file by `scripts/sync_version.ps1`).

`MIN_CLIENT_VERSION` declares the oldest client that this server will serve.
Bumped together with any MINOR or MAJOR `SERVER_VERSION` bump — see
`docs/VERSIONING.md` for the rule.
"""
from __future__ import annotations

import re

from omok_server import __version__ as _PACKAGE_VERSION

SERVER_VERSION: str = _PACKAGE_VERSION
MIN_CLIENT_VERSION: str = "1.6.2"  # bump together with any MINOR/MAJOR server bump

_SEMVER_RE = re.compile(r"^(\d+)\.(\d+)\.(\d+)$")


def parse_semver(s: str) -> tuple[int, int, int] | None:
    """Return (major, minor, patch), or None if `s` isn't a clean X.Y.Z."""
    m = _SEMVER_RE.match(s.strip()) if isinstance(s, str) else None
    if m is None:
        return None
    return (int(m.group(1)), int(m.group(2)), int(m.group(3)))


def compare_semver(a: str, b: str) -> int:
    """Return -1 / 0 / +1 for a < b / a == b / a > b. Unparseable inputs → 0."""
    pa, pb = parse_semver(a), parse_semver(b)
    if pa is None or pb is None:
        return 0
    if pa < pb: return -1
    if pa > pb: return +1
    return 0


def is_client_compatible(client_version: str | None) -> bool:
    """True if the client is at or above MIN_CLIENT_VERSION.

    Returns True for None / empty / unparseable — the gate is intentionally
    lenient on missing headers (curl, debugging, external tools). The real
    OmokGosu frontend always sends a valid version.
    """
    if not client_version:
        return True
    parsed = parse_semver(client_version)
    if parsed is None:
        return True
    min_parsed = parse_semver(MIN_CLIENT_VERSION)
    if min_parsed is None:
        return True
    return parsed >= min_parsed

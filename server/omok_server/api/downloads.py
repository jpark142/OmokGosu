"""Serve the Windows desktop installer straight off the Fly volume.

This lets us hand out the `.exe` without a public GitHub release. The binary is
NOT in the Docker image or git (it's ~75 MB) — it's uploaded once to the
persistent volume under OMOK_DOWNLOAD_DIR (default `/data/downloads`):

    flyctl ssh sftp shell -a omokgosu
    > put dist-electron/OmokGosu-Setup-1.8.1.exe /data/downloads/

The route serves the NEWEST `*.exe` in that directory, so dropping in a new
build replaces the download with no redeploy. These routes live OUTSIDE `/api`
so the client-version gate never touches them and any browser can fetch them.
"""
from __future__ import annotations

import os
from pathlib import Path

from fastapi import APIRouter, HTTPException
from fastapi.responses import FileResponse, HTMLResponse

router = APIRouter(prefix="/download", tags=["download"])

# PE/EXE media type. Browsers download rather than try to render it; combined
# with FileResponse's Content-Disposition: attachment this always saves to disk.
_EXE_MEDIA_TYPE = "application/vnd.microsoft.portable-executable"


def _download_dir() -> Path:
    return Path(os.environ.get("OMOK_DOWNLOAD_DIR", "/data/downloads"))


def _latest_exe() -> Path | None:
    d = _download_dir()
    if not d.is_dir():
        return None
    exes = sorted(d.glob("*.exe"), key=lambda p: p.stat().st_mtime, reverse=True)
    return exes[0] if exes else None


@router.get("/windows")
def download_windows() -> FileResponse:
    """Stream the latest Windows installer as an attachment."""
    exe = _latest_exe()
    if exe is None:
        raise HTTPException(status_code=404, detail="설치 파일이 아직 준비되지 않았습니다.")
    # FileResponse supports Range requests, so interrupted 75 MB downloads resume.
    return FileResponse(exe, media_type=_EXE_MEDIA_TYPE, filename=exe.name)


@router.get("", response_class=HTMLResponse)
@router.get("/", response_class=HTMLResponse)
def download_page() -> HTMLResponse:
    """A tiny shareable landing page: one button to grab the installer, plus the
    'just use the website' escape hatch and the SmartScreen heads-up."""
    exe = _latest_exe()
    if exe is None:
        button = (
            '<p style="color:#b91c1c">설치 파일이 아직 준비되지 않았습니다. '
            "잠시 후 다시 시도해 주세요.</p>"
        )
    else:
        size_mb = exe.stat().st_size / (1024 * 1024)
        button = (
            '<a class="btn" href="/download/windows">⬇ Windows 앱 다운로드</a>'
            f'<p class="meta">{exe.name} · {size_mb:.0f} MB</p>'
        )

    html = f"""<!doctype html>
<html lang="ko">
<head>
<meta charset="utf-8" />
<meta name="viewport" content="width=device-width, initial-scale=1" />
<title>오목고수 — 다운로드</title>
<style>
  body {{ font-family: system-ui, sans-serif; background:#0f172a; color:#e2e8f0;
         margin:0; display:flex; min-height:100vh; align-items:center; justify-content:center; }}
  .card {{ background:#1e293b; padding:2.5rem; border-radius:14px; max-width:420px;
          text-align:center; box-shadow:0 10px 40px rgba(0,0,0,.4); }}
  h1 {{ margin:0 0 .25rem; font-size:1.5rem; }}
  .sub {{ color:#94a3b8; margin:0 0 1.75rem; font-size:.9rem; }}
  .btn {{ display:inline-block; background:#f59e0b; color:#0f172a; font-weight:700;
         padding:.8rem 1.4rem; border-radius:9px; text-decoration:none; }}
  .btn:hover {{ background:#fbbf24; }}
  .meta {{ color:#64748b; font-size:.78rem; margin:.6rem 0 0; }}
  .note {{ color:#94a3b8; font-size:.78rem; margin-top:1.5rem; line-height:1.5; }}
  a.web {{ color:#fbbf24; }}
</style>
</head>
<body>
  <div class="card">
    <h1>오목고수 ⚫⚪</h1>
    <p class="sub">Windows 데스크탑 앱</p>
    {button}
    <p class="note">
      설치 시 "Windows의 PC 보호" 경고가 뜨면 <b>추가 정보 → 실행</b>을 누르세요.<br />
      설치 없이 바로 하려면 → <a class="web" href="/">웹에서 플레이</a>
    </p>
  </div>
</body>
</html>"""
    return HTMLResponse(html)

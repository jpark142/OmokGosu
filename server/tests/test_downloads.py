"""/download/* — serving the Windows installer off the volume."""
from __future__ import annotations


def test_windows_download_404_when_no_file(client, monkeypatch, tmp_path) -> None:
    monkeypatch.setenv("OMOK_DOWNLOAD_DIR", str(tmp_path))  # empty dir
    r = client.get("/download/windows")
    assert r.status_code == 404


def test_windows_download_serves_latest_exe(client, monkeypatch, tmp_path) -> None:
    monkeypatch.setenv("OMOK_DOWNLOAD_DIR", str(tmp_path))
    exe = tmp_path / "OmokGosu-Setup-1.8.1.exe"
    exe.write_bytes(b"MZ fake installer bytes")

    r = client.get("/download/windows")
    assert r.status_code == 200
    assert r.content == b"MZ fake installer bytes"
    cd = r.headers["content-disposition"]
    assert "attachment" in cd
    assert "OmokGosu-Setup-1.8.1.exe" in cd


def test_windows_download_picks_newest_of_several(client, monkeypatch, tmp_path) -> None:
    import os
    import time

    monkeypatch.setenv("OMOK_DOWNLOAD_DIR", str(tmp_path))
    old = tmp_path / "OmokGosu-Setup-1.0.0.exe"
    new = tmp_path / "OmokGosu-Setup-1.8.1.exe"
    old.write_bytes(b"old")
    new.write_bytes(b"new")
    # Make `new` unambiguously newer regardless of write order/fs resolution.
    past = time.time() - 100
    os.utime(old, (past, past))

    r = client.get("/download/windows")
    assert r.status_code == 200
    assert "OmokGosu-Setup-1.8.1.exe" in r.headers["content-disposition"]
    assert r.content == b"new"


def test_download_landing_page_renders(client, monkeypatch, tmp_path) -> None:
    monkeypatch.setenv("OMOK_DOWNLOAD_DIR", str(tmp_path))
    (tmp_path / "OmokGosu-Setup-1.8.1.exe").write_bytes(b"x" * 2048)

    r = client.get("/download")
    assert r.status_code == 200
    assert "text/html" in r.headers["content-type"]
    assert "/download/windows" in r.text  # the download button links to the file
    assert "오목고수" in r.text


def test_download_page_handles_missing_file(client, monkeypatch, tmp_path) -> None:
    monkeypatch.setenv("OMOK_DOWNLOAD_DIR", str(tmp_path))  # empty
    r = client.get("/download")
    assert r.status_code == 200  # page still renders, just without a button
    assert "준비되지 않" in r.text

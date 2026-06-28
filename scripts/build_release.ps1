# OmokGosu — one-shot release.
#
# Does the whole ship in order:
#   1. verify VERSION is consistent across all propagation targets
#   2. deploy the web app + server to Fly
#   3. build the Windows installer (electron-builder)
#   4. upload it to the Fly volume so https://<app>.fly.dev/download serves it
#   5. purge older installers from the volume (keep it from filling up)
#
# Run from a REAL terminal — flyctl ssh/sftp need a console (a non-interactive
# pipe fails with "handle is invalid"):
#   .\scripts\build_release.ps1            # full release (web + exe)
#   .\scripts\build_release.ps1 -SkipExe   # web/server only; skip the ~3min exe build
#
# Re-uploading the exe each release is OPTIONAL: the installer is a thin shell
# that loads the live site, so even an old installer always shows the latest
# web app. This step only keeps the downloadable file's version label in sync.

param(
    [switch]$SkipExe,
    [string]$App = "omokgosu"
)

# Continue (not Stop): flyctl writes progress to stderr, which PowerShell 5.1
# would otherwise promote to a terminating error. We gate on $LASTEXITCODE.
$ErrorActionPreference = "Continue"
$scriptDir = $PSScriptRoot
$root = Split-Path -Parent $scriptDir

function Step($msg) { Write-Host "`n[release] $msg" -ForegroundColor Cyan }
function Die($msg)  { Write-Host "[release] $msg" -ForegroundColor Red; exit 1 }

# 1. Version sanity — refuse to ship a half-propagated bump.
Step "verifying version sync"
& (Join-Path $scriptDir "sync_version.ps1") -Verify
if ($LASTEXITCODE -ne 0) { Die "version mismatch — run sync_version.ps1 first" }

$version = (Get-Content (Join-Path $root "VERSION") -Raw).Trim()
Step "releasing v$version"

# 2. Deploy web app + server.
Step "flyctl deploy"
& flyctl deploy --now -a $App
if ($LASTEXITCODE -ne 0) { Die "deploy FAILED" }

if ($SkipExe) {
    Step "done (web/server only; -SkipExe). https://$App.fly.dev"
    exit 0
}

# 3. Build the Windows installer.
Step "building Windows installer"
& (Join-Path $scriptDir "build_electron.ps1")
if ($LASTEXITCODE -ne 0) { Die "exe build FAILED" }

$exe = Join-Path $root ("dist-electron\OmokGosu-Setup-{0}.exe" -f $version)
if (-not (Test-Path $exe)) { Die "installer not found: $exe" }

# 4. Upload to the Fly volume. The /download route serves the newest *.exe there.
$remoteName = "OmokGosu-Setup-$version.exe"
Step "uploading $remoteName to volume"
& flyctl ssh sftp put $exe "/data/downloads/$remoteName" -a $App
if ($LASTEXITCODE -ne 0) { Die "upload FAILED" }

# 5. Purge older installers so the 1 GB volume can't fill up over many releases.
#    Runs AFTER the upload, so there's never a window with no downloadable file.
#    Non-fatal: a failed purge just leaves stale files; the newest is still served.
Step "purging older installers from volume"
& flyctl ssh console -a $App -C "find /data/downloads -name '*.exe' ! -name '$remoteName' -delete"
if ($LASTEXITCODE -ne 0) { Write-Host "[release] WARN: purge failed (non-fatal)" -ForegroundColor Yellow }

Step "DONE - v$version live"
Write-Host "  Web:       https://$App.fly.dev"
Write-Host "  Installer: https://$App.fly.dev/download"

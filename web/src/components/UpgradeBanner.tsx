// Sticky amber banner shown when a patch-level update is available.
// Dismissable for the current session only — the next poll tick will re-show
// if the user is still on a stale version, and promotes to hard modal if
// the gap widens to a minor/major.

import { useEffect, useState } from "react";

import { useVersion } from "@/lib/versionContext";

const DISMISS_KEY = "omok_upgrade_banner_dismissed";

export default function UpgradeBanner() {
  const { status, serverVersion, clientVersion } = useVersion();
  const [dismissed, setDismissed] = useState<string | null>(() =>
    sessionStorage.getItem(DISMISS_KEY),
  );

  // When the server version changes (e.g., we polled a newer one), reset the
  // dismissal so a fresh banner can reappear.
  useEffect(() => {
    if (status !== "soft") return;
    if (dismissed && serverVersion && dismissed !== serverVersion) {
      sessionStorage.removeItem(DISMISS_KEY);
      setDismissed(null);
    }
  }, [status, serverVersion, dismissed]);

  if (status !== "soft" || !serverVersion) return null;
  if (dismissed === serverVersion) return null;

  const onReload = () => window.location.reload();
  const onDismiss = () => {
    sessionStorage.setItem(DISMISS_KEY, serverVersion);
    setDismissed(serverVersion);
  };

  return (
    <div className="sticky top-0 z-30 bg-amber-100 border-b border-amber-300 text-amber-900 text-sm">
      <div className="max-w-5xl mx-auto px-4 py-2 flex items-center gap-3">
        <span className="font-medium">새 버전 {serverVersion} 사용 가능</span>
        <span className="text-amber-700 text-xs">(현재 {clientVersion})</span>
        <div className="flex-1" />
        <button
          onClick={onReload}
          className="px-3 py-1 bg-amber-600 text-white rounded hover:bg-amber-700 text-xs font-medium"
        >
          지금 새로고침
        </button>
        <button
          onClick={onDismiss}
          className="text-amber-700 hover:text-amber-900 text-xs"
          aria-label="닫기"
        >
          ✕
        </button>
      </div>
    </div>
  );
}

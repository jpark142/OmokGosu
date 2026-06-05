// Full-screen blocking modal shown when the server has bumped past a
// breaking change (minor/major), or the server returned 426. No close
// affordance — the user must reload.

import { useVersion } from "@/lib/versionContext";

export default function UpgradeModal() {
  const { status, serverVersion, clientVersion } = useVersion();
  if (status !== "hard") return null;

  const onReload = () => window.location.reload();

  return (
    <div
      className="fixed inset-0 z-50 bg-black/60 flex items-center justify-center p-4"
      // Block all backdrop clicks / escape — user MUST reload.
      onClick={(e) => e.stopPropagation()}
      onKeyDown={(e) => e.preventDefault()}
      role="dialog"
      aria-modal="true"
    >
      <div className="bg-white rounded-lg shadow-xl p-8 max-w-md w-full">
        <h2 className="text-2xl font-bold mb-2">업데이트가 필요합니다</h2>
        <div className="text-stone-700 mb-4 leading-relaxed">
          OmokGosu가 업데이트되었습니다. 계속 사용하시려면 새로고침해 주세요.
        </div>
        {serverVersion && (
          <div className="text-xs text-stone-500 mb-6">
            현재 {clientVersion} → 서버 {serverVersion}
          </div>
        )}
        <button
          onClick={onReload}
          className="w-full py-3 bg-stone-900 text-white rounded font-medium hover:bg-stone-800"
        >
          지금 새로고침
        </button>
      </div>
    </div>
  );
}

// Bottom-left mute toggle. Mirrors the BugReportLauncher pattern
// (small fixed button at the bottom corner) and reflects the
// localStorage-backed sound flag.

import { useEffect, useState } from "react";

import { isSoundEnabled, setSoundEnabled, subscribeSoundEnabled } from "@/lib/sound";

export default function SoundToggle() {
  const [enabled, setEnabled] = useState(isSoundEnabled);

  useEffect(() => {
    return subscribeSoundEnabled(setEnabled);
  }, []);

  const toggle = () => setSoundEnabled(!enabled);

  return (
    <button
      onClick={toggle}
      // Pinned to the top-right so it never collides with the
      // bottom-left version/bug-report row or the bottom-right "by jypark"
      // signature. Small enough to ignore when you're not looking for it.
      className="fixed top-2 right-3 text-xs text-stone-400/70 hover:text-stone-700 transition select-none px-2 py-1 rounded hover:bg-white/60"
      title={enabled ? "사운드 끄기" : "사운드 켜기"}
      aria-label={enabled ? "사운드 끄기" : "사운드 켜기"}
    >
      {enabled ? "🔊 사운드" : "🔇 사운드"}
    </button>
  );
}

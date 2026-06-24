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
      className="fixed bottom-2 left-32 text-xs text-stone-400/70 hover:text-stone-700 transition select-none"
      title={enabled ? "사운드 끄기" : "사운드 켜기"}
      aria-label={enabled ? "사운드 끄기" : "사운드 켜기"}
    >
      {enabled ? "🔊 사운드" : "🔇 사운드"}
    </button>
  );
}

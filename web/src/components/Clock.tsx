import { useEffect, useState } from "react";

import { cn, formatClock } from "@/lib/utils";
import type { ClockSnapshot, ColorStr } from "@/types/protocol";

interface ClockProps {
  color: ColorStr;
  snap: ClockSnapshot;
  active: boolean;
  serverTimeMs: number;
}

// Light interpolation: we don't trust the local clock, but we do extrapolate
// from the last server snapshot for a smooth countdown between 250ms ticks.
export default function Clock({ color, snap, active, serverTimeMs }: ClockProps) {
  const [, force] = useState(0);

  useEffect(() => {
    if (!active) return;
    const t = setInterval(() => force((n) => n + 1), 100);
    return () => clearInterval(t);
  }, [active]);

  // Compute display values. Use server snapshot as ground truth, deduct local elapsed since.
  const localElapsed = active ? Math.max(0, Date.now() - serverTimeMs) : 0;
  const mainDisplay = Math.max(0, snap.main_ms - (snap.in_byoyomi ? 0 : localElapsed));
  const byoyomiDisplay = snap.in_byoyomi
    ? Math.max(0, snap.byoyomi_ms - localElapsed)
    : snap.byoyomi_ms;

  return (
    <div
      className={cn(
        // Fixed min-width so the box doesn't shrink when the byo-yomi
        // number goes from two digits ("10") to one ("9, 8, ...") or
        // when main is showing "5:00" vs "0:09" etc.
        "flex flex-col items-center px-4 py-3 rounded-md border transition-colors min-w-[7rem]",
        active ? "bg-amber-50 border-amber-400 shadow-sm" : "bg-stone-100 border-stone-200",
      )}
    >
      <div className="text-xs uppercase tracking-wider text-stone-500">
        {color === "BLACK" ? "흑" : "백"}
      </div>
      {!snap.in_byoyomi ? (
        <div
          className={cn(
            "font-mono text-3xl tabular-nums mt-1",
            mainDisplay < 30_000 && active ? "text-red-600" : "text-stone-900",
          )}
        >
          {formatClock(mainDisplay)}
        </div>
      ) : (
        <div className="flex items-center gap-2 mt-1">
          {/* w-[2ch] reserves space for two digits so "9" doesn't shift
              the period dots to the left when the number drops below 10. */}
          <div
            className={cn(
              "font-mono text-3xl tabular-nums text-center w-[2ch]",
              byoyomiDisplay < 5000 && active ? "text-red-600" : "text-stone-900",
            )}
          >
            {Math.ceil(byoyomiDisplay / 1000)}
          </div>
          <div className="flex gap-1">
            {Array.from({ length: 3 }).map((_, i) => (
              <div
                key={i}
                className={cn(
                  "w-2 h-2 rounded-full",
                  i < snap.byoyomi_periods ? "bg-amber-500" : "bg-stone-300",
                )}
              />
            ))}
          </div>
        </div>
      )}
    </div>
  );
}

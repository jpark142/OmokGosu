// Global version status. Provider sits OUTSIDE AuthProvider so version checks
// happen even on the login page (an outdated client should see the upgrade
// modal before they can try to log in).

import { createContext, useContext } from "react";
import type { ReactNode } from "react";

import { useVersionCheck, type UseVersionCheck } from "@/hooks/useVersionCheck";

const VersionContext = createContext<UseVersionCheck | null>(null);

export function VersionProvider({ children }: { children: ReactNode }) {
  const value = useVersionCheck();
  return <VersionContext.Provider value={value}>{children}</VersionContext.Provider>;
}

export function useVersion(): UseVersionCheck {
  const v = useContext(VersionContext);
  if (v === null) throw new Error("useVersion must be used within VersionProvider");
  return v;
}

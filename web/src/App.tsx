import { Navigate, Route, Routes } from "react-router-dom";

import { useEffect } from "react";

import BugReportLauncher from "@/components/BugReportLauncher";
import SoundToggle from "@/components/SoundToggle";
import UpgradeBanner from "@/components/UpgradeBanner";
import UpgradeModal from "@/components/UpgradeModal";
import { AuthProvider, useAuth } from "@/lib/auth";
import { hookAutoUnlock } from "@/lib/sound";
import { CLIENT_VERSION } from "@/lib/version";
import { VersionProvider } from "@/lib/versionContext";
import Game from "@/routes/Game";
import Leaderboard from "@/routes/Leaderboard";
import Lobby from "@/routes/Lobby";
import Login from "@/routes/Login";
import MatchReplay from "@/routes/MatchReplay";
import Room from "@/routes/Room";
import UserProfile from "@/routes/UserProfile";

function Protected({ children }: { children: React.ReactNode }) {
  const { user, initializing } = useAuth();
  if (initializing) {
    return (
      <div className="min-h-screen flex items-center justify-center text-stone-500 text-sm">
        로딩 중...
      </div>
    );
  }
  if (!user) return <Navigate to="/login" replace />;
  return <>{children}</>;
}

function PublicOnly({ children }: { children: React.ReactNode }) {
  const { user, initializing } = useAuth();
  if (initializing) {
    return (
      <div className="min-h-screen flex items-center justify-center text-stone-500 text-sm">
        로딩 중...
      </div>
    );
  }
  if (user) return <Navigate to="/lobby" replace />;
  return <>{children}</>;
}

export default function App() {
  // Resume AudioContext + prime speechSynthesis on the user's first click.
  // Browser autoplay policies block both until a gesture; piggybacking on
  // any interaction means the very first move sound / TTS isn't lost.
  useEffect(() => hookAutoUnlock(), []);

  // VersionProvider wraps everything (including AuthProvider) so version checks
  // run even on the login page — an outdated client should see the upgrade
  // modal before they even try to log in.
  return (
    <VersionProvider>
      <UpgradeBanner />
      <AuthProvider>
        <Routes>
          <Route path="/login" element={<PublicOnly><Login /></PublicOnly>} />
          <Route path="/" element={<Navigate to="/lobby" replace />} />
          <Route path="/lobby" element={<Protected><Lobby /></Protected>} />
          <Route path="/rooms/:roomId" element={<Protected><Room /></Protected>} />
          <Route path="/game/:gameId" element={<Protected><Game /></Protected>} />
          <Route path="/matches/:matchId" element={<Protected><MatchReplay /></Protected>} />
          <Route path="/leaderboard" element={<Protected><Leaderboard /></Protected>} />
          <Route path="/users/:userId" element={<Protected><UserProfile /></Protected>} />
        </Routes>
        <BugReportLauncher />
      </AuthProvider>
      <UpgradeModal />
      <SoundToggle />
      <span className="fixed bottom-2 left-3 text-xs text-stone-400/60 pointer-events-none select-none tabular-nums">
        v{CLIENT_VERSION}
      </span>
      <span className="fixed bottom-2 right-3 text-xs text-stone-400/60 hover:text-stone-700 transition pointer-events-none select-none">
        by jypark
      </span>
    </VersionProvider>
  );
}

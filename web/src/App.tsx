import { Navigate, Route, Routes } from "react-router-dom";

import { AuthProvider, useAuth } from "@/lib/auth";
import Game from "@/routes/Game";
import Lobby from "@/routes/Lobby";
import Login from "@/routes/Login";
import Room from "@/routes/Room";

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
  return (
    <AuthProvider>
      <Routes>
        <Route path="/login" element={<PublicOnly><Login /></PublicOnly>} />
        <Route path="/" element={<Navigate to="/lobby" replace />} />
        <Route path="/lobby" element={<Protected><Lobby /></Protected>} />
        <Route path="/rooms/:roomId" element={<Protected><Room /></Protected>} />
        <Route path="/game/:gameId" element={<Protected><Game /></Protected>} />
      </Routes>
    </AuthProvider>
  );
}

// Floating "버그 제보" launcher: shows a small button at the bottom-left
// edge (right of the version chip) and opens the BugReportDialog when
// clicked. Hidden for logged-out viewers — the endpoint requires auth
// and we don't want the button to read as "you can submit" then bounce
// off a 401.

import { useState } from "react";

import { useAuth } from "@/lib/auth";

import BugReportDialog from "./BugReportDialog";

export default function BugReportLauncher() {
  const { user } = useAuth();
  const [open, setOpen] = useState(false);

  if (!user) return null;

  return (
    <>
      <button
        onClick={() => setOpen(true)}
        className="fixed bottom-2 left-16 text-xs text-stone-400/70 hover:text-stone-700 transition select-none"
        title="버그를 발견하셨나요? 알려주세요."
      >
        🐛 버그 제보
      </button>
      <BugReportDialog open={open} onClose={() => setOpen(false)} />
    </>
  );
}

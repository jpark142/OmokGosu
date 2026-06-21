// In-app bug report dialog. Captures a free-form description plus the
// browser context (current URL + UA) and submits to /api/bug-reports.
// The server mirrors to a GitHub Issue when its OMOK_GITHUB_TOKEN is set.

import { useEffect, useState } from "react";
import { toast } from "sonner";

import { submitBugReport } from "@/lib/api";
import { useAuth } from "@/lib/auth";
import { HttpError } from "@/lib/fetcher";
import { CLIENT_VERSION } from "@/lib/version";

interface Props {
  open: boolean;
  onClose: () => void;
}

const MAX_LEN = 4000;

// "Report on GitHub" fallback link — prefills the issue form with the
// same context fields so a developer-savvy reporter can submit directly
// to the public tracker without going through our API.
function buildGithubIssueUrl(opts: {
  description: string;
  url: string;
  userAgent: string;
  username: string | undefined;
}): string {
  const body =
    `**제보자**: ${opts.username ? `@${opts.username}` : "(미로그인)"}\n` +
    `**클라이언트 버전**: \`${CLIENT_VERSION}\`\n` +
    `**URL**: \`${opts.url}\`\n` +
    `**브라우저**: \`${opts.userAgent}\`\n\n` +
    `---\n\n` +
    opts.description;
  const params = new URLSearchParams({
    title: opts.description.split("\n")[0]?.slice(0, 80) ?? "버그 제보",
    body,
    labels: "bug",
  });
  return `https://github.com/jpark142/OmokGosu/issues/new?${params}`;
}

export default function BugReportDialog({ open, onClose }: Props) {
  const { user } = useAuth();
  const [description, setDescription] = useState("");
  const [anonymous, setAnonymous] = useState(false);
  const [busy, setBusy] = useState(false);

  // Reset every time the dialog opens so a previous draft doesn't linger.
  useEffect(() => {
    if (open) {
      setDescription("");
      setAnonymous(false);
      setBusy(false);
    }
  }, [open]);

  if (!open) return null;

  const trimmed = description.trim();
  const tooLong = trimmed.length > MAX_LEN;
  const canSubmit = !!user && trimmed.length > 0 && !tooLong && !busy;

  const onSubmit = async () => {
    if (!canSubmit) return;
    setBusy(true);
    try {
      const res = await submitBugReport({
        description: trimmed,
        url: window.location.pathname + window.location.search,
        user_agent: navigator.userAgent,
        anonymous,
      });
      if (res.mirrored === "github" && res.github_issue_url) {
        toast.success(
          `감사합니다. GitHub Issue #${res.github_issue_number}에 등록되었습니다.`,
          {
            action: {
              label: "보기",
              onClick: () => window.open(res.github_issue_url!, "_blank"),
            },
            duration: 8000,
          },
        );
      } else {
        toast.success("감사합니다. 제보가 접수되었습니다.");
      }
      onClose();
    } catch (e) {
      if (e instanceof HttpError && e.status === 429) {
        toast.error("제보가 너무 많습니다. 잠시 후 다시 시도하세요.");
      } else if (e instanceof HttpError && e.status === 401) {
        toast.error("로그인이 필요합니다.");
      } else {
        toast.error("제보 전송 실패. 잠시 후 다시 시도해 주세요.");
      }
    } finally {
      setBusy(false);
    }
  };

  const githubUrl = buildGithubIssueUrl({
    description: trimmed || "(여기에 내용을 적어주세요)",
    url: window.location.pathname + window.location.search,
    userAgent: navigator.userAgent,
    username: user?.username,
  });

  return (
    <div
      className="fixed inset-0 z-50 flex items-center justify-center bg-black/40 p-4"
      onClick={(e) => {
        if (e.target === e.currentTarget && !busy) onClose();
      }}
    >
      <div className="w-full max-w-lg bg-white rounded-lg shadow-xl p-6 space-y-4">
        <div className="flex items-center justify-between">
          <h2 className="text-lg font-semibold text-stone-900">버그 제보</h2>
          <button
            onClick={onClose}
            disabled={busy}
            className="text-stone-400 hover:text-stone-900 text-xl leading-none"
            aria-label="닫기"
          >
            ×
          </button>
        </div>

        <p className="text-xs text-stone-500 leading-relaxed">
          무엇이 잘못됐는지 알려주세요. 어떤 화면에서 어떤 행동을 했고 어떻게
          되었는지 적어주시면 큰 도움이 됩니다. 제보는 공개 GitHub 이슈로
          등록됩니다.
        </p>

        <div className="space-y-1">
          <div className="flex items-baseline justify-between">
            <label className="text-sm font-medium text-stone-700">내용</label>
            <span
              className={`text-[11px] tabular-nums ${
                tooLong ? "text-red-500" : "text-stone-400"
              }`}
            >
              {trimmed.length} / {MAX_LEN}
            </span>
          </div>
          <textarea
            value={description}
            onChange={(e) => setDescription(e.target.value)}
            rows={6}
            disabled={busy}
            placeholder="예) 전적보기 누르고 뒤로가니까 본인이 안 떠요"
            className="w-full px-3 py-2 border border-stone-300 rounded text-sm focus:outline-none focus:ring-2 focus:ring-amber-400 resize-y"
          />
        </div>

        <div className="rounded bg-stone-50 border border-stone-200 px-3 py-2 text-[11px] text-stone-500 leading-relaxed">
          자동 첨부: <code>v{CLIENT_VERSION}</code> · <code>{window.location.pathname}</code> ·{" "}
          {user ? <>제보자 <code>@{user.username}</code></> : "비로그인"}
        </div>

        <label className="flex items-center gap-2 text-sm text-stone-700 cursor-pointer select-none">
          <input
            type="checkbox"
            checked={anonymous}
            onChange={(e) => setAnonymous(e.target.checked)}
            disabled={busy}
            className="w-4 h-4 accent-amber-500"
          />
          익명으로 보내기
          <span className="text-[11px] text-stone-400">
            (공개 이슈에서 닉네임 숨김)
          </span>
        </label>

        <div className="flex items-center justify-between pt-2">
          <a
            href={githubUrl}
            target="_blank"
            rel="noreferrer"
            className="text-xs text-stone-500 hover:text-stone-900 underline decoration-dotted"
          >
            GitHub에서 직접 작성 →
          </a>
          <div className="flex gap-2">
            <button
              onClick={onClose}
              disabled={busy}
              className="px-3 py-2 text-sm text-stone-600 hover:text-stone-900 disabled:opacity-50"
            >
              취소
            </button>
            <button
              onClick={onSubmit}
              disabled={!canSubmit}
              className="px-4 py-2 bg-stone-900 text-white rounded text-sm font-medium hover:bg-stone-800 disabled:bg-stone-400"
            >
              {busy ? "보내는 중..." : "보내기"}
            </button>
          </div>
        </div>
      </div>
    </div>
  );
}

// /stats — operator-only usage analytics dashboard.
//
// Reads GET /api/admin/stats (operator-gated server-side) and renders DAU /
// cumulative / new-user trends plus D+1 / D+7 retention by signup cohort. The
// route is also guarded client-side: a non-operator who deep-links here is
// bounced to the lobby (the server would 403 anyway, this just avoids a flash).

import { useEffect, useState } from "react";
import { Navigate, useNavigate } from "react-router-dom";

import { http } from "@/lib/fetcher";
import { useAuth } from "@/lib/auth";
import { useIsOperator } from "@/lib/operators";

interface DailyRow {
  day: string;
  dau: number;
  new_users: number;
  cumulative_users: number;
  peak_concurrent: number;
}

interface CohortRow {
  cohort_day: string;
  size: number;
  d1_retained: number | null;
  d1_rate: number | null;
  d7_retained: number | null;
  d7_rate: number | null;
}

interface UsageStats {
  generated_at: string;
  timezone: string;
  data_since: string | null;
  today: string;
  total_users: number;
  dau_today: number;
  wau: number;
  mau: number;
  overall_d1_rate: number | null;
  overall_d7_rate: number | null;
  daily: DailyRow[];
  cohorts: CohortRow[];
}

function pct(rate: number | null): string {
  return rate === null ? "—" : `${Math.round(rate * 100)}%`;
}

function StatCard({ label, value, sub }: { label: string; value: string; sub?: string }) {
  return (
    <div className="bg-white rounded-md border border-stone-200 p-4">
      <div className="text-xs text-stone-500">{label}</div>
      <div className="text-2xl font-bold text-stone-900 tabular-nums">{value}</div>
      {sub && <div className="text-[11px] text-stone-400 mt-0.5">{sub}</div>}
    </div>
  );
}

export default function Stats() {
  const navigate = useNavigate();
  const { user } = useAuth();
  const isOperator = useIsOperator();
  const [stats, setStats] = useState<UsageStats | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let cancelled = false;
    http
      .get<UsageStats>("/api/admin/stats")
      .then((s) => {
        if (!cancelled) {
          setStats(s);
          setError(null);
        }
      })
      .catch(() => {
        if (!cancelled) setError("불러오기 실패 (운영자 전용)");
      });
    return () => {
      cancelled = true;
    };
  }, []);

  // Client-side operator guard. `useIsOperator` returns false until the list
  // loads; once it's loaded and says this user isn't an operator, bounce them
  // (the server 403s regardless — this just avoids showing the shell).
  const operatorListReady = isOperator("운영자") || isOperator(user?.username);
  if (user && operatorListReady && !isOperator(user.username)) {
    return <Navigate to="/lobby" replace />;
  }

  const maxDau = stats ? Math.max(1, ...stats.daily.map((d) => d.dau)) : 1;
  // Newest first for the tables.
  const dailyDesc = stats ? [...stats.daily].reverse() : [];
  const cohortsDesc = stats ? [...stats.cohorts].reverse() : [];

  return (
    <div className="min-h-screen p-4 md:p-6 bg-stone-50">
      <div className="max-w-4xl mx-auto space-y-5">
        <div className="flex justify-between items-center">
          <button
            onClick={() => navigate("/lobby")}
            className="text-sm text-stone-500 hover:text-stone-900"
          >
            ← 로비
          </button>
          <h1 className="text-2xl font-bold">접속 통계</h1>
          <span className="w-12" />
        </div>

        {error && (
          <div className="bg-white rounded-md border border-stone-200 p-6 text-center text-red-500 text-sm">
            {error}
          </div>
        )}
        {!error && stats === null && (
          <div className="bg-white rounded-md border border-stone-200 p-6 text-center text-stone-400 text-sm">
            불러오는 중...
          </div>
        )}

        {stats && (
          <>
            {/* Summary cards */}
            <div className="grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-6 gap-3">
              <StatCard label="누적 유저" value={String(stats.total_users)} />
              <StatCard label="오늘 DAU" value={String(stats.dau_today)} />
              <StatCard label="WAU (7일)" value={String(stats.wau)} />
              <StatCard label="MAU (30일)" value={String(stats.mau)} />
              <StatCard label="평균 D+1" value={pct(stats.overall_d1_rate)} sub="리텐션" />
              <StatCard label="평균 D+7" value={pct(stats.overall_d7_rate)} sub="리텐션" />
            </div>

            {/* Daily trend */}
            <div className="bg-white rounded-md border border-stone-200 overflow-hidden">
              <div className="px-4 py-2 text-xs font-medium text-stone-500 bg-stone-50 border-b border-stone-100">
                일별 접속 (최신순)
              </div>
              <div className="max-h-[22rem] overflow-y-auto">
                <table className="w-full text-sm">
                  <thead className="bg-white sticky top-0 text-stone-500 text-xs shadow-[0_1px_0_theme(colors.stone.100)]">
                    <tr>
                      <th className="px-4 py-2 text-left">날짜</th>
                      <th className="px-4 py-2 text-right">DAU</th>
                      <th className="px-4 py-2 text-right">신규</th>
                      <th className="px-4 py-2 text-right">누적</th>
                      <th className="px-4 py-2 text-right">동접 피크</th>
                    </tr>
                  </thead>
                  <tbody>
                    {dailyDesc.map((d) => (
                      <tr key={d.day} className="border-t border-stone-100">
                        <td className="px-4 py-1.5 text-stone-700 tabular-nums">{d.day}</td>
                        <td className="px-4 py-1.5 text-right tabular-nums">
                          <div className="flex items-center justify-end gap-2">
                            <div
                              className="h-2 bg-amber-400/70 rounded-sm"
                              style={{ width: `${(d.dau / maxDau) * 60}px` }}
                            />
                            <span className="w-8 text-right">{d.dau}</span>
                          </div>
                        </td>
                        <td className="px-4 py-1.5 text-right text-green-600 tabular-nums">
                          {d.new_users > 0 ? `+${d.new_users}` : "—"}
                        </td>
                        <td className="px-4 py-1.5 text-right text-stone-500 tabular-nums">
                          {d.cumulative_users}
                        </td>
                        <td className="px-4 py-1.5 text-right text-stone-500 tabular-nums">
                          {d.peak_concurrent}
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </div>

            {/* Retention cohorts */}
            <div className="bg-white rounded-md border border-stone-200 overflow-hidden">
              <div className="px-4 py-2 text-xs font-medium text-stone-500 bg-stone-50 border-b border-stone-100">
                리텐션 (첫 접속일 코호트별)
              </div>
              <div className="max-h-[22rem] overflow-y-auto">
                <table className="w-full text-sm">
                  <thead className="bg-white sticky top-0 text-stone-500 text-xs shadow-[0_1px_0_theme(colors.stone.100)]">
                    <tr>
                      <th className="px-4 py-2 text-left">코호트(첫 접속)</th>
                      <th className="px-4 py-2 text-right">인원</th>
                      <th className="px-4 py-2 text-right">D+1</th>
                      <th className="px-4 py-2 text-right">D+7</th>
                    </tr>
                  </thead>
                  <tbody>
                    {cohortsDesc.map((c) => (
                      <tr key={c.cohort_day} className="border-t border-stone-100">
                        <td className="px-4 py-1.5 text-stone-700 tabular-nums">{c.cohort_day}</td>
                        <td className="px-4 py-1.5 text-right tabular-nums">{c.size}</td>
                        <td className="px-4 py-1.5 text-right tabular-nums">
                          {pct(c.d1_rate)}
                          {c.d1_retained !== null && (
                            <span className="text-stone-400 text-xs"> ({c.d1_retained})</span>
                          )}
                        </td>
                        <td className="px-4 py-1.5 text-right tabular-nums">
                          {pct(c.d7_rate)}
                          {c.d7_retained !== null && (
                            <span className="text-stone-400 text-xs"> ({c.d7_retained})</span>
                          )}
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </div>

            <p className="text-xs text-stone-500 text-center leading-relaxed">
              집계 기준 {stats.timezone} · 데이터 시작 {stats.data_since ?? "—"} · 최신 {stats.today}
              <br />
              "—"는 아직 기간이 지나지 않아 측정 불가(D+7은 7일 경과 필요). 첫 접속일은 접속
              로깅 시작 이후 기준입니다.
            </p>
          </>
        )}
      </div>
    </div>
  );
}

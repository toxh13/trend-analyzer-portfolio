import React, { useMemo } from 'react';
import {
    Bar,
    BarChart,
    CartesianGrid,
    ResponsiveContainer,
    Tooltip,
    XAxis,
    YAxis,
} from 'recharts';
import { Activity, ArrowDownRight, ArrowUpRight, Minus } from 'lucide-react';

function VolatilityTooltip({ active, payload }) {
    if (!active || !payload || !payload.length) return null;

    const item = payload[0].payload;

    return (
        <div className="rounded-xl border border-slate-200 bg-white px-3 py-2 text-xs shadow-lg">
            <p className="font-semibold text-slate-900">{item.keyword}</p>
            <p className="mt-1 text-slate-500">변동성: {item.volatility}</p>
            <p className="text-slate-500">증감량: {item.velocity > 0 ? '+' : ''}{item.velocity}</p>
        </div>
    );
}

export default function VolatilityPanel({ trends = [] }) {
    const analytics = useMemo(() => {
        const rows = trends
            .map((item) => {
                // 백엔드 DTO가 camelCase 또는 snake_case로 와도 깨지지 않도록 둘 다 처리합니다.
                const velocity = Number(item.velocityScore ?? item.velocity_score ?? item.changeValue ?? 0);
                const mentionCount = Number(item.mentionCount ?? item.mention_count ?? 0);
                const score = Number(item.hotnessScore ?? item.score ?? 0);

                return {
                    keyword: item.keyword,
                    category: item.category,
                    velocity,
                    mentionCount,
                    score,
                    volatility: Math.abs(velocity),
                };
            })
            .sort((a, b) => b.volatility - a.volatility);

        const totalVolatility = rows.reduce((sum, item) => sum + item.volatility, 0);
        const averageVolatility = rows.length ? totalVolatility / rows.length : 0;
        const rising = rows.filter((item) => item.velocity > 0).length;
        const falling = rows.filter((item) => item.velocity < 0).length;
        const stable = rows.filter((item) => item.velocity === 0).length;

        return {
            rows,
            chartRows: rows.slice(0, 8),
            averageVolatility,
            rising,
            falling,
            stable,
        };
    }, [trends]);

    return (
        <section id="volatility" className="rounded-3xl border border-slate-200 bg-white p-5 shadow-sm">
            <div className="flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
                <div>
                    <p className="text-sm font-semibold text-blue-600">Volatility Analytics</p>
                    <h2 className="mt-1 text-xl font-bold text-slate-950">키워드 변동성 분석</h2>
                    <p className="mt-1 text-sm text-slate-500">
                        단순 순위보다 키워드의 상승/하락 폭을 먼저 확인할 수 있도록 구성했습니다.
                    </p>
                </div>
                <div className="flex h-12 w-12 items-center justify-center rounded-2xl bg-blue-50 text-blue-600">
                    <Activity className="h-6 w-6" />
                </div>
            </div>

            <div className="mt-5 grid gap-3 sm:grid-cols-3">
                <div className="rounded-2xl bg-slate-50 p-4">
                    <p className="text-xs font-semibold uppercase tracking-wide text-slate-400">평균 변동성</p>
                    <p className="mt-2 text-2xl font-bold text-slate-950">{analytics.averageVolatility.toFixed(1)}</p>
                    <p className="mt-1 text-xs text-slate-500">키워드별 증감 폭 평균</p>
                </div>
                <div className="rounded-2xl bg-emerald-50 p-4">
                    <div className="flex items-center gap-2 text-emerald-700">
                        <ArrowUpRight className="h-4 w-4" />
                        <p className="text-xs font-semibold uppercase tracking-wide">상승 키워드</p>
                    </div>
                    <p className="mt-2 text-2xl font-bold text-emerald-700">{analytics.rising}개</p>
                    <p className="mt-1 text-xs text-emerald-700/70">전 집계 대비 증가</p>
                </div>
                <div className="rounded-2xl bg-rose-50 p-4">
                    <div className="flex items-center gap-2 text-rose-700">
                        <ArrowDownRight className="h-4 w-4" />
                        <p className="text-xs font-semibold uppercase tracking-wide">하락 키워드</p>
                    </div>
                    <p className="mt-2 text-2xl font-bold text-rose-700">{analytics.falling}개</p>
                    <p className="mt-1 text-xs text-rose-700/70">전 집계 대비 감소</p>
                </div>
            </div>

            <div className="mt-5 h-72 rounded-2xl bg-slate-50 p-4">
                {analytics.chartRows.length === 0 ? (
                    <div className="flex h-full items-center justify-center text-sm text-slate-400">
                        변동성 데이터를 불러오는 중입니다.
                    </div>
                ) : (
                    <ResponsiveContainer width="100%" height="100%">
                        <BarChart data={analytics.chartRows} margin={{ top: 10, right: 10, left: -10, bottom: 0 }}>
                            <CartesianGrid strokeDasharray="3 3" vertical={false} stroke="#e2e8f0" />
                            <XAxis dataKey="keyword" tick={{ fontSize: 12, fill: '#64748b' }} axisLine={false} tickLine={false} />
                            <YAxis tick={{ fontSize: 12, fill: '#64748b' }} axisLine={false} tickLine={false} />
                            <Tooltip content={<VolatilityTooltip />} cursor={{ fill: 'rgba(37, 99, 235, 0.08)' }} />
                            <Bar dataKey="volatility" radius={[8, 8, 0, 0]} fill="#2563eb" />
                        </BarChart>
                    </ResponsiveContainer>
                )}
            </div>

            <div className="mt-4 flex items-center gap-2 rounded-2xl bg-slate-50 px-4 py-3 text-sm text-slate-500">
                <Minus className="h-4 w-4" />
                안정 키워드 {analytics.stable}개는 변동성이 낮아 장기 추세 확인용으로 분리해서 보면 좋습니다.
            </div>
        </section>
    );
}

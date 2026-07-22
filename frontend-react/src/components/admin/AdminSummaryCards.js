import React from 'react';
import { Activity, RefreshCw, Tags, Zap } from 'lucide-react';

function AdminMetricCard({ icon: Icon, label, value, helper }) {
    return (
        <div className="rounded-3xl border border-slate-200 bg-white p-5 shadow-sm">
            <div className="flex items-center gap-3">
                <div className="flex h-11 w-11 items-center justify-center rounded-2xl bg-blue-50 text-blue-600">
                    <Icon className="h-5 w-5" />
                </div>
                <div>
                    <p className="text-sm font-semibold text-slate-500">{label}</p>
                    <p className="text-2xl font-bold text-slate-950">{value}</p>
                </div>
            </div>
            <p className="mt-3 text-sm text-slate-500">{helper}</p>
        </div>
    );
}

export default function AdminSummaryCards({
    keywords,
    activeKeywordCount,
    stats,
    analyzing,
    onAnalyzeNow,
}) {
    return (
        <section className="grid gap-4 md:grid-cols-3">
            <AdminMetricCard
                icon={Tags}
                label="관리 키워드"
                value={`${keywords.length.toLocaleString()}개`}
                helper={`활성 ${activeKeywordCount.toLocaleString()}개`}
            />
            <AdminMetricCard
                icon={Activity}
                label="최근 분석 기사"
                value={`${(stats?.analyzedArticles ?? 0).toLocaleString()}건`}
                helper="최근 24시간 기준"
            />
            <div className="rounded-3xl border border-slate-200 bg-white p-5 shadow-sm">
                <div className="flex items-center gap-3">
                    <div className="flex h-11 w-11 items-center justify-center rounded-2xl bg-amber-50 text-amber-600">
                        <Zap className="h-5 w-5" />
                    </div>
                    <div>
                        <p className="text-sm font-semibold text-slate-500">수동 분석</p>
                        <p className="text-lg font-bold text-slate-950">관리자 실행</p>
                    </div>
                </div>
                <button
                    type="button"
                    onClick={onAnalyzeNow}
                    disabled={analyzing}
                    className="mt-4 inline-flex w-full items-center justify-center gap-2 rounded-2xl bg-slate-900 px-4 py-2 text-sm font-semibold text-white transition hover:bg-slate-700 disabled:cursor-not-allowed disabled:opacity-60"
                >
                    <RefreshCw className={`h-4 w-4 ${analyzing ? 'animate-spin' : ''}`} />
                    {analyzing ? '실행 중...' : '분석 즉시 실행'}
                </button>
            </div>
        </section>
    );
}

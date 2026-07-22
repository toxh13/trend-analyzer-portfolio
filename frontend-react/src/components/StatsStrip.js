import React from 'react';
import { Activity, BarChart3, TrendingDown, TrendingUp } from 'lucide-react';

function formatNumber(value) {
    const numericValue = Number(value ?? 0);
    return Number.isFinite(numericValue) ? numericValue.toLocaleString() : '0';
}

function formatChangeAmount(value) {
    const numericValue = Number(value ?? 0);
    if (!Number.isFinite(numericValue) || numericValue === 0) {
        return '0건';
    }
    return `${numericValue > 0 ? '+' : ''}${numericValue.toLocaleString()}건`;
}

function formatKeywordCard(keywordStat, fallbackCount) {
    if (keywordStat?.keyword) {
        return {
            value: `${keywordStat.keyword} · ${formatNumber(keywordStat.mentionCount)}건`,
            description: `24시간 변화량 ${formatChangeAmount(keywordStat.changeAmount)}`,
        };
    }

    // 신규 24시간 통계 API가 비어 있거나 장애가 난 경우 기존 개수형 fallback을 표시합니다.
    return {
        value: `${formatNumber(fallbackCount)}개`,
        description: '최근 24시간 기준 데이터 없음',
    };
}

export default function StatsStrip({ stats }) {
    if (!stats) {
        return (
            <section className="grid grid-cols-2 gap-3 lg:grid-cols-4">
                {[1, 2, 3, 4].map((item) => (
                    <div key={item} className="h-24 animate-pulse rounded-3xl border border-slate-200 bg-white" />
                ))}
            </section>
        );
    }

    const windowHours = stats.windowHours ?? 24;
    const analyzedArticles = stats.analyzedArticles ?? stats.mentions ?? 0;
    const trackedKeywords = stats.trackedKeywords ?? stats.tracked ?? 0;
    const risingDisplay = formatKeywordCard(stats.risingKeyword, stats.rising);
    const fallingDisplay = formatKeywordCard(stats.fallingKeyword, stats.falling);

    const cards = [
        {
            label: '분석 기사',
            value: `${formatNumber(analyzedArticles)}건`,
            description: `최근 ${windowHours}시간 기준`,
            icon: BarChart3,
            tone: 'bg-blue-50 text-blue-700',
        },
        {
            label: '추적 키워드',
            value: `${formatNumber(trackedKeywords)}개`,
            description: `최근 ${windowHours}시간 기준`,
            icon: Activity,
            tone: 'bg-slate-100 text-slate-700',
        },
        {
            label: '상승 키워드',
            value: risingDisplay.value,
            description: risingDisplay.description,
            icon: TrendingUp,
            tone: 'bg-emerald-50 text-emerald-700',
        },
        {
            label: '하락 키워드',
            value: fallingDisplay.value,
            description: fallingDisplay.description,
            icon: TrendingDown,
            tone: 'bg-rose-50 text-rose-700',
        },
    ];

    return (
        <section className="grid grid-cols-2 gap-3 lg:grid-cols-4">
            {cards.map((card) => {
                const Icon = card.icon;
                return (
                    <div key={card.label} className="rounded-3xl border border-slate-200 bg-white p-4 shadow-sm">
                        <div className="flex items-start justify-between gap-3">
                            <div className="min-w-0">
                                <p className="text-xs font-semibold uppercase tracking-wide text-slate-400">{card.label}</p>
                                <p className="td-data mt-2 truncate text-2xl font-bold text-slate-950" title={card.value}>
                                    {card.value}
                                </p>
                                <p className="mt-1 text-xs text-slate-500">{card.description}</p>
                            </div>
                            <div className={`flex h-10 w-10 shrink-0 items-center justify-center rounded-2xl ${card.tone}`}>
                                <Icon className="h-5 w-5" />
                            </div>
                        </div>
                    </div>
                );
            })}
        </section>
    );
}

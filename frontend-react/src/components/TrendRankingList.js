import React from 'react';
import TrendListSkeleton from './Skeletons/TrendListSkeleton';
import { RankBadge } from './UI/RankBadge';
import { CategoryBadge } from './UI/CategoryBadge';
import { ChangeBadge } from './UI/ChangeBadge';

export default function TrendRankingList({
    filteredTrends = [],
    loadingTrends = false,
    selectedId,
    onSelectKeyword,
    eyebrow = 'Keyword Signals',
    title,
    emptyMessage = '이 카테고리에는 아직 트렌드 데이터가 없습니다.',
}) {
    return (
        <section className="rounded-3xl border border-slate-200 bg-white p-5 shadow-sm">
            <div className="mb-4 flex items-center justify-between">
                <div>
                    <p className="text-sm font-semibold text-blue-600">{eyebrow}</p>
                    <h2 className="mt-1 text-xl font-bold text-slate-950">
                        {title ?? `변동성 기반 키워드 신호 · ${filteredTrends.length}개`}
                    </h2>
                </div>
            </div>

            {loadingTrends ? (
                <TrendListSkeleton />
            ) : filteredTrends.length === 0 ? (
                <div className="rounded-2xl border border-dashed border-slate-200 bg-slate-50 px-6 py-16 text-center text-sm text-slate-500">
                    {emptyMessage}
                </div>
            ) : (
                <ol className="space-y-3">
                    {filteredTrends.map((item) => {
                        const isSelected = selectedId === item.id;
                        const volatility = Math.abs(Number(item.velocityScore ?? item.velocity_score ?? item.changeValue ?? 0));
                        const mentionCount = Number(item.mentionCount ?? item.mention_count ?? 0);
                        const score = Number(item.hotnessScore ?? item.score ?? 0);

                        return (
                            <li key={item.id}>
                                <button
                                    type="button"
                                    onClick={() => onSelectKeyword?.(item)}
                                    aria-pressed={isSelected}
                                    className={`flex w-full items-center gap-4 rounded-3xl border px-4 py-4 text-left transition focus-visible:outline-none focus-visible:ring-4 focus-visible:ring-blue-100 ${
                                        isSelected
                                            ? 'border-blue-500 bg-blue-50 shadow-sm'
                                            : 'border-slate-200 bg-white hover:border-blue-200 hover:bg-slate-50'
                                    }`}
                                >
                                    <RankBadge rank={item.rank} />

                                    <div className="min-w-0 flex-1">
                                        <div className="flex flex-wrap items-center gap-2">
                                            <span className="truncate text-base font-bold text-slate-950">{item.keyword}</span>
                                            <CategoryBadge category={item.category} />
                                        </div>

                                        <div className="mt-3 grid gap-2 text-xs text-slate-500 sm:grid-cols-3">
                                            <span>언급량 {mentionCount.toLocaleString()}건</span>
                                            <span>변동성 {volatility}</span>
                                            <span>핫스코어 {score.toFixed ? score.toFixed(1) : score}</span>
                                        </div>
                                    </div>

                                    <div className="hidden shrink-0 sm:block">
                                        <ChangeBadge type={item.changeType} value={item.changeValue} />
                                    </div>
                                </button>
                            </li>
                        );
                    })}
                </ol>
            )}
        </section>
    );
}

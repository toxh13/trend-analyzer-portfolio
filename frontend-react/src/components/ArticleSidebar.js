/*
 * ArticleSidebar.js
 * 사이드바 컴포넌트: 선택된 키워드의 최근 7일 언급량 차트와 관련 기사 목록을 표시합니다.
 * Props:
 *  - selected: 선택된 키워드 데이터 (keyword, category, rank, score/hotnessScore, history)
 *  - articles: 관련 기사 배열
 *  - loadingArticles: 기사 로딩 상태 (boolean)
 *  - onClose: 사이드바 닫기 핸들러
 */

import React from 'react';
import { ExternalLink, Newspaper, X } from 'lucide-react';
import { CategoryBadge } from './UI/CategoryBadge';
import { ResponsiveContainer, AreaChart, Area, Tooltip } from 'recharts';
import ArticleListSkeleton from './Skeletons/ArticleListSkeleton';

// ChartTooltip: Recharts 툴팁 렌더러
// active/payload 유효성 검사를 통과하면 날짜(label)와 언급량(payload[0].value)을 표시
function ChartTooltip({ active, payload, label }) {
    if (!active || !payload || !payload.length) return null;
    const point = payload[0].payload ?? {};
    return (
        <div className="rounded-xl border border-slate-200 bg-white px-3 py-2 text-xs text-slate-700 shadow-lg">
            <p>{label?.slice(5).replace('-', '.') ?? label} · {Number(payload[0].value ?? 0).toLocaleString()}건</p>
            <p className="mt-1 text-slate-500">강조도 점수: {Number(point.weightedScore ?? 0).toFixed(3)}</p>
            {point.partial && <p className="mt-1 font-semibold text-amber-600">현재 시각까지의 부분 집계</p>}
        </div>
    );
}

// ArticleSidebar: 사이드바 전체 컴포넌트
// selected가 없으면 안내 UI를, 있으면 차트 + 기사 목록을 보여줌
export default function ArticleSidebar({ selected, articles, loadingArticles, onClose }) {
    return (
        <aside id="articles">
            <div className="rounded-3xl border border-slate-200 bg-white shadow-sm">
                {/* 선택된 키워드가 없을 때 보여줄 안내 */}
                {!selected ? (
                    <div className="flex flex-col items-center gap-3 px-6 py-16 text-center">
                        <div className="flex h-14 w-14 items-center justify-center rounded-3xl bg-slate-50 text-slate-400">
                            <Newspaper className="h-6 w-6" />
                        </div>
                        <p className="text-sm font-bold text-slate-800">관련 기사 보기</p>
                        <p className="text-xs leading-relaxed text-slate-500">
                            키워드를 선택하면 관련 최신 기사와 7일 언급량 추이를 보여드립니다.
                        </p>
                    </div>
                ) : (
                    <>
                        {/* 헤더: 키워드, 카테고리 배지, 랭킹/점수, 닫기 버튼 */}
                        <div className="flex items-start justify-between gap-2 border-b border-slate-100 px-5 py-4">
                            <div>
                                <div className="flex items-center gap-2">
                                    <h3 className="td-display font-bold text-slate-950">{selected.keyword}</h3>
                                    <CategoryBadge category={selected.category} />
                                </div>
                                <p className="td-data mt-1 text-xs text-slate-500">
                                    현재 {selected.rank}위 · {Number(selected.hotnessScore ?? selected.score ?? 0).toFixed(1)}점
                                </p>
                            </div>
                            <button
                                type="button"
                                onClick={onClose}
                                className="rounded-xl p-2 text-slate-400 transition hover:bg-slate-100 hover:text-slate-700 focus-visible:outline-none focus-visible:ring-4 focus-visible:ring-blue-100"
                                aria-label="닫기"
                            >
                                <X className="h-4 w-4" />
                            </button>
                        </div>

                        {/* 최근 7일 언급량 차트 영역 */}
                        <div className="px-5 pt-4">
                            <p className="text-xs font-semibold uppercase tracking-wide text-slate-400">최근 7일 언급량</p>
                            <div className="mt-2 h-24 rounded-2xl bg-slate-50 p-2">
                                <ResponsiveContainer width="100%" height="100%">
                                    <AreaChart data={selected.history ?? []} margin={{ top: 8, right: 4, bottom: 0, left: 4 }}>
                                        <defs>
                                            <linearGradient id="scoreFillLight" x1="0" y1="0" x2="0" y2="1">
                                                <stop offset="0%" stopColor="#2563eb" stopOpacity={0.28} />
                                                <stop offset="100%" stopColor="#2563eb" stopOpacity={0} />
                                            </linearGradient>
                                        </defs>
                                        <Tooltip content={<ChartTooltip />} cursor={false} />
                                        <Area type="monotone" dataKey="articleCount" stroke="#2563eb" strokeWidth={2} fill="url(#scoreFillLight)" />
                                    </AreaChart>
                                </ResponsiveContainer>
                            </div>
                        </div>

                        {/* 기사 목록: 로딩, 빈 상태, 또는 기사 목록 렌더링 */}
                        <div className="mt-4 border-t border-slate-100">
                            {loadingArticles ? (
                                <ArticleListSkeleton />
                            ) : articles.length === 0 ? (
                                <p className="px-4 py-8 text-center text-sm text-slate-500">관련 기사를 찾지 못했습니다.</p>
                            ) : (
                                <div className="max-h-96 overflow-y-auto">
                                    {articles.map((article) => {
                                        // URL / 발행일 필드의 다양한 형태를 안전하게 처리
                                        const url = article.sourceUrl ?? article.url;
                                        const publishedDate = article.publishedAt ?? article.date ?? article.published_at;

                                        return (
                                            <a
                                                key={article.id ?? url}
                                                href={url}
                                                target="_blank"
                                                rel="noreferrer"
                                                className="block border-b border-slate-100 px-5 py-4 transition last:border-b-0 hover:bg-slate-50"
                                            >
                                                {/* 기사 제목 (두 줄까지 클램프) */}
                                                <p
                                                    className="text-sm font-medium leading-snug text-slate-800 hover:text-blue-700"
                                                    style={{ display: '-webkit-box', WebkitLineClamp: 2, WebkitBoxOrient: 'vertical', overflow: 'hidden' }}
                                                >
                                                    {article.title}
                                                </p>

                                                {/* 메타 정보: 출처 · 발행일 · 외부 링크 아이콘 */}
                                                <div className="td-data mt-2 flex items-center gap-2 text-xs text-slate-400">
                                                    <span>{article.source}</span>
                                                    <span>·</span>
                                                    <span>{publishedDate}</span>
                                                    <ExternalLink className="ml-auto h-3 w-3" />
                                                </div>
                                            </a>
                                        );
                                    })}
                                </div>
                            )}
                        </div>
                    </>
                )}
            </div>
        </aside>
    );
}

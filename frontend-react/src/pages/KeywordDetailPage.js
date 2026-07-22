import React, { useEffect, useState } from 'react';
import { ExternalLink, Search } from 'lucide-react';
import { Link, useNavigate, useOutletContext, useParams } from 'react-router-dom';
import {
    Area,
    AreaChart,
    CartesianGrid,
    ResponsiveContainer,
    Tooltip,
    XAxis,
    YAxis,
} from 'recharts';

import { CategoryBadge } from '../components/UI/CategoryBadge';
import ArticleListSkeleton from '../components/Skeletons/ArticleListSkeleton';
import { useKeywordDetail } from '../hooks/useKeywordDetail';
import { findTrendByKeyword } from '../utils/trendUtils';

function KeywordHistoryTooltip({ active, payload, label }) {
    if (!active || !payload || !payload.length) return null;

    const point = payload[0].payload ?? {};

    return (
        <div className="rounded-xl border border-slate-200 bg-white px-3 py-2 text-xs text-slate-700 shadow-lg">
            <p>{label} · {Number(payload[0].value ?? 0).toLocaleString()}건</p>
            <p className="mt-1 text-slate-500">강조도 점수: {Number(point.weightedScore ?? 0).toFixed(3)}</p>
            {point.partial && <p className="mt-1 font-semibold text-amber-600">현재 시각까지의 부분 집계</p>}
        </div>
    );
}

function KeywordSearchForm({ value, onChange, onSubmit, compact = false }) {
    return (
        <form
            onSubmit={onSubmit}
            className={`flex w-full flex-col gap-3 ${compact ? 'sm:max-w-xl sm:flex-row' : 'sm:flex-row'}`}
        >
            <label className="sr-only" htmlFor={compact ? 'keyword-search-compact' : 'keyword-search'}>
                분석할 키워드
            </label>
            <div className="relative min-w-0 flex-1">
                <Search className="pointer-events-none absolute left-4 top-1/2 h-4 w-4 -translate-y-1/2 text-slate-400" />
                <input
                    id={compact ? 'keyword-search-compact' : 'keyword-search'}
                    type="search"
                    value={value}
                    onChange={(event) => onChange(event.target.value)}
                    placeholder="분석할 키워드를 입력하세요"
                    className="h-12 w-full rounded-2xl border border-slate-200 bg-white pl-11 pr-4 text-sm font-medium text-slate-900 outline-none transition placeholder:text-slate-400 focus:border-blue-400 focus:ring-4 focus:ring-blue-100"
                />
            </div>
            <button
                type="submit"
                className="inline-flex h-12 items-center justify-center rounded-2xl bg-blue-600 px-5 text-sm font-bold text-white transition hover:bg-blue-700 disabled:cursor-not-allowed disabled:bg-slate-300"
                disabled={!value.trim()}
            >
                조회
            </button>
        </form>
    );
}

export default function KeywordDetailPage() {
    const { keyword: keywordParam } = useParams();
    const keyword = decodeURIComponent(keywordParam ?? '');
    const navigate = useNavigate();
    const { allTrends = [] } = useOutletContext() ?? {};
    const [searchKeyword, setSearchKeyword] = useState(keyword);
    const {
        articles,
        history,
        loadingKeywordDetail,
    } = useKeywordDetail(keyword);

    useEffect(() => {
        setSearchKeyword(keyword);
    }, [keyword]);

    const matchedTrend = findTrendByKeyword(allTrends, keyword);
    const category = matchedTrend?.category ?? '미분류';
    const mentionCount = matchedTrend?.mentionCount ?? matchedTrend?.mention_count ?? 0;
    const hotnessScore = Number(matchedTrend?.hotnessScore ?? matchedTrend?.score ?? 0);

    const handleSearch = (event) => {
        event.preventDefault();
        const nextKeyword = searchKeyword.trim();

        if (nextKeyword) {
            navigate(`/keywords/${encodeURIComponent(nextKeyword)}`);
        }
    };

    if (!keyword) {
        return (
            <section className="space-y-6">
                <div className="rounded-3xl border border-slate-200 bg-white p-6 shadow-sm">
                    <p className="text-sm font-semibold text-blue-600">Keyword Analysis</p>
                    <h2 className="mt-1 text-2xl font-bold text-slate-950">키워드 분석</h2>
                    <p className="mt-2 max-w-3xl text-sm text-slate-500">
                        인기 키워드나 카테고리 순위에 없는 키워드도 직접 검색해서 7일 추이와 관련 기사를 확인합니다.
                    </p>
                    <div className="mt-6">
                        <KeywordSearchForm
                            value={searchKeyword}
                            onChange={setSearchKeyword}
                            onSubmit={handleSearch}
                        />
                    </div>
                </div>

                <div className="grid gap-4 md:grid-cols-3">
                    <div className="rounded-3xl border border-slate-200 bg-white p-5 shadow-sm">
                        <p className="text-sm font-bold text-slate-900">단일 키워드 조회</p>
                        <p className="mt-2 text-sm text-slate-500">원하는 키워드를 바로 검색해 상세 화면으로 이동합니다.</p>
                    </div>
                    <div className="rounded-3xl border border-slate-200 bg-white p-5 shadow-sm">
                        <p className="text-sm font-bold text-slate-900">7일 추이</p>
                        <p className="mt-2 text-sm text-slate-500">최근 흐름을 간단한 차트로 먼저 확인합니다.</p>
                    </div>
                    <div className="rounded-3xl border border-slate-200 bg-white p-5 shadow-sm">
                        <p className="text-sm font-bold text-slate-900">관련 기사</p>
                        <p className="mt-2 text-sm text-slate-500">검색한 키워드가 언급된 기사 목록을 함께 봅니다.</p>
                    </div>
                </div>
            </section>
        );
    }

    return (
        <section className="space-y-6">
            <div className="rounded-3xl border border-slate-200 bg-white p-6 shadow-sm">
                <div className="flex flex-col gap-5 lg:flex-row lg:items-start lg:justify-between">
                    <div>
                        <p className="text-sm font-semibold text-blue-600">Keyword Detail</p>
                        <div className="mt-1 flex flex-wrap items-center gap-2">
                            <h2 className="text-2xl font-bold text-slate-950">{keyword}</h2>
                            <CategoryBadge category={category} />
                        </div>
                        <p className="mt-2 text-sm text-slate-500">
                            Asia/Seoul 달력 기준 7일 고유 기사 수와 관련 기사를 확인합니다.
                        </p>
                        {matchedTrend && (
                            <p className="td-data mt-2 text-xs text-slate-400">
                                현재 {matchedTrend.rank}위 · 언급량 {Number(mentionCount).toLocaleString()}건 · 핫스코어 {hotnessScore.toFixed(1)}
                            </p>
                        )}
                    </div>

                    <div className="flex flex-wrap gap-2">
                        <Link
                            to={`/history/${encodeURIComponent(keyword)}`}
                            className="inline-flex items-center justify-center rounded-2xl border border-blue-200 bg-blue-50 px-4 py-2 text-sm font-semibold text-blue-700 transition hover:bg-blue-100"
                        >
                            비교 화면에서 보기
                        </Link>
                        <Link
                            to="/"
                            className="inline-flex items-center justify-center rounded-2xl border border-slate-200 px-4 py-2 text-sm font-semibold text-slate-600 transition hover:bg-slate-50 hover:text-blue-700"
                        >
                            인기 키워드로 돌아가기
                        </Link>
                    </div>
                </div>

                <div className="mt-6 border-t border-slate-100 pt-5">
                    <KeywordSearchForm
                        value={searchKeyword}
                        onChange={setSearchKeyword}
                        onSubmit={handleSearch}
                        compact
                    />
                </div>
            </div>

            <section className="rounded-3xl border border-slate-200 bg-white p-6 shadow-sm">
                <div className="flex flex-col gap-1 sm:flex-row sm:items-end sm:justify-between">
                    <div>
                        <p className="text-sm font-semibold text-blue-600">7 Day Trend</p>
                        <h3 className="mt-1 text-xl font-bold text-slate-950">최근 7일 고유 기사 언급량</h3>
                        <p className="mt-1 text-xs font-semibold text-amber-600">오늘은 현재 시각까지의 부분 집계입니다.</p>
                        <p className="mt-1 text-xs text-slate-400">0건은 실제 미언급과 크롤러 실패를 현재 구분하지 못합니다.</p>
                    </div>
                    <p className="text-sm text-slate-500">긴 기간 비교는 키워드 비교 화면에서 조회할 수 있습니다.</p>
                </div>

                <div className="mt-5 h-72">
                    {loadingKeywordDetail ? (
                        <div className="flex h-full items-center justify-center rounded-2xl bg-slate-50 text-sm text-slate-500">
                            추이 데이터를 불러오는 중입니다.
                        </div>
                    ) : history.length === 0 ? (
                        <div className="flex h-full items-center justify-center rounded-2xl border border-dashed border-slate-200 bg-slate-50 text-sm text-slate-500">
                            최근 7일 추이 데이터가 없습니다.
                        </div>
                    ) : (
                        <ResponsiveContainer width="100%" height="100%">
                            <AreaChart data={history} margin={{ top: 10, right: 10, bottom: 0, left: 0 }}>
                                <CartesianGrid strokeDasharray="3 3" vertical={false} stroke="#e2e8f0" />
                                <XAxis
                                    dataKey="day"
                                    tickFormatter={(day) => day?.slice(5).replace('-', '.') ?? day}
                                    tick={{ fontSize: 12, fill: '#64748b' }}
                                    axisLine={false}
                                    tickLine={false}
                                />
                                <YAxis tick={{ fontSize: 12, fill: '#64748b' }} axisLine={false} tickLine={false} />
                                <Tooltip content={<KeywordHistoryTooltip />} cursor={false} />
                                <Area type="monotone" dataKey="articleCount" stroke="#2563eb" strokeWidth={3} fill="#dbeafe" />
                            </AreaChart>
                        </ResponsiveContainer>
                    )}
                </div>
            </section>

            <section className="rounded-3xl border border-slate-200 bg-white p-6 shadow-sm">
                <div>
                    <p className="text-sm font-semibold text-blue-600">Related Articles</p>
                    <h3 className="mt-1 text-xl font-bold text-slate-950">관련 기사</h3>
                </div>

                <div className="mt-5 overflow-hidden rounded-2xl border border-slate-100">
                    {loadingKeywordDetail ? (
                        <ArticleListSkeleton />
                    ) : articles.length === 0 ? (
                        <div className="px-6 py-12 text-center text-sm text-slate-500">
                            관련 기사를 찾지 못했습니다.
                        </div>
                    ) : (
                        <div className="divide-y divide-slate-100">
                            {articles.map((article) => {
                                const url = article.sourceUrl ?? article.url;
                                const publishedDate = article.publishedAt ?? article.date ?? article.published_at;

                                return (
                                    <a
                                        key={article.id ?? url}
                                        href={url}
                                        target="_blank"
                                        rel="noreferrer"
                                        className="block px-5 py-4 transition hover:bg-slate-50"
                                    >
                                        <div className="flex items-start gap-3">
                                            <div className="min-w-0 flex-1">
                                                <p className="text-sm font-bold leading-snug text-slate-900 hover:text-blue-700">
                                                    {article.title}
                                                </p>
                                                <div className="td-data mt-2 flex flex-wrap items-center gap-2 text-xs text-slate-400">
                                                    <span>{article.source}</span>
                                                    <span>·</span>
                                                    <span>{publishedDate}</span>
                                                </div>
                                            </div>
                                            <ExternalLink className="mt-1 h-4 w-4 shrink-0 text-slate-400" />
                                        </div>
                                    </a>
                                );
                            })}
                        </div>
                    )}
                </div>
            </section>
        </section>
    );
}

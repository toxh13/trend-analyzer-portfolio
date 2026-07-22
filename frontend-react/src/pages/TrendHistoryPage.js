import React, { useCallback, useEffect, useMemo, useRef, useState } from 'react';
import { Link, useLocation, useNavigate, useParams } from 'react-router-dom';
import {
    CartesianGrid,
    Legend,
    Line,
    LineChart,
    ResponsiveContainer,
    Tooltip,
    XAxis,
    YAxis,
} from 'recharts';

import {
    fetchKeywordHistoryComparison,
    fetchKeywordHistoryEvidence,
} from '../api/trendApi';
import {
    buildComparisonInterpretation,
    buildComparisonSummary,
    normalizeHistoryRows,
} from '../utils/trendComparison';

const QUICK_DAY_OPTIONS = [2, 5, 7, 14, 30];
const DEFAULT_DAYS = '7';

function isValidDays(value) {
    const parsed = Number(value);
    return Number.isInteger(parsed) && parsed >= 2 && parsed <= 30;
}

function formatDay(day) {
    return day ? day.replaceAll('-', '.') : '-';
}

function formatPublishedAt(value, timezone) {
    if (!value) return '발행 시각 없음';
    const date = new Date(value);
    if (Number.isNaN(date.getTime())) return value;

    return new Intl.DateTimeFormat('ko-KR', {
        timeZone: timezone || 'Asia/Seoul',
        month: '2-digit',
        day: '2-digit',
        hour: '2-digit',
        minute: '2-digit',
    }).format(date);
}

function HistoryTooltip({ active, payload, label }) {
    if (!active || !payload || !payload.length) return null;

    return (
        <div className="rounded-xl border border-slate-200 bg-white px-3 py-2 text-xs text-slate-700 shadow-lg">
            <p className="mb-1 font-bold text-slate-900">{label}</p>
            {payload.map((item) => (
                <p key={item.dataKey} className="mb-1 last:mb-0" style={{ color: item.color }}>
                    {item.name}: {Number(item.value ?? 0).toLocaleString()}건
                    {item.payload?.partial ? ' · 부분 집계' : ''}
                </p>
            ))}
        </div>
    );
}

function ChangeText({ change }) {
    if (!change) return <span className="text-slate-400">비교할 완료일 부족</span>;
    if (change.value === 0) return <span className="text-slate-500">최근 완료일 변화 없음</span>;

    return (
        <span className={change.value > 0 ? 'text-rose-600' : 'text-blue-600'}>
            최근 완료일 {change.value > 0 ? '+' : ''}{change.value.toLocaleString()}건
        </span>
    );
}

function KeywordSummaryCard({ keyword, colorClass, summary }) {
    return (
        <article className="rounded-2xl border border-slate-200 bg-white p-4">
            <p className={`text-sm font-bold ${colorClass}`}>{keyword}</p>
            <p className="mt-2 text-2xl font-black text-slate-950">누적 {summary.total.toLocaleString()}건</p>
            <dl className="mt-3 grid grid-cols-2 gap-3 text-xs">
                <div>
                    <dt className="text-slate-400">최고 언급일</dt>
                    <dd className="mt-1 font-bold text-slate-700">
                        {summary.peakDay
                            ? `${formatDay(summary.peakDay)} · ${summary.peakCount.toLocaleString()}건${summary.peakDays.length > 1 ? ` 외 ${summary.peakDays.length - 1}일` : ''}`
                            : '데이터 없음'}
                    </dd>
                </div>
                <div>
                    <dt className="text-slate-400">우세 날짜</dt>
                    <dd className="mt-1 font-bold text-slate-700">{summary.leadingDays}일</dd>
                </div>
            </dl>
            <p className="mt-3 text-xs font-semibold"><ChangeText change={summary.recentCompletedChange} /></p>
        </article>
    );
}

function ArticleList({ keyword, articles, timezone }) {
    return (
        <section className="rounded-2xl border border-slate-200 bg-white p-4">
            <h4 className="font-bold text-slate-900">{keyword} 관련 기사</h4>
            {articles.length === 0 ? (
                <p className="mt-4 rounded-xl bg-slate-50 px-3 py-6 text-center text-sm text-slate-500">
                    {keyword} 관련 기사가 없습니다.
                </p>
            ) : (
                <div className="mt-3 space-y-3">
                    {articles.map((article) => (
                        <article key={article.id ?? article.sourceUrl} className="rounded-xl bg-slate-50 p-3">
                            <a
                                href={article.sourceUrl}
                                target="_blank"
                                rel="noreferrer"
                                className="font-bold text-slate-900 transition hover:text-blue-700"
                            >
                                {article.title}
                            </a>
                            <p className="mt-1 text-xs text-slate-400">
                                {article.source || '출처 미상'} · {formatPublishedAt(article.publishedAt, timezone)}
                            </p>
                            {article.summary && <p className="mt-2 text-sm leading-6 text-slate-600">{article.summary}</p>}
                        </article>
                    ))}
                </div>
            )}
        </section>
    );
}

function EvidencePanel({ query, selectedDate, evidence, loading, error }) {
    if (!selectedDate) {
        return (
            <div className="rounded-2xl border border-dashed border-slate-200 bg-slate-50 px-4 py-8 text-center text-sm text-slate-500">
                그래프의 날짜를 선택하면 해당 날짜의 근거 기사를 확인할 수 있습니다.
            </div>
        );
    }

    if (loading) {
        return <div className="rounded-2xl bg-slate-50 px-4 py-8 text-center text-sm text-slate-500">근거 기사를 불러오는 중입니다.</div>;
    }

    if (error) {
        return <div className="rounded-2xl bg-rose-50 px-4 py-4 text-sm font-semibold text-rose-700">{error}</div>;
    }

    if (!evidence) return null;

    const firstKeyword = evidence.firstCanonicalKeyword ?? query.firstKeyword;
    const secondKeyword = evidence.secondCanonicalKeyword ?? query.secondKeyword;
    return (
        <div className="grid gap-4 lg:grid-cols-2">
            <ArticleList keyword={firstKeyword} articles={evidence.firstArticles ?? []} timezone={evidence.timezone} />
            <ArticleList keyword={secondKeyword} articles={evidence.secondArticles ?? []} timezone={evidence.timezone} />
        </div>
    );
}

export default function TrendHistoryPage() {
    const navigate = useNavigate();
    const location = useLocation();
    const { keyword: keywordParam } = useParams();
    const [initialParams] = useState(() => new URLSearchParams(location.search));
    const initialKeyword = initialParams.get('first')
        ?? (keywordParam ? decodeURIComponent(keywordParam) : '');
    const [firstKeyword, setFirstKeyword] = useState(initialKeyword);
    const [secondKeyword, setSecondKeyword] = useState(initialParams.get('second') ?? '');
    const [days, setDays] = useState(initialParams.get('days') ?? DEFAULT_DAYS);
    const [submittedQuery, setSubmittedQuery] = useState(null);
    const [firstHistory, setFirstHistory] = useState([]);
    const [secondHistory, setSecondHistory] = useState([]);
    const [loading, setLoading] = useState(false);
    const [errorMessage, setErrorMessage] = useState('');
    const [selectedDate, setSelectedDate] = useState(null);
    const [evidence, setEvidence] = useState(null);
    const [evidenceLoading, setEvidenceLoading] = useState(false);
    const [evidenceError, setEvidenceError] = useState('');
    const initialQueryHandled = useRef(false);
    const comparisonRequestId = useRef(0);
    const evidenceRequestId = useRef(0);

    const resetEvidence = useCallback(() => {
        evidenceRequestId.current += 1;
        setSelectedDate(null);
        setEvidence(null);
        setEvidenceError('');
        setEvidenceLoading(false);
    }, []);

    const loadComparison = useCallback(async (requestedFirst, requestedSecond, requestedDays, updateUrl) => {
        const requestId = comparisonRequestId.current + 1;
        comparisonRequestId.current = requestId;
        const normalizedFirst = requestedFirst.trim();
        const normalizedSecond = requestedSecond.trim();

        if (!normalizedFirst || !normalizedSecond) {
            setLoading(false);
            setErrorMessage('비교할 키워드 2개를 모두 입력해주세요.');
            return false;
        }
        if (!isValidDays(requestedDays)) {
            setLoading(false);
            setErrorMessage('조회 기간은 2일에서 30일 사이여야 합니다.');
            return false;
        }

        setLoading(true);
        setErrorMessage('');
        setSubmittedQuery(null);
        setFirstHistory([]);
        setSecondHistory([]);
        resetEvidence();

        try {
            const parsedDays = Number(requestedDays);
            const result = await fetchKeywordHistoryComparison(normalizedFirst, normalizedSecond, parsedDays);
            if (requestId !== comparisonRequestId.current) return false;
            const confirmedQuery = {
                firstKeyword: result.firstCanonicalKeyword ?? normalizedFirst,
                secondKeyword: result.secondCanonicalKeyword ?? normalizedSecond,
                days: result.days ?? parsedDays,
                timezone: result.timezone ?? 'Asia/Seoul',
                todayPartial: Boolean(result.todayPartial),
            };

            setFirstHistory(result.firstHistory ?? []);
            setSecondHistory(result.secondHistory ?? []);
            setSubmittedQuery(confirmedQuery);

            if (updateUrl) {
                const params = new URLSearchParams({
                    first: confirmedQuery.firstKeyword,
                    second: confirmedQuery.secondKeyword,
                    days: String(confirmedQuery.days),
                });
                navigate({ pathname: '/history', search: params.toString() }, { replace: true });
            }
            return true;
        } catch (error) {
            if (requestId !== comparisonRequestId.current) return false;
            console.error('키워드 비교 조회 실패:', error);
            setFirstHistory([]);
            setSecondHistory([]);
            setSubmittedQuery(null);
            setErrorMessage(
                error.response?.data?.detail
                ?? error.response?.data?.message
                ?? '키워드 비교 데이터를 불러오지 못했습니다.'
            );
            return false;
        } finally {
            if (requestId === comparisonRequestId.current) setLoading(false);
        }
    }, [navigate, resetEvidence]);

    useEffect(() => {
        if (initialQueryHandled.current) return;
        initialQueryHandled.current = true;

        const sharedFirst = initialParams.get('first');
        const sharedSecond = initialParams.get('second');
        const sharedDays = initialParams.get('days') ?? DEFAULT_DAYS;
        if (sharedFirst && sharedSecond) {
            loadComparison(sharedFirst, sharedSecond, sharedDays, false);
        }
    }, [initialParams, loadComparison]);

    const chartRows = useMemo(() => {
        if (!submittedQuery) return [];
        return normalizeHistoryRows(
            submittedQuery.firstKeyword,
            firstHistory,
            submittedQuery.secondKeyword,
            secondHistory
        );
    }, [firstHistory, secondHistory, submittedQuery]);

    const summary = useMemo(() => {
        if (!submittedQuery) return null;
        return buildComparisonSummary(chartRows, submittedQuery.firstKeyword, submittedQuery.secondKeyword);
    }, [chartRows, submittedQuery]);

    const interpretation = useMemo(() => {
        if (!submittedQuery || !summary) return '';
        return buildComparisonInterpretation(
            summary,
            submittedQuery.firstKeyword,
            submittedQuery.secondKeyword,
            submittedQuery.days,
            submittedQuery.todayPartial
        );
    }, [submittedQuery, summary]);

    const handleSubmit = (event) => {
        event.preventDefault();
        loadComparison(firstKeyword, secondKeyword, days, true);
    };

    const handleInputChange = (setter) => (event) => {
        comparisonRequestId.current += 1;
        setLoading(false);
        setter(event.target.value);
        resetEvidence();
    };

    const handleQuickDays = (option) => {
        comparisonRequestId.current += 1;
        setLoading(false);
        setDays(String(option));
        resetEvidence();
    };

    const handleOpenDetail = (keyword) => {
        const normalizedKeyword = keyword.trim();
        if (normalizedKeyword) navigate(`/keywords/${encodeURIComponent(normalizedKeyword)}`);
    };

    const handleSelectDate = useCallback(async (rawDay) => {
        if (!submittedQuery || !rawDay) return;

        const requestId = evidenceRequestId.current + 1;
        evidenceRequestId.current = requestId;
        setSelectedDate(rawDay);
        setEvidence(null);
        setEvidenceError('');
        setEvidenceLoading(true);
        try {
            const result = await fetchKeywordHistoryEvidence(
                submittedQuery.firstKeyword,
                submittedQuery.secondKeyword,
                rawDay,
                5
            );
            if (requestId !== evidenceRequestId.current) return;
            setEvidence(result);
        } catch (error) {
            if (requestId !== evidenceRequestId.current) return;
            console.error('근거 기사 조회 실패:', error);
            setEvidenceError(
                error.response?.data?.detail
                ?? error.response?.data?.message
                ?? '선택한 날짜의 근거 기사를 불러오지 못했습니다.'
            );
        } finally {
            if (requestId === evidenceRequestId.current) setEvidenceLoading(false);
        }
    }, [submittedQuery]);

    const handleChartClick = (chartState) => {
        const rawDay = chartState?.activePayload?.[0]?.payload?.rawDay;
        if (rawDay) handleSelectDate(rawDay);
    };

    const renderDot = useCallback((keyword, color, peakDays) => (props) => {
        const { cx, cy, payload } = props;
        const isPeak = peakDays.includes(payload.rawDay);
        const isSelected = payload.rawDay === selectedDate;
        const radius = isSelected ? 7 : isPeak ? 6 : 3;
        return (
            <g
                role="button"
                aria-label={`${keyword} ${payload.rawDay} ${isPeak ? '최고점' : '데이터'}${payload.partial ? ' 부분 집계' : ''}`}
                tabIndex="0"
                onClick={(event) => {
                    event.stopPropagation();
                    handleSelectDate(payload.rawDay);
                }}
                onKeyDown={(event) => {
                    if (event.key === 'Enter' || event.key === ' ') handleSelectDate(payload.rawDay);
                }}
                className="cursor-pointer"
            >
                <circle
                    cx={cx}
                    cy={cy}
                    r={radius}
                    fill={payload.partial ? '#f59e0b' : color}
                    stroke={isSelected ? '#0f172a' : '#ffffff'}
                    strokeWidth={isSelected ? 3 : 1.5}
                />
            </g>
        );
    }, [handleSelectDate, selectedDate]);

    return (
        <section className="space-y-6">
            <div className="rounded-3xl border border-slate-200 bg-white p-6 shadow-sm">
                <p className="text-sm font-semibold text-blue-600">Keyword Compare</p>
                <h2 className="mt-1 text-2xl font-bold text-slate-950">키워드 비교</h2>
                <p className="mt-2 text-sm text-slate-500">
                    두 키워드의 언급량 차이를 요약과 그래프로 확인하고, 날짜별 실제 기사까지 내려가 근거를 살펴봅니다.
                </p>
            </div>

            <form onSubmit={handleSubmit} className="rounded-3xl border border-slate-200 bg-white p-5 shadow-sm">
                <div className="grid gap-4 lg:grid-cols-[minmax(0,1fr)_minmax(0,1fr)_220px]">
                    <label className="block text-sm font-semibold text-slate-700">
                        첫 번째 키워드
                        <div className="mt-2 flex gap-2">
                            <input
                                value={firstKeyword}
                                onChange={handleInputChange(setFirstKeyword)}
                                placeholder="예: 인공지능"
                                className="min-w-0 flex-1 rounded-2xl border border-slate-200 px-4 py-2 text-sm outline-none transition focus:border-blue-400 focus:ring-4 focus:ring-blue-50"
                            />
                            <button type="button" onClick={() => handleOpenDetail(firstKeyword)} className="rounded-2xl border border-slate-200 px-3 py-2 text-xs font-bold text-slate-600 transition hover:bg-slate-50 hover:text-blue-700">상세</button>
                        </div>
                    </label>

                    <label className="block text-sm font-semibold text-slate-700">
                        두 번째 키워드
                        <div className="mt-2 flex gap-2">
                            <input
                                value={secondKeyword}
                                onChange={handleInputChange(setSecondKeyword)}
                                placeholder="예: 반도체"
                                className="min-w-0 flex-1 rounded-2xl border border-slate-200 px-4 py-2 text-sm outline-none transition focus:border-blue-400 focus:ring-4 focus:ring-blue-50"
                            />
                            <button type="button" onClick={() => handleOpenDetail(secondKeyword)} className="rounded-2xl border border-slate-200 px-3 py-2 text-xs font-bold text-slate-600 transition hover:bg-slate-50 hover:text-blue-700">상세</button>
                        </div>
                    </label>

                    <label className="block text-sm font-semibold text-slate-700">
                        조회 기간
                        <input
                            type="number"
                            min="2"
                            max="30"
                            value={days}
                            onChange={handleInputChange(setDays)}
                            className="mt-2 w-full rounded-2xl border border-slate-200 px-4 py-2 text-sm outline-none transition focus:border-blue-400 focus:ring-4 focus:ring-blue-50"
                        />
                    </label>
                </div>

                <div className="mt-4 flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
                    <div className="flex flex-wrap gap-2">
                        {QUICK_DAY_OPTIONS.map((option) => (
                            <button
                                key={option}
                                type="button"
                                onClick={() => handleQuickDays(option)}
                                className={`rounded-2xl px-3 py-2 text-xs font-bold transition ${
                                    Number(days) === option
                                        ? 'bg-blue-600 text-white'
                                        : 'bg-slate-100 text-slate-600 hover:bg-blue-50 hover:text-blue-700'
                                }`}
                            >
                                {option}일
                            </button>
                        ))}
                    </div>
                    <button type="submit" disabled={loading} className="rounded-2xl bg-blue-600 px-5 py-2 text-sm font-bold text-white transition hover:bg-blue-700 disabled:cursor-not-allowed disabled:opacity-60">
                        {loading ? '조회 중...' : '비교 조회'}
                    </button>
                </div>

                {errorMessage && <div className="mt-4 rounded-2xl bg-rose-50 px-4 py-3 text-sm font-semibold text-rose-700">{errorMessage}</div>}
            </form>

            <section className="rounded-3xl border border-slate-200 bg-white p-6 shadow-sm">
                <div className="flex flex-col gap-2 sm:flex-row sm:items-center sm:justify-between">
                    <div>
                        <p className="text-sm font-semibold text-blue-600">Comparison Summary</p>
                        <h3 className="mt-1 text-xl font-bold text-slate-950">
                            {submittedQuery ? `${submittedQuery.firstKeyword} vs ${submittedQuery.secondKeyword}` : '키워드 추이 비교'}
                        </h3>
                        <p className="mt-1 text-sm text-slate-500">
                            {submittedQuery
                                ? `${submittedQuery.timezone} 달력 기준 최근 ${submittedQuery.days}일의 고유 기사 수입니다.`
                                : '키워드 2개와 기간을 입력한 뒤 비교 조회를 실행해주세요.'}
                        </p>
                    </div>
                    {submittedQuery && (
                        <div className="flex gap-2">
                            <Link to={`/keywords/${encodeURIComponent(submittedQuery.firstKeyword)}`} className="rounded-2xl border border-slate-200 px-3 py-2 text-xs font-bold text-slate-600 hover:text-blue-700">{submittedQuery.firstKeyword} 상세</Link>
                            <Link to={`/keywords/${encodeURIComponent(submittedQuery.secondKeyword)}`} className="rounded-2xl border border-slate-200 px-3 py-2 text-xs font-bold text-slate-600 hover:text-blue-700">{submittedQuery.secondKeyword} 상세</Link>
                        </div>
                    )}
                </div>

                {summary && submittedQuery && (
                    <>
                        <div className="mt-5 grid gap-3 md:grid-cols-3">
                            <KeywordSummaryCard keyword={submittedQuery.firstKeyword} colorClass="text-blue-600" summary={summary.first} />
                            <KeywordSummaryCard keyword={submittedQuery.secondKeyword} colorClass="text-emerald-600" summary={summary.second} />
                            <article className="rounded-2xl border border-slate-200 bg-slate-50 p-4">
                                <p className="text-sm font-bold text-slate-600">비교 결과</p>
                                <p className="mt-2 text-2xl font-black text-slate-950">차이 {Math.abs(summary.difference).toLocaleString()}건</p>
                                <p className="mt-3 text-xs font-semibold text-slate-600">동률 {summary.tieDays}일</p>
                            </article>
                        </div>
                        <p className="mt-4 rounded-2xl bg-blue-50 px-4 py-3 text-sm leading-6 text-blue-950">{interpretation}</p>
                        <p className="mt-2 text-xs text-slate-400">0건은 실제 미언급과 수집 실패를 현재 구분하지 못합니다.</p>
                    </>
                )}

                <div className="mt-5 h-[420px]">
                    {loading ? (
                        <div className="flex h-full items-center justify-center rounded-2xl bg-slate-50 text-sm text-slate-500">비교 데이터를 불러오는 중입니다.</div>
                    ) : chartRows.length === 0 ? (
                        <div className="flex h-full items-center justify-center rounded-2xl border border-dashed border-slate-200 bg-slate-50 text-sm text-slate-500">아직 조회된 비교 데이터가 없습니다.</div>
                    ) : (
                        <ResponsiveContainer width="100%" height="100%">
                            <LineChart data={chartRows} margin={{ top: 20, right: 20, bottom: 0, left: 0 }} onClick={handleChartClick}>
                                <CartesianGrid strokeDasharray="3 3" vertical={false} stroke="#e2e8f0" />
                                <XAxis dataKey="day" tick={{ fontSize: 12, fill: '#64748b' }} axisLine={false} tickLine={false} />
                                <YAxis tick={{ fontSize: 12, fill: '#64748b' }} axisLine={false} tickLine={false} allowDecimals={false} />
                                <Tooltip content={<HistoryTooltip />} cursor={{ stroke: '#cbd5e1', strokeWidth: 1 }} />
                                <Legend />
                                <Line type="monotone" dataKey={submittedQuery.firstKeyword} name={submittedQuery.firstKeyword} stroke="#2563eb" strokeWidth={3} dot={renderDot(submittedQuery.firstKeyword, '#2563eb', summary.first.peakDays)} activeDot={{ r: 7 }} />
                                <Line type="monotone" dataKey={submittedQuery.secondKeyword} name={submittedQuery.secondKeyword} stroke="#059669" strokeWidth={3} dot={renderDot(submittedQuery.secondKeyword, '#059669', summary.second.peakDays)} activeDot={{ r: 7 }} />
                            </LineChart>
                        </ResponsiveContainer>
                    )}
                </div>

                {chartRows.length > 0 && (
                    <>
                        <div className="mt-2 flex flex-wrap gap-3 text-xs text-slate-500">
                            <span><span className="mr-1 inline-block h-2.5 w-2.5 rounded-full bg-slate-900" />선택 날짜</span>
                            <span><span className="mr-1 inline-block h-2.5 w-2.5 rounded-full bg-amber-500" />오늘 부분 집계</span>
                            <span>큰 점은 키워드별 최고 언급일</span>
                        </div>
                        <details className="mt-5 rounded-2xl border border-slate-200">
                            <summary className="cursor-pointer px-4 py-3 text-sm font-bold text-slate-700">날짜별 정확한 수치 보기</summary>
                            <div className="overflow-x-auto border-t border-slate-200">
                                <table className="min-w-full text-left text-sm">
                                    <thead className="bg-slate-50 text-xs text-slate-500">
                                        <tr><th className="px-4 py-3">날짜</th><th className="px-4 py-3">{submittedQuery.firstKeyword}</th><th className="px-4 py-3">{submittedQuery.secondKeyword}</th><th className="px-4 py-3">상태</th></tr>
                                    </thead>
                                    <tbody>
                                        {chartRows.map((row) => (
                                            <tr key={row.rawDay} className={selectedDate === row.rawDay ? 'bg-blue-50' : 'border-t border-slate-100'}>
                                                <td className="px-4 py-3"><button type="button" className="font-bold text-blue-700 hover:underline" onClick={() => handleSelectDate(row.rawDay)}>{row.rawDay}</button></td>
                                                <td className="px-4 py-3">{row[submittedQuery.firstKeyword].toLocaleString()}건</td>
                                                <td className="px-4 py-3">{row[submittedQuery.secondKeyword].toLocaleString()}건</td>
                                                <td className="px-4 py-3">{row.partial ? <span className="rounded-full bg-amber-100 px-2 py-1 text-xs font-bold text-amber-700">부분 집계</span> : '완료'}</td>
                                            </tr>
                                        ))}
                                    </tbody>
                                </table>
                            </div>
                        </details>
                    </>
                )}
            </section>

            {submittedQuery && (
                <section className="rounded-3xl border border-slate-200 bg-white p-6 shadow-sm">
                    <p className="text-sm font-semibold text-blue-600">Article Evidence</p>
                    <h3 className="mt-1 text-xl font-bold text-slate-950">{selectedDate ? `${selectedDate} 관련 기사` : '날짜별 관련 기사'}</h3>
                    <div className="mt-4">
                        <EvidencePanel query={submittedQuery} selectedDate={selectedDate} evidence={evidence} loading={evidenceLoading} error={evidenceError} />
                    </div>
                </section>
            )}
        </section>
    );
}

import React, { useCallback, useEffect, useState } from 'react';
import { useOutletContext } from 'react-router-dom';

import { fetchRecentRuns, fetchSiteMeta } from '../api/staticTrendApi';
import { formatCrawlRunTime, StatusBadge } from '../components/admin/AdminCrawlRunsTab';
import { describeFreshness, formatSeoulLocal, FRESHNESS_PRESENTATION } from '../utils/freshness';

const TRIGGER_LABELS = {
    schedule: '정기 실행',
    workflow_dispatch: '수동 실행',
    backfill: '백필',
    local: '로컬',
};

function formatCount(value) {
    return Number(value ?? 0).toLocaleString('ko-KR');
}

function formatDuration(durationMs) {
    const seconds = Math.round(Number(durationMs ?? 0) / 1000);
    if (!Number.isFinite(seconds) || seconds <= 0) return '-';
    if (seconds < 60) return `${seconds}초`;
    return `${Math.floor(seconds / 60)}분 ${seconds % 60}초`;
}

function SummaryCard({ label, value, description }) {
    return (
        <div className="rounded-3xl border border-slate-200 bg-white p-5 shadow-sm">
            <p className="text-xs font-semibold uppercase tracking-wide text-slate-400">{label}</p>
            <div className="mt-2 text-xl font-bold text-slate-950">{value}</div>
            {description && <p className="mt-1 text-xs text-slate-500">{description}</p>}
        </div>
    );
}

// v2 static 모드 전용 읽기 전용 운영 현황 화면입니다.
// v1 관리자 화면의 "수집 실행 이력"을 로그인 없이 공개하되, 수정·재실행 기능은 없습니다.
export default function OperationsStatusPage() {
    const { registerPageRefresh } = useOutletContext() ?? {};
    const [meta, setMeta] = useState(null);
    const [runs, setRuns] = useState([]);
    const [loading, setLoading] = useState(true);
    const [errorMessage, setErrorMessage] = useState('');

    const loadStatus = useCallback(() => (
        Promise.all([fetchSiteMeta(), fetchRecentRuns()])
            .then(([metaResult, runResult]) => {
                setMeta(metaResult);
                setRuns(runResult);
                setErrorMessage('');
            })
            .catch((error) => {
                console.error('운영 현황 조회 실패:', error);
                setErrorMessage('운영 현황 데이터를 불러오지 못했습니다.');
                throw error;
            })
            .finally(() => setLoading(false))
    ), []);

    useEffect(() => {
        if (registerPageRefresh) {
            return registerPageRefresh(loadStatus);
        }
        loadStatus().catch(() => {});
        return undefined;
    }, [loadStatus, registerPageRefresh]);

    const freshness = FRESHNESS_PRESENTATION[meta?.freshness] ?? null;

    return (
        <section className="space-y-6">
            <div className="rounded-3xl border border-slate-200 bg-white p-6 shadow-sm">
                <p className="text-sm font-semibold text-blue-600">Pipeline Status</p>
                <h2 className="mt-1 text-2xl font-bold text-slate-950">운영 현황</h2>
                <p className="mt-2 max-w-3xl text-sm text-slate-500">
                    GitHub Actions가 3시간마다 뉴스를 수집하고, 집계 결과를 정적 파일로 배포합니다.
                    이 화면은 배포본의 기준 시각과 최근 수집 실행 기록을 보여 줍니다.
                </p>
            </div>

            {errorMessage && (
                <div role="alert" className="rounded-2xl border border-rose-200 bg-rose-50 px-4 py-3 text-sm text-rose-700">
                    {errorMessage}
                </div>
            )}

            {loading && !meta ? (
                <div className="rounded-3xl border border-slate-200 bg-white p-6 text-sm text-slate-500 shadow-sm">
                    운영 현황을 불러오는 중입니다.
                </div>
            ) : meta && (
                <div className="grid gap-4 md:grid-cols-2 xl:grid-cols-4">
                    <SummaryCard
                        label="데이터 신선도"
                        value={freshness ? (
                            <span className={`inline-flex rounded-full border px-3 py-1 text-sm ${freshness.className}`}>
                                {freshness.label}
                            </span>
                        ) : meta.freshness}
                        description={describeFreshness(meta)}
                    />
                    <SummaryCard
                        label="지표 기준 시각"
                        value={formatSeoulLocal(meta.asOf)}
                        description={`서울 기준 · 배포 ${formatCrawlRunTime(meta.generatedAt)}`}
                    />
                    <SummaryCard
                        label="마지막 성공 수집"
                        value={formatCrawlRunTime(meta.lastSuccessfulRunAt)}
                        description={meta.lastRun ? `마지막 실행 결과: ${meta.lastRun.outcome}` : '실행 기록 없음'}
                    />
                    <SummaryCard
                        label="최근 30일 데이터"
                        value={`기사 ${formatCount(meta.counts?.articles30d)} · 키워드 ${formatCount(meta.counts?.keywords30d)}`}
                        description={`최근 7일 수집 실행 ${formatCount(meta.counts?.runs7d)}회 · 코드 ${meta.codeVersion}`}
                    />
                </div>
            )}

            <section className="rounded-3xl border border-slate-200 bg-white p-6 shadow-sm">
                <div>
                    <p className="text-sm font-semibold text-blue-600">Recent Runs</p>
                    <h3 className="mt-1 text-xl font-bold text-slate-950">최근 수집 실행</h3>
                    <p className="mt-1 text-sm text-slate-500">
                        최근 50회까지 표시합니다. 일부 채널만 실패한 실행(일부 수집 단계 실패)도 신선도 계산에서는 성공으로 봅니다.
                    </p>
                </div>

                {runs.length === 0 && !loading ? (
                    <div className="mt-5 rounded-2xl border border-dashed border-slate-200 px-6 py-10 text-center text-sm text-slate-500">
                        수집 실행 기록이 없습니다.
                    </div>
                ) : (
                    <div className="mt-5 overflow-x-auto">
                        <table className="min-w-full text-left text-sm">
                            <thead className="whitespace-nowrap border-b border-slate-200 text-xs uppercase text-slate-400">
                                <tr>
                                    <th className="px-3 py-2 font-semibold">시작 (서울)</th>
                                    <th className="px-3 py-2 font-semibold">결과</th>
                                    <th className="px-3 py-2 font-semibold">실행 방식</th>
                                    <th className="px-3 py-2 text-right font-semibold">선택</th>
                                    <th className="px-3 py-2 text-right font-semibold">저장</th>
                                    <th className="px-3 py-2 text-right font-semibold">이미 수집</th>
                                    <th className="px-3 py-2 text-right font-semibold">검증 탈락</th>
                                    <th className="px-3 py-2 font-semibold">대사</th>
                                    <th className="px-3 py-2 font-semibold">채널</th>
                                    <th className="px-3 py-2 text-right font-semibold">소요</th>
                                </tr>
                            </thead>
                            <tbody className="divide-y divide-slate-100">
                                {runs.map((run) => (
                                    <tr key={run.runId} className="align-top">
                                        <td className="td-data whitespace-nowrap px-3 py-3 text-slate-700">{formatCrawlRunTime(run.startedAt)}</td>
                                        <td className="px-3 py-3"><StatusBadge outcome={run.outcome} /></td>
                                        <td className="whitespace-nowrap px-3 py-3 text-slate-600">{TRIGGER_LABELS[run.trigger] ?? run.trigger}</td>
                                        <td className="td-data px-3 py-3 text-right">{formatCount(run.selectedCount)}</td>
                                        <td className="td-data px-3 py-3 text-right font-semibold">{formatCount(run.writtenCount)}</td>
                                        <td className="td-data px-3 py-3 text-right">{formatCount(run.previouslySeenCount)}</td>
                                        <td className="td-data px-3 py-3 text-right">{formatCount(run.validationRejectedCount)}</td>
                                        <td className="whitespace-nowrap px-3 py-3">
                                            {run.reconciliationOk
                                                ? <span className="text-emerald-700">일치</span>
                                                : <span className="font-semibold text-rose-700">불일치</span>}
                                        </td>
                                        <td className="px-3 py-3">
                                            <div className="flex flex-wrap gap-1">
                                                {(run.channels ?? []).map((channel) => (
                                                    <span
                                                        key={channel.channel}
                                                        title={`${channel.channel}: ${channel.outcome}, 검증 통과 ${formatCount(channel.validatedArticleCount)}건`}
                                                        className={`rounded-full px-2 py-0.5 text-xs font-semibold ${
                                                            channel.outcome === 'FAILURE'
                                                                ? 'bg-rose-50 text-rose-700'
                                                                : channel.outcome === 'EMPTY'
                                                                    ? 'bg-slate-100 text-slate-500'
                                                                    : 'bg-emerald-50 text-emerald-700'
                                                        }`}
                                                    >
                                                        {channel.channel} {formatCount(channel.validatedArticleCount)}
                                                    </span>
                                                ))}
                                            </div>
                                        </td>
                                        <td className="td-data whitespace-nowrap px-3 py-3 text-right text-slate-500">{formatDuration(run.durationMs)}</td>
                                    </tr>
                                ))}
                            </tbody>
                        </table>
                    </div>
                )}
            </section>
        </section>
    );
}

import React from 'react';
import { RefreshCw } from 'lucide-react';

const STATUS_PRESENTATION = {
    RUNNING: { label: '실행 중', className: 'bg-blue-50 text-blue-700' },
    SUCCESS: { label: '정상 완료', className: 'bg-emerald-50 text-emerald-700' },
    EMPTY: { label: '정상 완료 · 수집 결과 없음', className: 'bg-slate-100 text-slate-600' },
    PARTIAL_FAILURE: { label: '일부 수집 단계 실패', className: 'bg-amber-50 text-amber-700' },
    FAILURE: { label: '배치 실패', className: 'bg-rose-50 text-rose-700' },
};

export function StatusBadge({ outcome }) {
    const presentation = STATUS_PRESENTATION[outcome] || {
        label: outcome || '상태 미확인',
        className: 'bg-slate-100 text-slate-600',
    };
    return <span className={`inline-flex rounded-full px-2.5 py-1 text-xs font-bold ${presentation.className}`}>{presentation.label}</span>;
}

function formatCount(value) {
    return Number(value || 0).toLocaleString('ko-KR');
}

export function formatCrawlRunTime(value) {
    const date = value ? new Date(value) : null;
    if (!date || Number.isNaN(date.getTime())) return '-';

    return new Intl.DateTimeFormat('ko-KR', {
        timeZone: 'Asia/Seoul',
        year: 'numeric', month: '2-digit', day: '2-digit',
        hour: '2-digit', minute: '2-digit', second: '2-digit', hour12: false,
    }).format(date);
}

function formatElapsed(value) {
    const completedAt = value ? new Date(value).getTime() : NaN;
    const elapsedMs = Date.now() - completedAt;
    if (!Number.isFinite(elapsedMs)) return '-';
    if (elapsedMs < 60000) return '1분 미만';
    const minutes = Math.floor(elapsedMs / 60000);
    if (minutes < 60) return `${minutes.toLocaleString('ko-KR')}분`;
    const hours = Math.floor(minutes / 60);
    if (hours < 24) return `${hours.toLocaleString('ko-KR')}시간`;
    return `${Math.floor(hours / 24).toLocaleString('ko-KR')}일`;
}

function failureCount(run) {
    return Number(run.preprocessingFailedCount || 0) + Number(run.httpFailedCount || 0) + Number(run.transportFailedCount || 0);
}

function RunDetail({ run }) {
    const channels = run.channels || run.channelRuns || [];
    const flow = [
        ['수집기 출력', run.crawlerOutputCount],
        ['공통 검증 탈락', run.validationRejectedCount],
        ['URL 중복 제외', run.duplicateUrlCount],
        ['선택 가능', run.eligibleCount],
        ['최종 선택', run.selectedCount],
        ['상한으로 제외', run.droppedByLimitCount],
        ['전처리 실패', run.preprocessingFailedCount],
        ['백엔드 정상 응답', run.backendAcknowledgedCount],
        ['HTTP 실패', run.httpFailedCount],
        ['전송 실패', run.transportFailedCount],
    ];

    return (
        <section className="mt-6 rounded-2xl border border-slate-200 p-5">
            <div className="flex flex-wrap items-center justify-between gap-3">
                <div><h3 className="font-bold text-slate-950">선택한 실행 상세</h3><p className="mt-1 break-all text-xs text-slate-500">runId: {run.runId}</p></div>
                <StatusBadge outcome={run.outcome} />
            </div>
            {run.reconciliationOk === false && <p className="mt-4 rounded-2xl bg-rose-50 px-4 py-3 text-sm font-semibold text-rose-700">단계별 처리 수량이 일치하지 않습니다.</p>}
            <div className="mt-5">
                <h4 className="text-sm font-bold text-slate-800">수량 흐름</h4>
                <p className="mt-1 text-xs text-slate-500">수집원 내부 탈락 {formatCount(run.sourceInvalidCount)}건은 수집기 출력 전에 제외되어 공통 검증 탈락과 분리합니다.</p>
                <div className="mt-3 grid gap-2 sm:grid-cols-2 lg:grid-cols-5">
                    {flow.map(([label, value]) => <div key={label} className="rounded-xl bg-slate-50 p-3"><p className="text-xs text-slate-500">{label}</p><p className="mt-1 font-bold text-slate-900">{formatCount(value)}건</p></div>)}
                </div>
            </div>
            <div className="mt-5">
                <h4 className="text-sm font-bold text-slate-800">채널별 상태</h4>
                {channels.length === 0 ? <p className="mt-2 text-sm text-slate-500">저장된 채널별 이력이 없습니다.</p> : (
                    <div className="mt-3 grid gap-2 sm:grid-cols-3">
                        {channels.map((channel) => <div key={channel.channel} className="rounded-xl border border-slate-100 p-3"><p className="text-sm font-bold uppercase text-slate-800">{channel.channel}</p><div className="mt-2"><StatusBadge outcome={channel.outcome} /></div><p className="mt-2 text-xs text-slate-500">공통 검증 통과 {formatCount(channel.validatedArticleCount)}건 · 수집원 내부 탈락 {formatCount(channel.sourceInvalidCount)}건</p></div>)}
                    </div>
                )}
            </div>
        </section>
    );
}

export default function AdminCrawlRunsTab({ runs, loading, error, selectedRun, detailLoading, detailError, onRefresh, onSelectRun, onRetryDetail }) {
    const latestRun = runs[0];
    const latestReferenceTime = latestRun?.completedAt || latestRun?.startedAt;
    return (
        <section className="rounded-3xl border border-slate-200 bg-white p-6 shadow-sm">
            <div className="flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
                <div><h2 className="text-lg font-bold text-slate-950">수집 현황</h2><p className="text-sm text-slate-500">관측된 수집 범위의 실행 상태와 처리 수량입니다. 정상 완료도 세상 전체의 기사 수집을 보장하지 않습니다.</p></div>
                <button type="button" onClick={onRefresh} disabled={loading} className="inline-flex items-center justify-center gap-2 rounded-2xl border border-slate-200 px-4 py-2 text-sm font-semibold text-slate-600 disabled:opacity-60"><RefreshCw className={`h-4 w-4 ${loading ? 'animate-spin' : ''}`} />새로고침</button>
            </div>
            {loading ? <div className="mt-5 rounded-2xl bg-slate-50 p-6 text-sm text-slate-500">수집 실행 이력을 불러오는 중입니다.</div> : error ? (
                <div className="mt-5 rounded-2xl bg-rose-50 p-6 text-sm text-rose-700"><p className="font-semibold">{error}</p><button type="button" onClick={onRefresh} className="mt-3 rounded-xl border border-rose-200 px-3 py-2 font-semibold">다시 시도</button></div>
            ) : runs.length === 0 ? <div className="mt-5 rounded-2xl bg-slate-50 p-6 text-sm text-slate-500">아직 저장된 수집 실행 이력이 없습니다. 다음 크롤러 완료 보고부터 이력이 표시됩니다.</div> : (
                <>
                    <div className="mt-5 grid gap-3 md:grid-cols-2 xl:grid-cols-4">
                        <div className="rounded-2xl bg-slate-50 p-4"><p className="text-xs font-bold text-slate-500">최근 결과</p><div className="mt-2"><StatusBadge outcome={latestRun.outcome} /></div></div>
                        <div className="rounded-2xl bg-slate-50 p-4"><p className="text-xs font-bold text-slate-500">{latestRun.completedAt ? '마지막 완료 시각' : '실행 시작 시각'}</p><p className="mt-2 font-bold">{formatCrawlRunTime(latestReferenceTime)}</p></div>
                        <div className="rounded-2xl bg-slate-50 p-4"><p className="text-xs font-bold text-slate-500">{latestRun.completedAt ? '마지막 완료 후 경과' : '실행 시작 후 경과'}</p><p className="mt-2 font-bold">{formatElapsed(latestReferenceTime)}</p></div>
                        <div className="rounded-2xl bg-slate-50 p-4"><p className="text-xs font-bold text-slate-500">백엔드 정상 응답 요청</p><p className="mt-2 font-bold">{formatCount(latestRun.backendAcknowledgedCount)}건</p></div>
                    </div>
                    <p className="mt-3 text-xs text-slate-500">백엔드 정상 응답은 신규 저장 건수가 아니라 백엔드가 정상 응답한 요청 수입니다.</p>
                    <div className="mt-5 overflow-x-auto rounded-2xl border border-slate-100"><table className="min-w-full divide-y divide-slate-100 text-sm"><thead className="bg-slate-50 text-left text-xs font-bold text-slate-500"><tr><th className="px-4 py-3">실행 시각</th><th className="px-4 py-3">결과</th><th className="px-4 py-3 text-right">수집기 출력</th><th className="px-4 py-3 text-right">선택</th><th className="px-4 py-3 text-right">정상 응답</th><th className="px-4 py-3 text-right">처리 실패</th></tr></thead><tbody className="divide-y divide-slate-100">{runs.map((run) => <tr key={run.runId} onClick={() => onSelectRun(run.runId)} className={`cursor-pointer hover:bg-blue-50 ${selectedRun?.runId === run.runId ? 'bg-blue-50' : ''}`}><td className="whitespace-nowrap px-4 py-3 font-semibold">{formatCrawlRunTime(run.completedAt || run.startedAt)}</td><td className="px-4 py-3"><StatusBadge outcome={run.outcome} /></td><td className="px-4 py-3 text-right">{formatCount(run.crawlerOutputCount)}</td><td className="px-4 py-3 text-right">{formatCount(run.selectedCount)}</td><td className="px-4 py-3 text-right">{formatCount(run.backendAcknowledgedCount)}</td><td className="px-4 py-3 text-right">{formatCount(failureCount(run))}</td></tr>)}</tbody></table></div>
                    {detailLoading && <div className="mt-6 rounded-2xl bg-slate-50 p-5 text-sm text-slate-500">선택한 실행의 상세 정보를 불러오는 중입니다.</div>}
                    {!detailLoading && detailError && <div className="mt-6 rounded-2xl bg-rose-50 p-5 text-sm text-rose-700"><p className="font-semibold">{detailError}</p><p className="mt-1">최근 실행 목록은 그대로 유지됩니다.</p><button type="button" onClick={onRetryDetail} className="mt-3 rounded-xl border border-rose-200 px-3 py-2 font-semibold">상세 다시 시도</button></div>}
                    {!detailLoading && !detailError && selectedRun && <RunDetail run={selectedRun} />}
                </>
            )}
        </section>
    );
}

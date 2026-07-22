import React from 'react';
import { RefreshCw } from 'lucide-react';

export default function AdminMergeSuggestionsTab({
    generatingSuggestions,
    recommendationRun,
    selectedSuggestionGroup,
    suggestionGroupSearchKeyword,
    filteredSuggestionGroups,
    selectedSuggestionGroupId,
    mergeSuggestions,
    onGenerateSuggestions,
    onRefresh,
    onSuggestionGroupSearchChange,
    onSelectSuggestionGroup,
    onApproveSuggestion,
    onRejectSuggestion,
}) {
    return (
        <section className="rounded-3xl border border-slate-200 bg-white p-6 shadow-sm">
            <div className="flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
                <div>
                    <h2 className="text-lg font-bold text-slate-950">AI 병합 추천 검토</h2>
                    <p className="text-sm text-slate-500">
                        대표 키워드 그룹 하나를 선택한 뒤, 해당 그룹 기준으로만 유사도를 계산합니다.
                    </p>
                </div>

                <div className="flex flex-wrap gap-2">
                    <button
                        type="button"
                        onClick={onGenerateSuggestions}
                        disabled={generatingSuggestions || !selectedSuggestionGroup || ['PENDING', 'RUNNING'].includes(recommendationRun?.status)}
                        className="inline-flex items-center justify-center gap-2 rounded-2xl bg-blue-600 px-4 py-2 text-sm font-semibold text-white transition hover:bg-blue-700 disabled:cursor-not-allowed disabled:opacity-60"
                    >
                        <RefreshCw className={`h-4 w-4 ${generatingSuggestions ? 'animate-spin' : ''}`} />
                        {generatingSuggestions ? '추천 생성 중...' : 'AI 추천 생성'}
                    </button>
                    <button
                        type="button"
                        onClick={onRefresh}
                        className="rounded-2xl border border-slate-200 px-4 py-2 text-sm font-semibold text-slate-600 transition hover:bg-slate-50"
                    >
                        새로고침
                    </button>
                </div>
            </div>

            <div className="mt-5 rounded-2xl border border-slate-100 bg-slate-50 p-4">
                {recommendationRun && (
                    <div className="mb-4 rounded-2xl border border-blue-100 bg-white p-4 text-sm text-slate-600">
                        <div className="flex flex-wrap items-center justify-between gap-2">
                            <span className="font-bold text-slate-900">추천 실행 상태: {recommendationRun.status}</span>
                            {recommendationRun.failureCode && (
                                <span className="text-rose-600">실패 코드: {recommendationRun.failureCode}</span>
                            )}
                        </div>
                        {recommendationRun.status === 'SUCCESS' && (
                            <p className="mt-2">
                                후보 {recommendationRun.candidateCount ?? 0}개 중 요청 {recommendationRun.requestedSuggestionCount ?? 0}개,
                                새 저장 {recommendationRun.savedSuggestionCount ?? 0}개
                            </p>
                        )}
                        {['PENDING', 'RUNNING'].includes(recommendationRun.status) && (
                            <p className="mt-2">모델 추론은 백그라운드에서 실행 중이며 3초마다 상태를 갱신합니다.</p>
                        )}
                    </div>
                )}
                <div className="flex flex-col gap-3 lg:flex-row lg:items-center lg:justify-between">
                    <div>
                        <p className="text-sm font-bold text-slate-800">추천 기준 대표 키워드</p>
                        <p className="text-sm text-slate-500">
                            {selectedSuggestionGroup
                                ? `"${selectedSuggestionGroup.canonicalKeyword}" 기준으로 후보 키워드를 비교합니다.`
                                : '대표 키워드 그룹을 선택해야 AI 추천을 생성할 수 있습니다.'}
                        </p>
                    </div>

                    <input
                        value={suggestionGroupSearchKeyword}
                        onChange={(event) => onSuggestionGroupSearchChange(event.target.value)}
                        placeholder="대표 키워드 또는 alias 검색"
                        className="w-full rounded-2xl border border-slate-200 bg-white px-4 py-2 text-sm outline-none transition focus:border-blue-400 focus:ring-4 focus:ring-blue-50 lg:max-w-xs"
                    />
                </div>

                <div className="mt-4 grid gap-2 md:grid-cols-2 xl:grid-cols-3">
                    {filteredSuggestionGroups.length === 0 ? (
                        <div className="rounded-2xl bg-white p-4 text-sm text-slate-500 md:col-span-2 xl:col-span-3">
                            조건에 맞는 활성 대표 키워드 그룹이 없습니다.
                        </div>
                    ) : (
                        filteredSuggestionGroups.map((group) => {
                            const selected = selectedSuggestionGroupId === group.id;

                            return (
                                <button
                                    key={group.id}
                                    type="button"
                                    onClick={() => onSelectSuggestionGroup(group.id)}
                                    className={`rounded-2xl border p-4 text-left transition ${
                                        selected
                                            ? 'border-blue-300 bg-blue-50 text-blue-900'
                                            : 'border-slate-200 bg-white text-slate-700 hover:border-blue-200 hover:bg-blue-50'
                                    }`}
                                >
                                    <span className="block text-sm font-bold">{group.canonicalKeyword}</span>
                                    <span className="mt-1 block text-xs text-slate-500">
                                        alias {(group.aliases || []).length}개
                                    </span>
                                </button>
                            );
                        })
                    )}
                </div>
            </div>

            <div className="mt-5 overflow-hidden rounded-2xl border border-slate-100">
                {mergeSuggestions.length === 0 ? (
                    <div className="p-6 text-sm text-slate-500">
                        현재 검토할 AI 병합 추천이 없습니다. AI 추천 생성을 실행하면 후보가 표시됩니다.
                    </div>
                ) : (
                    <div className="divide-y divide-slate-100">
                        {mergeSuggestions.map((suggestion) => (
                            <div key={suggestion.id} className="p-4">
                                <div className="flex flex-col gap-3 lg:flex-row lg:items-center lg:justify-between">
                                    <div>
                                        <div className="flex flex-wrap items-center gap-2">
                                            <span className="text-base font-bold text-slate-950">
                                                {suggestion.sourceKeyword}
                                            </span>
                                            <span className="text-sm text-slate-400">→</span>
                                            <span className="text-base font-bold text-blue-700">
                                                {suggestion.targetKeyword}
                                            </span>
                                            <span className="rounded-full bg-amber-50 px-2.5 py-1 text-xs font-bold text-amber-700">
                                                유사도 {Number(suggestion.similarityScore).toFixed(4)}
                                            </span>
                                        </div>

                                        <p className="mt-1 text-sm text-slate-500">
                                            {suggestion.reason || '추천 이유 없음'}
                                        </p>

                                        <p className="mt-1 text-xs text-slate-400">
                                            모델: {suggestion.modelName || '-'} / 버전: {suggestion.modelVersion || '-'}
                                        </p>
                                    </div>

                                    <div className="flex gap-2">
                                        <button
                                            type="button"
                                            onClick={() => onApproveSuggestion(suggestion.id)}
                                            className="rounded-2xl bg-blue-600 px-4 py-2 text-sm font-semibold text-white transition hover:bg-blue-700"
                                        >
                                            승인
                                        </button>
                                        <button
                                            type="button"
                                            onClick={() => onRejectSuggestion(suggestion.id)}
                                            className="rounded-2xl border border-rose-200 px-4 py-2 text-sm font-semibold text-rose-600 transition hover:bg-rose-50"
                                        >
                                            거절
                                        </button>
                                    </div>
                                </div>
                            </div>
                        ))}
                    </div>
                )}
            </div>
        </section>
    );
}

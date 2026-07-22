import React from 'react';
import { Plus, RefreshCw } from 'lucide-react';

export default function AdminKeywordTab({
    form,
    keywords,
    loading,
    saving,
    onChange,
    onCreateKeyword,
    onRefresh,
    onToggleKeyword,
}) {
    return (
        <section className="grid gap-6 lg:grid-cols-[360px_1fr]">
            <form onSubmit={onCreateKeyword} className="rounded-3xl border border-slate-200 bg-white p-6 shadow-sm">
                <h2 className="text-lg font-bold text-slate-950">키워드 추가</h2>
                <p className="mt-1 text-sm text-slate-500">MVP 단계에서는 삭제 없이 활성/비활성으로만 관리합니다.</p>

                <label className="mt-5 block text-sm font-semibold text-slate-700">
                    키워드
                    <input
                        name="keyword"
                        value={form.keyword}
                        onChange={onChange}
                        placeholder="예: 생성형 AI"
                        className="mt-2 w-full rounded-2xl border border-slate-200 px-4 py-2 text-sm outline-none transition focus:border-blue-400 focus:ring-4 focus:ring-blue-50"
                    />
                </label>

                <label className="mt-4 block text-sm font-semibold text-slate-700">
                    카테고리
                    <input
                        name="category"
                        value={form.category}
                        onChange={onChange}
                        placeholder="예: AI"
                        className="mt-2 w-full rounded-2xl border border-slate-200 px-4 py-2 text-sm outline-none transition focus:border-blue-400 focus:ring-4 focus:ring-blue-50"
                    />
                </label>

                <label className="mt-4 block text-sm font-semibold text-slate-700">
                    키워드 용도
                    <select
                        name="keywordType"
                        value={form.keywordType}
                        onChange={onChange}
                        className="mt-2 w-full rounded-2xl border border-slate-200 px-4 py-2 text-sm outline-none transition focus:border-blue-400 focus:ring-4 focus:ring-blue-50"
                    >
                        <option value="TRACKING">추적 키워드</option>
                        <option value="BLOCKED">차단 키워드</option>
                    </select>
                </label>

                <label className="mt-4 block text-sm font-semibold text-slate-700">
                    우선순위
                    <input
                        name="priority"
                        type="number"
                        value={form.priority}
                        onChange={onChange}
                        className="mt-2 w-full rounded-2xl border border-slate-200 px-4 py-2 text-sm outline-none transition focus:border-blue-400 focus:ring-4 focus:ring-blue-50"
                    />
                </label>

                <label className="mt-4 flex items-center gap-2 text-sm font-semibold text-slate-700">
                    <input
                        name="notionEnabled"
                        type="checkbox"
                        checked={form.notionEnabled}
                        onChange={onChange}
                        className="h-4 w-4 rounded border-slate-300"
                    />
                    Notion 보고서 반영 대상
                </label>

                <button
                    type="submit"
                    disabled={saving}
                    className="mt-6 inline-flex w-full items-center justify-center gap-2 rounded-2xl bg-blue-600 px-4 py-2 text-sm font-semibold text-white transition hover:bg-blue-700 disabled:cursor-not-allowed disabled:opacity-60"
                >
                    <Plus className="h-4 w-4" />
                    {saving ? '저장 중...' : '키워드 등록'}
                </button>
            </form>

            <section className="rounded-3xl border border-slate-200 bg-white p-6 shadow-sm">
                <div className="flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
                    <div>
                        <h2 className="text-lg font-bold text-slate-950">관리 키워드 목록</h2>
                        <p className="text-sm text-slate-500">활성 키워드는 이후 크롤링 보고서 필터 기준으로 확장할 수 있습니다.</p>
                    </div>
                    <button
                        type="button"
                        onClick={onRefresh}
                        className="inline-flex items-center justify-center gap-2 rounded-2xl border border-slate-200 px-4 py-2 text-sm font-semibold text-slate-600 transition hover:bg-slate-50"
                    >
                        <RefreshCw className="h-4 w-4" />
                        새로고침
                    </button>
                </div>

                <div className="mt-5 overflow-hidden rounded-2xl border border-slate-100">
                    {loading ? (
                        <div className="p-6 text-sm text-slate-500">키워드 목록을 불러오는 중...</div>
                    ) : keywords.length === 0 ? (
                        <div className="p-6 text-sm text-slate-500">아직 등록된 관리 키워드가 없습니다.</div>
                    ) : (
                        <div className="divide-y divide-slate-100">
                            {keywords.map((item) => (
                                <div key={item.id} className="flex flex-col gap-3 p-4 sm:flex-row sm:items-center sm:justify-between">
                                    <div>
                                        <div className="flex flex-wrap items-center gap-2">
                                            <p className="text-base font-bold text-slate-950">{item.keyword}</p>

                                            <span className={`rounded-full px-2.5 py-1 text-xs font-bold ${
                                                item.keywordType === 'BLOCKED'
                                                    ? 'bg-rose-50 text-rose-700'
                                                    : 'bg-indigo-50 text-indigo-700'
                                            }`}>
                                                {item.keywordType === 'BLOCKED' ? '차단' : '추적'}
                                            </span>

                                            <span className={`rounded-full px-2.5 py-1 text-xs font-bold ${
                                                item.active
                                                    ? 'bg-emerald-50 text-emerald-700'
                                                    : 'bg-slate-100 text-slate-500'
                                            }`}>
                                                {item.active ? '활성' : '비활성'}
                                            </span>

                                            {item.notionEnabled && (
                                                <span className="rounded-full bg-blue-50 px-2.5 py-1 text-xs font-bold text-blue-700">
                                                    Notion
                                                </span>
                                            )}
                                        </div>
                                        <p className="mt-1 text-sm text-slate-500">
                                            카테고리: {item.category || '-'} · 우선순위: {item.priority ?? 0}
                                        </p>
                                    </div>
                                    <button
                                        type="button"
                                        onClick={() => onToggleKeyword(item.id)}
                                        className={`rounded-2xl px-4 py-2 text-sm font-semibold transition ${
                                            item.active
                                                ? 'border border-rose-200 text-rose-600 hover:bg-rose-50'
                                                : 'border border-emerald-200 text-emerald-700 hover:bg-emerald-50'
                                        }`}
                                    >
                                        {item.active ? '비활성화' : '활성화'}
                                    </button>
                                </div>
                            ))}
                        </div>
                    )}
                </div>
            </section>
        </section>
    );
}

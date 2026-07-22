import React from 'react';

const ADMIN_TABS = [
    { id: 'keywords', label: '추적/차단 키워드' },
    { id: 'groups', label: '그룹 관리' },
    { id: 'suggestions', label: 'AI 병합 추천' },
    { id: 'crawl-runs', label: '수집 현황' },
];

export default function AdminTabNav({ activeTab, onChangeTab }) {
    return (
        <section className="rounded-3xl border border-slate-200 bg-white p-2 shadow-sm">
            <div className="grid gap-2 sm:grid-cols-2 lg:grid-cols-4">
                {ADMIN_TABS.map((tab) => (
                    <button
                        key={tab.id}
                        type="button"
                        onClick={() => onChangeTab(tab.id)}
                        className={`rounded-2xl px-4 py-3 text-sm font-bold transition ${
                            activeTab === tab.id
                                ? 'bg-blue-600 text-white shadow-sm'
                                : 'bg-slate-50 text-slate-600 hover:bg-slate-100'
                        }`}
                    >
                        {tab.label}
                    </button>
                ))}
            </div>
        </section>
    );
}

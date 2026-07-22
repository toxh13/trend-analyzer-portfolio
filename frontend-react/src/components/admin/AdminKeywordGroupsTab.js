import React from 'react';

export default function AdminKeywordGroupsTab({
    groupForm,
    saving,
    filteredKeywordGroups,
    groupSearchKeyword,
    expandedGroupIds,
    aliasForms,
    onGroupFormChange,
    onCreateGroup,
    onGroupSearchChange,
    onRefresh,
    onToggleGroupExpand,
    onActivateGroup,
    onDeactivateGroup,
    onAliasChange,
    onAddAlias,
    onActivateAlias,
    onDeactivateAlias,
    onDetachAlias,
}) {
    return (
        <section className="grid gap-6 lg:grid-cols-[360px_1fr]">
            <form onSubmit={onCreateGroup} className="rounded-3xl border border-slate-200 bg-white p-6 shadow-sm">
                <h2 className="text-lg font-bold text-slate-950">대표 키워드 추가</h2>
                <p className="mt-1 text-sm text-slate-500">
                    메인 트렌드에서 기준이 되는 대표 키워드를 직접 등록합니다.
                </p>

                <label className="mt-5 block text-sm font-semibold text-slate-700">
                    대표 키워드
                    <input
                        value={groupForm.canonicalKeyword}
                        onChange={(event) => onGroupFormChange('canonicalKeyword', event.target.value)}
                        placeholder="예: 반도체"
                        className="mt-2 w-full rounded-2xl border border-slate-200 px-4 py-2 text-sm outline-none transition focus:border-blue-400 focus:ring-4 focus:ring-blue-50"
                    />
                </label>

                <label className="mt-4 block text-sm font-semibold text-slate-700">
                    설명
                    <textarea
                        value={groupForm.description}
                        onChange={(event) => onGroupFormChange('description', event.target.value)}
                        placeholder="예: AI, 머신러닝, 딥러닝 관련 대표 키워드"
                        className="mt-2 min-h-24 w-full rounded-2xl border border-slate-200 px-4 py-2 text-sm outline-none transition focus:border-blue-400 focus:ring-4 focus:ring-blue-50"
                    />
                </label>

                <button
                    type="submit"
                    disabled={saving}
                    className="mt-6 inline-flex w-full items-center justify-center gap-2 rounded-2xl bg-blue-600 px-4 py-2 text-sm font-semibold text-white transition hover:bg-blue-700 disabled:cursor-not-allowed disabled:opacity-60"
                >
                    대표 키워드 등록
                </button>
            </form>

            <section className="rounded-3xl border border-slate-200 bg-white p-6 shadow-sm">
                <div className="flex items-center justify-between gap-3">
                    <div>
                        <h2 className="text-lg font-bold text-slate-950">대표 키워드 그룹 목록</h2>
                        <p className="text-sm text-slate-500">
                            alias 등록은 대표 키워드로 합산합니다.
                        </p>
                    </div>
                    <div className="mt-4">
                        <input
                            value={groupSearchKeyword}
                            onChange={(event) => onGroupSearchChange(event.target.value)}
                            placeholder="키워드 또는 alias 검색"
                            className="w-full rounded-2xl border border-slate-200 px-4 py-2 text-sm outline-none transition focus:border-blue-400 focus:ring-4 focus:ring-blue-50"
                        />
                    </div>

                    <button
                        type="button"
                        onClick={onRefresh}
                        className="rounded-2xl border border-slate-200 px-4 py-2 text-sm font-semibold text-slate-600 transition hover:bg-slate-50"
                    >
                        새로고침
                    </button>
                </div>

                <div className="mt-5 space-y-4">
                    {filteredKeywordGroups.length === 0 ? (
                        <div className="rounded-2xl bg-slate-50 p-5 text-sm text-slate-500">
                            조건에 맞는 대표 키워드 그룹이 없습니다.
                        </div>
                    ) : (
                        filteredKeywordGroups.map((group) => (
                            <div key={group.id} className="rounded-2xl border border-slate-100 p-4">
                                <div className="flex flex-col gap-3 sm:flex-row sm:items-start sm:justify-between">
                                    <div>
                                        <div className="flex flex-wrap items-center gap-2">
                                            <h3 className="text-base font-bold text-slate-950">
                                                {group.canonicalKeyword}
                                            </h3>

                                            <span className={`rounded-full px-2.5 py-1 text-xs font-bold ${
                                                group.active
                                                    ? 'bg-emerald-50 text-emerald-700'
                                                    : 'bg-slate-100 text-slate-500'
                                            }`}>
                                                {group.active ? '활성' : '비활성'}
                                            </span>
                                        </div>

                                        <p className="mt-1 text-sm text-slate-500">
                                            {group.description || '설명 없음'}
                                        </p>
                                    </div>

                                    <div className="mt-4 flex flex-wrap items-center gap-2">
                                        <button
                                            type="button"
                                            onClick={() => onToggleGroupExpand(group.id)}
                                            className="rounded-2xl border border-slate-200 px-4 py-2 text-sm font-semibold text-slate-600 transition hover:bg-slate-50"
                                        >
                                            {(expandedGroupIds[group.id] ? 'alias 접기' : 'alias 보기')}
                                            {' '}
                                            ({(group.aliases || []).length}개)
                                        </button>

                                        {group.active ? (
                                            <button
                                                type="button"
                                                onClick={() => onDeactivateGroup(group.id)}
                                                className="rounded-2xl border border-rose-200 px-4 py-2 text-sm font-semibold text-rose-600 transition hover:bg-rose-50"
                                            >
                                                그룹 비활성화
                                            </button>
                                        ) : (
                                            <button
                                                type="button"
                                                onClick={() => onActivateGroup(group.id)}
                                                className="rounded-2xl border border-emerald-200 px-4 py-2 text-sm font-semibold text-emerald-700 transition hover:bg-emerald-50"
                                            >
                                                그룹 활성화
                                            </button>
                                        )}
                                    </div>
                                </div>

                                {expandedGroupIds[group.id] && (
                                    <div className="mt-4 rounded-2xl bg-slate-50 p-4">
                                        <p className="text-sm font-bold text-slate-700">alias 목록</p>

                                        <div className="mt-2 flex flex-wrap gap-2">
                                            {(group.aliases || []).length === 0 ? (
                                                <span className="text-sm text-slate-400">등록된 alias 없음</span>
                                            ) : (
                                                group.aliases.map((alias) => (
                                                    <span
                                                        key={alias.id}
                                                        className={`inline-flex items-center gap-2 rounded-full px-3 py-1 text-xs font-bold ${
                                                            alias.active
                                                                ? 'bg-indigo-50 text-indigo-700'
                                                                : 'bg-slate-100 text-slate-400'
                                                        }`}
                                                    >
                                                        {alias.rawKeyword}

                                                        <span className="text-[10px] opacity-70">
                                                            {alias.sourceType}
                                                        </span>

                                                        {alias.active ? (
                                                            <button
                                                                type="button"
                                                                onClick={() => onDeactivateAlias(alias.id)}
                                                                className="text-rose-500 hover:text-rose-700"
                                                            >
                                                                비활성화
                                                            </button>
                                                        ) : (
                                                            <button
                                                                type="button"
                                                                onClick={() => onActivateAlias(alias.id)}
                                                                className="text-emerald-600 hover:text-emerald-800"
                                                            >
                                                                활성화
                                                            </button>
                                                        )}

                                                        <button
                                                            type="button"
                                                            onClick={() => onDetachAlias(alias.id, alias.rawKeyword)}
                                                            className="text-slate-500 hover:text-slate-800"
                                                        >
                                                            해제
                                                        </button>
                                                    </span>
                                                ))
                                            )}
                                        </div>

                                        {group.active && (
                                            <div className="mt-3 flex gap-2">
                                                <input
                                                    value={aliasForms[group.id] || ''}
                                                    onChange={(event) => onAliasChange(group.id, event.target.value)}
                                                    placeholder="예: AI"
                                                    className="flex-1 rounded-2xl border border-slate-200 px-4 py-2 text-sm outline-none transition focus:border-blue-400 focus:ring-4 focus:ring-blue-50"
                                                />
                                                <button
                                                    type="button"
                                                    onClick={() => onAddAlias(group.id)}
                                                    className="rounded-2xl bg-slate-900 px-4 py-2 text-sm font-semibold text-white transition hover:bg-slate-700"
                                                >
                                                    alias 추가
                                                </button>
                                            </div>
                                        )}
                                    </div>
                                )}
                            </div>
                        ))
                    )}
                </div>
            </section>
        </section>
    );
}

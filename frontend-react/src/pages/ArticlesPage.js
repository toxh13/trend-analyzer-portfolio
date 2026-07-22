import React, { useState } from 'react';
import { useOutletContext } from 'react-router-dom';

import ArticleSidebar from '../components/ArticleSidebar';
import TrendRankingList from '../components/TrendRankingList';
import { useKeywordDetail } from '../hooks/useKeywordDetail';

export default function ArticlesPage() {
    const {
        allTrends = [],
        loadingAllTrends = false,
    } = useOutletContext() ?? {};
    const [selectedTrend, setSelectedTrend] = useState(null);
    const {
        articles,
        history,
        loadingKeywordDetail,
    } = useKeywordDetail(selectedTrend?.keyword);

    const selected = selectedTrend
        ? {
            ...selectedTrend,
            history,
        }
        : null;

    return (
        <section className="space-y-6">
            <div className="rounded-3xl border border-slate-200 bg-white p-6 shadow-sm">
                <p className="text-sm font-semibold text-blue-600">Article Explorer</p>
                <h2 className="mt-1 text-2xl font-bold text-slate-950">관련 기사 탐색</h2>
                <p className="mt-2 text-sm leading-relaxed text-slate-500">
                    왼쪽의 인기 키워드를 선택하면 오른쪽 영역에서 해당 키워드의 관련 기사와 7일 흐름을 확인할 수 있습니다.
                    메인 화면과 달리 기사 탐색에 집중하도록 페이지를 분리했습니다.
                </p>
            </div>

            <section className="grid gap-6 xl:grid-cols-[minmax(0,1fr)_420px]">
                <TrendRankingList
                    filteredTrends={allTrends}
                    loadingTrends={loadingAllTrends}
                    selectedId={selectedTrend?.id}
                    onSelectKeyword={setSelectedTrend}
                    eyebrow="Article Keywords"
                    title="관련 기사를 볼 키워드 선택"
                    emptyMessage="관련 기사를 조회할 키워드 데이터가 없습니다."
                />

                <ArticleSidebar
                    selected={selected}
                    articles={articles}
                    loadingArticles={loadingKeywordDetail}
                    onClose={() => setSelectedTrend(null)}
                />
            </section>
        </section>
    );
}

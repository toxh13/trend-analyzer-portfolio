import React, { useCallback, useEffect, useMemo, useRef, useState } from 'react';
import { useNavigate, useOutletContext } from 'react-router-dom';

import StatsStrip from '../components/StatsStrip';
import TrendRankingList from '../components/TrendRankingList';
import { fetchPopularTrends, fetchSurgingTrends } from '../api/trendApi';

const RANKING_MODES = {
    popular: {
        id: 'popular',
        label: '전체 인기',
        eyebrow: 'Volume Ranking',
        title: '전체 인기 키워드',
        description: '최근 집계 기준 전체 뉴스에서 언급량이 많은 키워드입니다.',
        emptyMessage: '아직 표시할 전체 인기 키워드 데이터가 없습니다.',
    },
    surging: {
        id: 'surging',
        label: '급상승',
        eyebrow: 'Rising Signals',
        title: '급상승 키워드',
        description: '최근 24시간 동안 직전 24시간보다 언급량이 빠르게 늘어난 키워드입니다.',
        emptyMessage: '최근 24시간 기준 급상승 키워드가 없습니다.',
    },
};

export default function HomePage() {
    const navigate = useNavigate();
    const { stats = null, registerPageRefresh } = useOutletContext() ?? {};
    const [rankingMode, setRankingMode] = useState('popular');
    const [popularTrends, setPopularTrends] = useState([]);
    const [surgingTrends, setSurgingTrends] = useState([]);
    const [loadingPopular, setLoadingPopular] = useState(true);
    const [loadingSurging, setLoadingSurging] = useState(true);
    const mountedRef = useRef(true);
    const refreshPromiseRef = useRef(null);
    const hasSuccessfulDataRef = useRef(false);

    useEffect(() => {
        mountedRef.current = true;
        return () => {
            mountedRef.current = false;
        };
    }, []);

    const loadRankings = useCallback(() => {
        if (refreshPromiseRef.current) {
            return refreshPromiseRef.current;
        }

        if (!hasSuccessfulDataRef.current) {
            setLoadingPopular(true);
            setLoadingSurging(true);
        }

        const request = Promise.allSettled([
            fetchPopularTrends(20),
            fetchSurgingTrends(10),
        ])
            .then(([popularResult, surgingResult]) => {
                const failure = [popularResult, surgingResult]
                    .find((result) => result.status === 'rejected');
                if (failure) {
                    throw failure.reason;
                }
                if (mountedRef.current) {
                    setPopularTrends(popularResult.value);
                    setSurgingTrends(surgingResult.value);
                    hasSuccessfulDataRef.current = true;
                }
            })
            .catch((error) => {
                console.error('홈 키워드 순위 조회 실패:', error);
                throw error;
            })
            .finally(() => {
                if (mountedRef.current) {
                    setLoadingPopular(false);
                    setLoadingSurging(false);
                }
                if (refreshPromiseRef.current === request) {
                    refreshPromiseRef.current = null;
                }
            });

        refreshPromiseRef.current = request;
        return request;
    }, []);

    useEffect(() => {
        loadRankings().catch(() => {});
    }, [loadRankings]);

    useEffect(() => {
        if (!registerPageRefresh) {
            return undefined;
        }
        return registerPageRefresh(loadRankings);
    }, [loadRankings, registerPageRefresh]);

    const activeMode = RANKING_MODES[rankingMode];
    const activeTrends = rankingMode === 'popular' ? popularTrends : surgingTrends;
    const loadingActiveTrends = rankingMode === 'popular' ? loadingPopular : loadingSurging;
    const activeTitle = useMemo(
        () => `${activeMode.title} TOP ${activeTrends.length}`,
        [activeMode.title, activeTrends.length]
    );

    const handleSelectKeyword = (item) => {
        navigate(`/keywords/${encodeURIComponent(item.keyword)}`);
    };

    return (
        <section className="space-y-6">
            <div className="rounded-3xl border border-slate-200 bg-white p-6 shadow-sm">
                <p className="text-sm font-semibold text-blue-600">Popular Keywords</p>
                <h2 className="mt-1 text-2xl font-bold text-slate-950">인기 키워드</h2>
                <p className="mt-2 text-sm leading-relaxed text-slate-500">
                    전체 뉴스에서 많이 언급되는 큰 흐름과 최근 24시간 사이 급부상한 키워드를 전환해서 확인합니다.
                    전체 인기는 현재 관심이 큰 주제를, 급상승은 새로 떠오르는 이슈를 보여줍니다.
                </p>
            </div>

            <StatsStrip stats={stats} />

            <section className="rounded-3xl border border-slate-200 bg-white p-4 shadow-sm">
                <div className="flex flex-col gap-4 lg:flex-row lg:items-center lg:justify-between">
                    <div>
                        <p className="text-sm font-semibold text-blue-600">Ranking Mode</p>
                        <h3 className="mt-1 text-lg font-bold text-slate-950">{activeMode.label}</h3>
                        <p className="mt-1 text-sm text-slate-500">{activeMode.description}</p>
                    </div>

                    <div className="grid grid-cols-2 gap-2 rounded-2xl bg-slate-100 p-1">
                        {Object.values(RANKING_MODES).map((mode) => {
                            const active = rankingMode === mode.id;

                            return (
                                <button
                                    key={mode.id}
                                    type="button"
                                    onClick={() => setRankingMode(mode.id)}
                                    className={`rounded-xl px-4 py-2 text-sm font-bold transition ${
                                        active
                                            ? 'bg-blue-600 text-white shadow-sm'
                                            : 'text-slate-600 hover:bg-white hover:text-blue-700'
                                    }`}
                                >
                                    {mode.label}
                                </button>
                            );
                        })}
                    </div>
                </div>
            </section>

            <TrendRankingList
                filteredTrends={activeTrends}
                loadingTrends={loadingActiveTrends}
                selectedId={null}
                onSelectKeyword={handleSelectKeyword}
                eyebrow={activeMode.eyebrow}
                title={activeTitle}
                emptyMessage={activeMode.emptyMessage}
            />
        </section>
    );
}

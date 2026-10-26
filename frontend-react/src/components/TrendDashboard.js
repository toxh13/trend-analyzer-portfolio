import React, { useEffect, useMemo, useState } from 'react';

import DashboardHeader from './DashboardHeader';
import SidebarNav from './SidebarNav';
import StatsStrip from './StatsStrip';
import CategoryFilter from './CategoryFilter';
import TrendRankingList from './TrendRankingList';
import ArticleSidebar from './ArticleSidebar';
import VolatilityPanel from './VolatilityPanel';
import TrendChatbot from './TrendChatbot';
import { isStaticMode } from '../config/dataMode';
import { fetchKeywordArticles, fetchKeywordHistory, fetchTrendStats, fetchTrends } from '../api/trendApi';
import { buildTrendStats, CATEGORIES, CATEGORY_META } from '../utils/trendUtils';

// 기존 컴포넌트에서 직접 import하던 코드와의 호환성을 위해 재노출합니다.
export { CATEGORIES, CATEGORY_META };

export default function TrendDashboard() {
    const [trends, setTrends] = useState([]);
    const [stats, setStats] = useState(null);
    const [loadingTrends, setLoadingTrends] = useState(true);
    const [selectedCategory, setSelectedCategory] = useState('ALL');
    const [selected, setSelected] = useState(null);
    const [articles, setArticles] = useState([]);
    const [loadingArticles, setLoadingArticles] = useState(false);
    const [updatedAt, setUpdatedAt] = useState('');
    const [isMenuOpen, setIsMenuOpen] = useState(() => (
        typeof window !== 'undefined' ? window.innerWidth >= 1024 : true
    ));

    // 프로젝트 전체 폰트 로드입니다. /dashboard 백업 화면에서도 기존 가독성을 유지합니다.
    useEffect(() => {
        const link = document.createElement('link');
        link.rel = 'stylesheet';
        link.href =
            'https://fonts.googleapis.com/css2?family=Space+Grotesk:wght@500;700&family=Inter:wght@400;500;600;700&family=JetBrains+Mono:wght@400;500;600&display=swap';
        document.head.appendChild(link);
        return () => document.head.removeChild(link);
    }, []);

    useEffect(() => {
        const updateClock = () => {
            setUpdatedAt(new Date().toLocaleTimeString('ko-KR', {
                hour: '2-digit',
                minute: '2-digit',
                second: '2-digit',
            }));
        };

        updateClock();
        const clockTimer = setInterval(updateClock, 1000);
        return () => clearInterval(clockTimer);
    }, []);

    useEffect(() => {
        let isMounted = true;

        const fetchTrendsData = async () => {
            setLoadingTrends(true);

            // 트렌드 목록과 상단 통계는 독립적으로 실패할 수 있으므로 allSettled로 분리 처리합니다.
            const [trendResult, statsResult] = await Promise.allSettled([
                fetchTrends(selectedCategory),
                fetchTrendStats(selectedCategory),
            ]);

            if (!isMounted) {
                return;
            }

            if (trendResult.status === 'fulfilled') {
                setTrends(trendResult.value);
            } else {
                console.error('트렌드 데이터를 가져오는 중 오류 발생:', trendResult.reason);
                setTrends([]);
            }

            if (statsResult.status === 'fulfilled') {
                setStats(statsResult.value);
            } else {
                console.error('24시간 통계 데이터를 가져오는 중 오류 발생:', statsResult.reason);
                setStats(null);
            }

            setLoadingTrends(false);
        };

        fetchTrendsData();

        return () => {
            isMounted = false;
        };
    }, [selectedCategory]);

    const handleSelectKeyword = async (item) => {
        if (selected?.id === item.id) {
            setSelected(null);
            setArticles([]);
            return;
        }

        setSelected(item);
        setLoadingArticles(true);
        setArticles([]);

        try {
            const [articleRows, historyRows] = await Promise.all([
                fetchKeywordArticles(item.keyword),
                fetchKeywordHistory(item.keyword),
            ]);

            setArticles(articleRows);
            setSelected((prev) => ({ ...prev, history: historyRows }));
        } catch (error) {
            console.error('기사 또는 히스토리 데이터를 가져오는 중 오류 발생:', error);
        } finally {
            setLoadingArticles(false);
        }
    };

    function handleCloseSidebar() {
        setSelected(null);
        setArticles([]);
    }

    const filteredTrends = useMemo(
        () => (selectedCategory === 'ALL' ? trends : trends.filter((trend) => trend.category === selectedCategory)),
        [trends, selectedCategory]
    );

    // 정상 상황에서는 백엔드가 계산한 최근 24시간 통계를 사용하고, API 장애 시 기존 Top20 기반 계산값을 fallback으로 사용합니다.
    const dashboardStats = useMemo(() => stats ?? buildTrendStats(trends), [stats, trends]);

    return (
        <div id="dashboard" className="min-h-screen bg-slate-50 text-slate-900" style={{ fontFamily: "'Inter', system-ui, sans-serif" }}>
            <div className="flex min-h-screen">
                <SidebarNav
                    isOpen={isMenuOpen}
                    onToggle={() => setIsMenuOpen((prev) => !prev)}
                    stats={dashboardStats}
                />

                <div className="min-w-0 flex-1">
                    <DashboardHeader
                        updatedAt={updatedAt}
                        onToggleMenu={() => setIsMenuOpen((prev) => !prev)}
                    />

                    <main className="mx-auto w-full max-w-[1440px] px-4 py-5 sm:px-6 lg:px-8">
                        <StatsStrip stats={dashboardStats} />

                        <CategoryFilter
                            selectedCategory={selectedCategory}
                            setSelectedCategory={setSelectedCategory}
                            trends={trends}
                        />

                        <section className="grid gap-6 py-6 xl:grid-cols-[minmax(0,1fr)_420px]">
                            <div className="min-w-0 space-y-6">
                                <VolatilityPanel trends={filteredTrends} />

                                <TrendRankingList
                                    filteredTrends={filteredTrends}
                                    loadingTrends={loadingTrends}
                                    selectedId={selected?.id}
                                    onSelectKeyword={handleSelectKeyword}
                                />
                            </div>

                            <div className="space-y-6">
                                <ArticleSidebar
                                    selected={selected}
                                    articles={articles}
                                    loadingArticles={loadingArticles}
                                    onClose={handleCloseSidebar}
                                />

                                {/* 챗봇은 서버가 필요해 static 모드에서는 숨깁니다. */}
                                {!isStaticMode() && <TrendChatbot trends={filteredTrends} />}
                            </div>
                        </section>
                    </main>
                </div>
            </div>
        </div>
    );
}

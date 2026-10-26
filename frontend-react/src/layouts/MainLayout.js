import React, { useCallback, useEffect, useMemo, useRef, useState } from 'react';
import { Outlet } from 'react-router-dom';

import DashboardHeader from '../components/DashboardHeader';
import SidebarNav from '../components/SidebarNav';
import StaticFreshnessBanner from '../components/StaticFreshnessBanner';
import { useTrends } from '../hooks/useTrends';
import { fetchTrendStats } from '../api/trendApi';
import { buildTrendStats } from '../utils/trendUtils';

const REFRESH_INTERVAL_MS = 5 * 60 * 1000;

function formatQueryTime() {
    return new Date().toLocaleTimeString('ko-KR', {
        hour: '2-digit',
        minute: '2-digit',
        second: '2-digit',
    });
}

export default function MainLayout() {
    const {
        trends: allTrends,
        loadingTrends: loadingAllTrends,
        refreshTrends,
    } = useTrends('ALL', { autoLoad: false });
    const [dashboardStats, setDashboardStats] = useState(null);
    const [updatedAt, setUpdatedAt] = useState('');
    const [isRefreshing, setIsRefreshing] = useState(false);
    const [isMenuOpen, setIsMenuOpen] = useState(() => (
        typeof window !== 'undefined' ? window.innerWidth >= 1024 : true
    ));
    const mountedRef = useRef(true);
    const pageRefreshHandlerRef = useRef(null);
    const pageGenerationRef = useRef(0);
    const refreshPromiseRef = useRef(null);
    const refreshQueuedRef = useRef(false);

    // 라우팅 이후에도 전체 화면에서 동일한 폰트를 사용하도록 레이아웃에서 한 번만 로드합니다.
    useEffect(() => {
        const link = document.createElement('link');
        link.rel = 'stylesheet';
        link.href =
            'https://fonts.googleapis.com/css2?family=Space+Grotesk:wght@500;700&family=Inter:wght@400;500;600;700&family=JetBrains+Mono:wght@400;500;600&display=swap';
        document.head.appendChild(link);

        return () => document.head.removeChild(link);
    }, []);

    useEffect(() => {
        mountedRef.current = true;
        return () => {
            mountedRef.current = false;
        };
    }, []);

    const loadDashboardStats = useCallback(() => (
        fetchTrendStats('ALL')
            .then((result) => {
                if (mountedRef.current) {
                    setDashboardStats(result);
                }
                return result;
            })
            .catch((error) => {
                console.error('대시보드 통계 조회 실패:', error);
                throw error;
            })
    ), []);

    const requestRefresh = useCallback(() => {
        if (refreshPromiseRef.current) {
            return refreshPromiseRef.current;
        }

        setIsRefreshing(true);
        const pageRefresh = pageRefreshHandlerRef.current;
        const pageGeneration = pageGenerationRef.current;
        const tasks = [refreshTrends(), loadDashboardStats()];
        if (pageRefresh) {
            tasks.push(Promise.resolve().then(pageRefresh));
        }

        const request = Promise.allSettled(tasks)
            .then((results) => {
                const failure = results.find((result) => result.status === 'rejected');
                if (failure) {
                    throw failure.reason;
                }
                if (mountedRef.current && pageGeneration === pageGenerationRef.current) {
                    setUpdatedAt(formatQueryTime());
                }
            })
            .catch((error) => {
                console.error('대시보드 새로고침 실패:', error);
            })
            .finally(() => {
                if (mountedRef.current) {
                    setIsRefreshing(false);
                }
                if (refreshPromiseRef.current === request) {
                    refreshPromiseRef.current = null;
                }
                if (mountedRef.current && refreshQueuedRef.current) {
                    refreshQueuedRef.current = false;
                    requestRefresh();
                }
            });

        refreshPromiseRef.current = request;
        return request;
    }, [loadDashboardStats, refreshTrends]);

    const registerPageRefresh = useCallback((handler) => {
        pageGenerationRef.current += 1;
        pageRefreshHandlerRef.current = handler;
        setUpdatedAt('');

        if (refreshPromiseRef.current) {
            refreshQueuedRef.current = true;
        } else {
            requestRefresh();
        }

        return () => {
            if (pageRefreshHandlerRef.current === handler) {
                pageRefreshHandlerRef.current = null;
                pageGenerationRef.current += 1;
            }
        };
    }, [requestRefresh]);

    useEffect(() => {
        requestRefresh();
    }, [requestRefresh]);

    useEffect(() => {
        const refreshTimer = setInterval(() => {
            if (document.visibilityState === 'visible') {
                requestRefresh();
            }
        }, REFRESH_INTERVAL_MS);
        const handleVisibilityChange = () => {
            if (document.visibilityState === 'visible') {
                requestRefresh();
            }
        };

        document.addEventListener('visibilitychange', handleVisibilityChange);
        return () => {
            clearInterval(refreshTimer);
            document.removeEventListener('visibilitychange', handleVisibilityChange);
        };
    }, [requestRefresh]);

    const fallbackStats = useMemo(() => buildTrendStats(allTrends), [allTrends]);
    const stats = dashboardStats ?? fallbackStats;

    return (
        <div id="dashboard" className="min-h-screen bg-slate-50 text-slate-900" style={{ fontFamily: "'Inter', system-ui, sans-serif" }}>
            <div className="flex min-h-screen">
                <SidebarNav
                    isOpen={isMenuOpen}
                    onToggle={() => setIsMenuOpen((prev) => !prev)}
                    stats={stats}
                />

                <div className="min-w-0 flex-1">
                    <DashboardHeader
                        updatedAt={updatedAt}
                        isRefreshing={isRefreshing}
                        onRefresh={requestRefresh}
                        onToggleMenu={() => setIsMenuOpen((prev) => !prev)}
                    />

                    {/* 사이드바 메뉴 또는 키워드 클릭에 따라 이 영역의 페이지가 교체됩니다. */}
                    <main className="mx-auto w-full max-w-[1440px] px-4 py-5 sm:px-6 lg:px-8">
                        <StaticFreshnessBanner />
                        <Outlet
                            context={{
                                allTrends,
                                loadingAllTrends,
                                stats,
                                updatedAt,
                                registerPageRefresh,
                            }}
                        />
                    </main>
                </div>
            </div>
        </div>
    );
}

import React, { useCallback, useEffect, useMemo, useRef, useState } from 'react';
import { useNavigate, useOutletContext, useParams } from 'react-router-dom';

import CategoryFilter from '../components/CategoryFilter';
import StatsStrip from '../components/StatsStrip';
import TrendRankingList from '../components/TrendRankingList';
import VolatilityPanel from '../components/VolatilityPanel';
import { fetchTrendStats } from '../api/trendApi';
import { useTrends } from '../hooks/useTrends';
import { buildTrendStats, getCategoryBySlug, getCategorySlugById } from '../utils/trendUtils';

function resolveStaticCategory(categorySlug) {
    if (!categorySlug || categorySlug === 'all') {
        return null;
    }

    const category = getCategoryBySlug(categorySlug);
    return category.id === 'ALL' ? null : category;
}

export default function CategoryPage() {
    const navigate = useNavigate();
    const { registerPageRefresh } = useOutletContext() ?? {};
    const { categorySlug } = useParams();
    const [selectedCategoryOption, setSelectedCategoryOption] = useState(() =>
        resolveStaticCategory(categorySlug)
    );
    const [categoryStats, setCategoryStats] = useState(null);
    const categoryIdRef = useRef(null);
    const statsRequestRef = useRef(null);
    const mountedRef = useRef(true);

    useEffect(() => {
        mountedRef.current = true;
        return () => {
            mountedRef.current = false;
        };
    }, []);

    useEffect(() => {
        if (!categorySlug || categorySlug === 'all') {
            setSelectedCategoryOption(null);
            return;
        }

        setSelectedCategoryOption((current) => {
            if (current?.slug === categorySlug) {
                return current;
            }

            return resolveStaticCategory(categorySlug);
        });
    }, [categorySlug]);

    const hasSelectedCategory = Boolean(selectedCategoryOption);
    const { trends, loadingTrends, refreshTrends } = useTrends(
        selectedCategoryOption?.id,
        { enabled: hasSelectedCategory }
    );
    const fallbackStats = useMemo(() => buildTrendStats(trends), [trends]);
    const stats = categoryStats ?? fallbackStats;

    const loadCategoryStats = useCallback((reset = false) => {
        if (!hasSelectedCategory) {
            setCategoryStats(null);
            return Promise.resolve(null);
        }

        if (statsRequestRef.current) {
            return statsRequestRef.current;
        }

        const categoryId = selectedCategoryOption.id;
        if (reset) {
            setCategoryStats(null);
        }

        const request = fetchTrendStats(categoryId)
            .then((result) => {
                if (mountedRef.current && categoryIdRef.current === categoryId) {
                    setCategoryStats(result);
                }
                return result;
            })
            .catch((error) => {
                console.error('카테고리 통계 조회 실패:', error);
                throw error;
            })
            .finally(() => {
                if (statsRequestRef.current === request) {
                    statsRequestRef.current = null;
                }
            });

        statsRequestRef.current = request;
        return request;
    }, [hasSelectedCategory, selectedCategoryOption?.id]);

    useEffect(() => {
        categoryIdRef.current = selectedCategoryOption?.id ?? null;
        statsRequestRef.current = null;
        loadCategoryStats(true).catch(() => {});
    }, [loadCategoryStats, selectedCategoryOption?.id]);

    const refreshCategoryPage = useCallback(() => (
        Promise.allSettled([refreshTrends(), loadCategoryStats()])
            .then((results) => {
                const failure = results.find((result) => result.status === 'rejected');
                if (failure) {
                    throw failure.reason;
                }
            })
    ), [loadCategoryStats, refreshTrends]);

    useEffect(() => {
        if (!registerPageRefresh || !hasSelectedCategory) {
            return undefined;
        }
        return registerPageRefresh(refreshCategoryPage);
    }, [hasSelectedCategory, refreshCategoryPage, registerPageRefresh]);

    const handleChangeCategory = (categoryId, category) => {
        const nextCategory = category || {
            id: categoryId,
            label: categoryId,
            slug: getCategorySlugById(categoryId),
        };

        setSelectedCategoryOption(nextCategory);
        navigate(`/categories/${nextCategory.slug}`);
    };

    return (
        <>
            <div className="mb-5 rounded-3xl border border-slate-200 bg-white p-6 shadow-sm">
                <p className="text-sm font-semibold text-blue-600">Category Trends</p>
                <h2 className="mt-1 text-2xl font-bold text-slate-950">카테고리 분석</h2>
                <p className="mt-2 text-sm text-slate-500">
                    카테고리를 선택하면 해당 분야 안에서 급상승하는 키워드와 Hot Score를 확인할 수 있습니다.
                </p>
            </div>

            <CategoryFilter
                selectedCategory={selectedCategoryOption?.id ?? null}
                setSelectedCategory={handleChangeCategory}
                trends={trends}
                includeAll={false}
            />

            {!hasSelectedCategory ? (
                <div className="mt-6 rounded-3xl border border-dashed border-slate-200 bg-white px-6 py-16 text-center shadow-sm">
                    <p className="text-sm font-semibold text-slate-500">분석할 카테고리를 먼저 선택해주세요.</p>
                    <p className="mt-2 text-sm text-slate-400">
                        전체 통합 순위는 인기 키워드 화면에서 확인할 수 있습니다.
                    </p>
                </div>
            ) : (
                <section className="space-y-6 py-6">
                    <StatsStrip stats={stats} />
                    <VolatilityPanel trends={trends} />
                    <TrendRankingList
                        filteredTrends={trends}
                        loadingTrends={loadingTrends}
                        selectedId={null}
                        onSelectKeyword={(item) => navigate(`/keywords/${encodeURIComponent(item.keyword)}`)}
                        eyebrow="Category Keywords"
                        title={`${selectedCategoryOption.label} 키워드 TOP ${trends.length}`}
                        emptyMessage="선택한 카테고리에는 아직 트렌드 데이터가 없습니다."
                    />
                </section>
            )}
        </>
    );
}

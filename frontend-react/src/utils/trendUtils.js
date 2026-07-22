// 트렌드 화면 전반에서 공통으로 사용하는 카테고리/정규화 유틸입니다.
// API 응답 필드명이 camelCase 또는 snake_case로 섞여 와도 화면 컴포넌트가 동일한 형태로 사용할 수 있게 맞춰줍니다.

// 기존 화면의 색상 톤을 유지하기 위한 기본 메타데이터입니다.
// 실제 카테고리 목록은 백엔드 API에서 받아오며, 이 값은 API 실패 시 fallback 또는 기존 카테고리 색상 유지 용도로만 사용합니다.
export const CATEGORY_META = {
    'IT/과학': { hex: '#2563eb', text: 'text-blue-700', slug: 'it-science' },
    '경제': { hex: '#059669', text: 'text-emerald-700', slug: 'economy' },
};

// 새 카테고리가 추가됐을 때도 화면에서 구분되도록 순환 적용할 색상 팔레트입니다.
const CATEGORY_PALETTE = [
    { hex: '#2563eb', text: 'text-blue-700' },
    { hex: '#059669', text: 'text-emerald-700' },
    { hex: '#7c3aed', text: 'text-violet-700' },
    { hex: '#dc2626', text: 'text-red-700' },
    { hex: '#d97706', text: 'text-amber-700' },
    { hex: '#0891b2', text: 'text-cyan-700' },
    { hex: '#be185d', text: 'text-pink-700' },
    { hex: '#4f46e5', text: 'text-indigo-700' },
];

export const ALL_CATEGORY = { id: 'ALL', label: '전체', slug: 'all' };

function toCategorySlug(categoryName = '', index = 0) {
    const normalized = String(categoryName)
        .trim()
        .toLowerCase()
        .replace(/[\s/]+/g, '-')
        .replace(/[^\w가-힣-]/g, '')
        .replace(/-+/g, '-');

    return normalized || `category-${index + 1}`;
}

function toNumber(value, fallback = 0) {
    const parsed = Number(value);
    return Number.isFinite(parsed) ? parsed : fallback;
}

export function createCategoryMeta(categoryName, index = 0) {
    const fallbackMeta = CATEGORY_META[categoryName];
    if (fallbackMeta) {
        return fallbackMeta;
    }

    const palette = CATEGORY_PALETTE[index % CATEGORY_PALETTE.length];
    return {
        ...palette,
        slug: toCategorySlug(categoryName, index),
    };
}

export function buildCategoryOption(rawCategory, index = 0) {
    const isObject = rawCategory && typeof rawCategory === 'object';
    const id = String(
        isObject
            ? rawCategory.id ?? rawCategory.category ?? rawCategory.label ?? ''
            : rawCategory
    ).trim();

    if (!id || id === 'ALL') {
        return null;
    }

    const meta = createCategoryMeta(id, index);
    const trendCount = Number(
        isObject
            ? rawCategory.trendCount ?? rawCategory.count ?? rawCategory.mentionCount ?? 0
            : 0
    );

    return {
        id,
        label: String(isObject ? rawCategory.label ?? id : id).trim(),
        slug: isObject ? rawCategory.slug ?? meta.slug : meta.slug,
        hex: isObject ? rawCategory.hex ?? meta.hex : meta.hex,
        text: isObject ? rawCategory.text ?? meta.text : meta.text,
        trendCount: Number.isFinite(trendCount) ? trendCount : 0,
    };
}

export function normalizeCategoryList(categoryRows = []) {
    const rows = Array.isArray(categoryRows) ? categoryRows : [];
    const categoryMap = new Map();

    rows.forEach((row, index) => {
        const category = buildCategoryOption(row, index);
        if (category) {
            categoryMap.set(category.id, category);
        }
    });

    const dynamicCategories = Array.from(categoryMap.values());
    if (!dynamicCategories.length) {
        return [
            ALL_CATEGORY,
            ...Object.keys(CATEGORY_META).map((id, index) => buildCategoryOption({ id, label: id }, index)),
        ];
    }

    const totalTrendCount = dynamicCategories.reduce(
        (sum, category) => sum + Number(category.trendCount ?? 0),
        0
    );

    return [
        { ...ALL_CATEGORY, trendCount: totalTrendCount },
        ...dynamicCategories,
    ];
}

// API가 아직 응답하지 못한 초기 렌더링 또는 장애 상황에서 사용하는 fallback 카테고리입니다.
export const CATEGORIES = normalizeCategoryList(
    Object.keys(CATEGORY_META).map((id) => ({ id, label: id }))
);

export function normalizeTrendItem(item, index) {
    const velocity = Number(item.velocityScore ?? item.velocity_score ?? item.changeValue ?? 0);
    const mentionCount = Number(item.mentionCount ?? item.mention_count ?? 0);
    const score = Number(item.hotnessScore ?? item.score ?? 0);

    return {
        ...item,
        id: item.id ?? `${item.keyword}-${index}`,
        rank: item.rank ?? index + 1,
        mentionCount,
        mention_count: mentionCount,
        velocityScore: velocity,
        velocity_score: velocity,
        score,
        hotnessScore: score,
        changeValue: item.changeValue ?? velocity,
        changeType: item.changeType ?? (velocity > 0 ? 'up' : velocity < 0 ? 'down' : 'same'),
    };
}

function normalizeKeywordChange(rawKeyword) {
    if (!rawKeyword || !rawKeyword.keyword) {
        return null;
    }

    return {
        keyword: String(rawKeyword.keyword),
        mentionCount: toNumber(rawKeyword.mentionCount ?? rawKeyword.mention_count),
        changeAmount: toNumber(rawKeyword.changeAmount ?? rawKeyword.change_amount),
    };
}

export function normalizeTrendStats(rawStats = {}) {
    return {
        analyzedArticles: toNumber(rawStats.analyzedArticles ?? rawStats.analyzed_articles),
        trackedKeywords: toNumber(rawStats.trackedKeywords ?? rawStats.tracked_keywords),
        risingKeyword: normalizeKeywordChange(rawStats.risingKeyword ?? rawStats.rising_keyword),
        fallingKeyword: normalizeKeywordChange(rawStats.fallingKeyword ?? rawStats.falling_keyword),
        windowHours: toNumber(rawStats.windowHours ?? rawStats.window_hours, 24),
    };
}

export function buildTrendStats(trends = []) {
    if (!trends.length) return null;

    const totalMentions = trends.reduce((sum, trend) => sum + Number(trend.mentionCount ?? 0), 0);
    const totalVolatility = trends.reduce((sum, trend) => sum + Math.abs(Number(trend.velocityScore ?? 0)), 0);

    return {
        // API 장애 시 화면이 완전히 비지 않도록 유지하는 fallback 값입니다.
        mentions: totalMentions,
        tracked: trends.length,
        rising: trends.filter((trend) => trend.changeType === 'up').length,
        falling: trends.filter((trend) => trend.changeType === 'down').length,
        averageVolatility: trends.length ? totalVolatility / trends.length : 0,
        windowHours: 24,
    };
}

export function getCategoryBySlug(slug = 'all', categories = CATEGORIES) {
    return categories.find((category) => category.slug === slug) ?? categories[0] ?? ALL_CATEGORY;
}

export function getCategorySlugById(categoryId = 'ALL', categories = CATEGORIES) {
    return categories.find((category) => category.id === categoryId)?.slug ?? 'all';
}

export function findTrendByKeyword(trends = [], keyword = '') {
    const decodedKeyword = decodeURIComponent(keyword).trim();
    return trends.find((trend) => trend.keyword === decodedKeyword);
}

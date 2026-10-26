import { getStaticDataBase } from '../config/dataMode';
import { buildTrendStats, normalizeCategoryList, normalizeTrendItem, normalizeTrendStats } from '../utils/trendUtils';

// v2 static 모드에서 trendApi.js 대신 쓰는 구현입니다.
// GitHub Actions가 미리 계산해 둔 정적 JSON(contracts/site)을 읽어 Spring API와 같은 모양으로 돌려줍니다.
// 그래서 페이지·훅은 API 모드와 static 모드를 구분하지 않고 같은 함수를 호출합니다.
//
// 엔드포인트 대응 (docs/v2/DESIGN.md 6절)
//   /categories            -> categories.json
//   /trends, /category     -> trends/all.json, trends/category/<slug>.json
//   /popular, /surging     -> trends/popular.json, trends/surging/all.json (limit은 여기서 자름)
//   /stats                 -> stats/all.json, stats/<slug>.json
//   /articles, /history    -> keywords/<slug>.json
//   /history/compare       -> 두 키워드 파일을 받아 브라우저에서 계산
//   /history/evidence      -> 두 키워드 파일의 evidenceByDay[date]

export { buildTrendStats };

const TREND_ZONE = 'Asia/Seoul';
const MIN_HISTORY_DAYS = 2;
const MAX_HISTORY_DAYS = 30;
const MIN_EVIDENCE_LIMIT = 1;
const MAX_EVIDENCE_LIMIT = 5;
const SAME_CANONICAL_MESSAGE = '두 입력은 같은 대표 키워드로 해석되어 비교할 수 없습니다. 서로 다른 키워드를 입력해주세요.';

// 한 번 받은 파일은 새로고침 전까지 메모리에 둡니다. 실패한 요청은 다음 호출에서 다시 받습니다.
const jsonCache = new Map();

export function clearStaticDataCache() {
    jsonCache.clear();
}

// 화면의 오류 처리(error.response.status, error.response.data.detail ?? message)가 그대로 동작하도록
// axios 오류와 같은 모양으로 만듭니다. data는 Spring ProblemDetail 형식을 따릅니다.
function createHttpError(status, detail) {
    const title = status === 400 ? 'Bad Request' : status === 404 ? 'Not Found' : 'Error';
    const error = new Error(detail);
    error.name = 'StaticDataError';
    error.isAxiosError = true;
    error.response = {
        status,
        statusText: title,
        data: { type: 'about:blank', title, status, detail, message: detail },
    };
    return error;
}

function loadJson(path) {
    if (jsonCache.has(path)) {
        return jsonCache.get(path);
    }

    const url = `${getStaticDataBase()}/${path}`;
    const request = fetch(url)
        .then((response) => {
            if (!response.ok) {
                throw createHttpError(response.status, `정적 데이터를 불러오지 못했습니다: ${path}`);
            }
            return response.json();
        })
        .catch((error) => {
            jsonCache.delete(path);
            throw error;
        });

    jsonCache.set(path, request);
    return request;
}

// ---------------------------------------------------------------- 운영 메타데이터 (static 전용)

export function fetchSiteMeta() {
    return loadJson('meta.json');
}

export function fetchRecentRuns() {
    return loadJson('runs/recent.json').then((data) => data?.runs ?? []);
}

// ---------------------------------------------------------------- 키워드 해석

// v1 KeywordNormalizer.normalize와 같은 규칙입니다.
export function normalizeKeyword(keyword) {
    if (keyword == null) {
        return '';
    }

    return String(keyword)
        .trim()
        .toLowerCase()
        .replace(/\s+/g, '')
        .replace(/\./g, '')
        .replace(/-/g, '');
}

function requireKeyword(keyword) {
    if (keyword == null || String(keyword).trim() === '') {
        throw createHttpError(400, '키워드는 비어 있을 수 없습니다.');
    }
    return String(keyword).trim();
}

// 입력 키워드 -> 대표 키워드. 색인에 없으면 입력을 그대로 대표 키워드로 봅니다(v1 resolveKeyword와 같음).
async function resolveCanonicalKeyword(keyword) {
    const index = await loadJson('keywords/index.json');
    return (index.aliasToCanonical?.[normalizeKeyword(keyword)] ?? keyword).trim();
}

// 대표 키워드의 상세 파일. 색인에 없는 키워드는 null(= 수집된 데이터 없음)입니다.
async function loadKeywordDetail(canonicalKeyword) {
    const index = await loadJson('keywords/index.json');
    const entry = (index.keywords ?? []).find((item) => item.keyword === canonicalKeyword);
    return entry ? loadJson(`keywords/${entry.slug}.json`) : null;
}

// ---------------------------------------------------------------- 카테고리

async function findCategorySlug(categoryName) {
    const categories = await loadJson('categories.json');
    const name = String(categoryName ?? '').trim();
    return categories.find((category) => category.id === name || category.label === name)?.slug ?? null;
}

function isAllCategory(categoryName) {
    return !categoryName || String(categoryName).trim() === '' || String(categoryName).toUpperCase() === 'ALL';
}

export async function fetchCategories() {
    const categories = await loadJson('categories.json');
    // 파일의 slug(해시)는 파일 경로용입니다. 화면 URL은 API 모드와 같은 slug(it-science 등)를 쓰도록 뺍니다.
    return normalizeCategoryList(categories.map(({ slug, ...category }) => category));
}

// ---------------------------------------------------------------- 트렌드 목록·통계

function toTrendList(rows) {
    return (rows ?? []).map((item, index) => normalizeTrendItem(item, index));
}

// v1 TrendService.clampLimit과 같습니다: 0 이하이면 기본값, 최대 50.
function clampLimit(limit, defaultLimit) {
    const parsed = Number(limit);
    if (!Number.isFinite(parsed) || parsed <= 0) {
        return defaultLimit;
    }
    return Math.min(Math.trunc(parsed), 50);
}

export async function fetchTrends(categoryName = 'ALL') {
    if (isAllCategory(categoryName)) {
        return toTrendList(await loadJson('trends/all.json'));
    }

    const slug = await findCategorySlug(categoryName);
    return slug ? toTrendList(await loadJson(`trends/category/${slug}.json`)) : [];
}

export async function fetchPopularTrends(limit = 20) {
    const rows = await loadJson('trends/popular.json');
    return toTrendList(rows.slice(0, clampLimit(limit, 20)));
}

export async function fetchSurgingTrends(limit = 10) {
    const rows = await loadJson('trends/surging/all.json');
    return toTrendList(rows.slice(0, clampLimit(limit, 10)));
}

export async function fetchTrendStats(categoryName = 'ALL') {
    if (isAllCategory(categoryName)) {
        return normalizeTrendStats(await loadJson('stats/all.json'));
    }

    const slug = await findCategorySlug(categoryName);
    return normalizeTrendStats(slug ? await loadJson(`stats/${slug}.json`) : {});
}

// ---------------------------------------------------------------- 키워드 상세·추이·비교

export async function fetchKeywordArticles(keyword) {
    const canonicalKeyword = await resolveCanonicalKeyword(requireKeyword(keyword));
    const detail = await loadKeywordDetail(canonicalKeyword);
    return detail?.articles ?? [];
}

function validateHistoryDays(days) {
    const parsed = Number(days);
    if (!Number.isInteger(parsed) || parsed < MIN_HISTORY_DAYS || parsed > MAX_HISTORY_DAYS) {
        throw createHttpError(400, 'days는 2~30 사이여야 합니다.');
    }
    return parsed;
}

function validateEvidenceLimit(limit) {
    const parsed = Number(limit);
    if (!Number.isInteger(parsed) || parsed < MIN_EVIDENCE_LIMIT || parsed > MAX_EVIDENCE_LIMIT) {
        throw createHttpError(400, 'limit는 1~5 사이여야 합니다.');
    }
    return parsed;
}

// 오늘(서울)은 브라우저 시계가 아니라 배포본의 기준 시각 meta.asOf로 정합니다.
async function loadToday() {
    const meta = await fetchSiteMeta();
    return String(meta.asOf).slice(0, 10);
}

function shiftDay(day, offset) {
    const date = new Date(`${day}T00:00:00Z`);
    date.setUTCDate(date.getUTCDate() + offset);
    return date.toISOString().slice(0, 10);
}

// v1 buildKeywordHistory와 같은 모양: today-(days-1) ~ today, 기사 없는 날은 0, 오늘은 partial.
function buildHistory(detail, today, days) {
    const pointByDay = new Map((detail?.daily ?? []).map((point) => [point.day, point]));
    const history = [];
    for (let offset = days - 1; offset >= 0; offset -= 1) {
        const day = shiftDay(today, -offset);
        const point = pointByDay.get(day);
        history.push({
            day,
            articleCount: Number(point?.articleCount ?? 0),
            weightedScore: Number(point?.weightedScore ?? 0),
            partial: day === today,
        });
    }
    return history;
}

export async function fetchKeywordHistory(keyword, days = 7) {
    const parsedDays = validateHistoryDays(days);
    const canonicalKeyword = await resolveCanonicalKeyword(requireKeyword(keyword));
    const [detail, today] = await Promise.all([loadKeywordDetail(canonicalKeyword), loadToday()]);
    return buildHistory(detail, today, parsedDays);
}

async function resolveComparisonPair(firstKeyword, secondKeyword) {
    const firstRequestedKeyword = requireKeyword(firstKeyword);
    const secondRequestedKeyword = requireKeyword(secondKeyword);
    const [firstCanonicalKeyword, secondCanonicalKeyword] = await Promise.all([
        resolveCanonicalKeyword(firstRequestedKeyword),
        resolveCanonicalKeyword(secondRequestedKeyword),
    ]);

    // v1은 equalsIgnoreCase로 비교합니다.
    if (firstCanonicalKeyword.toLowerCase() === secondCanonicalKeyword.toLowerCase()) {
        throw createHttpError(400, SAME_CANONICAL_MESSAGE);
    }

    return { firstRequestedKeyword, secondRequestedKeyword, firstCanonicalKeyword, secondCanonicalKeyword };
}

export async function fetchKeywordHistoryComparison(firstKeyword, secondKeyword, days = 7) {
    const parsedDays = validateHistoryDays(days);
    const pair = await resolveComparisonPair(firstKeyword, secondKeyword);
    const [firstDetail, secondDetail, today] = await Promise.all([
        loadKeywordDetail(pair.firstCanonicalKeyword),
        loadKeywordDetail(pair.secondCanonicalKeyword),
        loadToday(),
    ]);

    return {
        ...pair,
        days: parsedDays,
        timezone: TREND_ZONE,
        todayPartial: true,
        firstHistory: buildHistory(firstDetail, today, parsedDays),
        secondHistory: buildHistory(secondDetail, today, parsedDays),
    };
}

export async function fetchKeywordHistoryEvidence(firstKeyword, secondKeyword, date, limit = 5) {
    const parsedLimit = validateEvidenceLimit(limit);
    if (!date) {
        throw createHttpError(400, 'date는 필수입니다.');
    }
    if (!/^\d{4}-\d{2}-\d{2}$/.test(String(date))) {
        throw createHttpError(400, 'date는 YYYY-MM-DD 형식이어야 합니다.');
    }

    const pair = await resolveComparisonPair(firstKeyword, secondKeyword);
    const [firstDetail, secondDetail] = await Promise.all([
        loadKeywordDetail(pair.firstCanonicalKeyword),
        loadKeywordDetail(pair.secondCanonicalKeyword),
    ]);
    const pickEvidence = (detail) => (detail?.evidenceByDay?.[date] ?? []).slice(0, parsedLimit);

    return {
        date: String(date),
        timezone: TREND_ZONE,
        firstCanonicalKeyword: pair.firstCanonicalKeyword,
        secondCanonicalKeyword: pair.secondCanonicalKeyword,
        firstArticles: pickEvidence(firstDetail),
        secondArticles: pickEvidence(secondDetail),
    };
}

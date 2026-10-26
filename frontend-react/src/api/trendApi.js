import axios from 'axios';
import { buildApiUrl } from '../utils/apiBaseUrl';
import { buildTrendStats, normalizeCategoryList, normalizeTrendItem, normalizeTrendStats } from '../utils/trendUtils';
import { isStaticMode } from '../config/dataMode';
import * as staticTrendApi from './staticTrendApi';

// 트렌드 관련 API의 기본 URL입니다.
// 운영 환경에서는 Nginx 프록시를 통해 /api 경로가 백엔드로 전달됩니다.
const TRENDS_API_BASE = buildApiUrl('/api/v1/trends');

// 페이지 컴포넌트는 API 함수와 통계 계산 함수를 한 곳에서 가져올 수 있습니다.
export { buildTrendStats };

// REACT_APP_DATA_MODE=static 빌드(v2, GitHub Pages)에서는 서버 대신 정적 JSON을 읽는 구현으로 넘깁니다.
// 반환 형태는 같으므로 페이지·훅은 모드를 몰라도 됩니다.

// 백엔드 DB 기준 카테고리 목록을 조회합니다.
// 새 크롤링 카테고리가 추가되면 이 API 응답을 통해 프론트 필터가 자동으로 확장됩니다.
export async function fetchCategories() {
    if (isStaticMode()) return staticTrendApi.fetchCategories();

    const response = await axios.get(`${TRENDS_API_BASE}/categories`);
    return normalizeCategoryList(response.data);
}

// 전체 또는 카테고리별 트렌드 목록을 조회합니다.
// categoryName이 ALL이면 전체 트렌드 API를, 특정 카테고리면 카테고리 API를 호출합니다.
export async function fetchTrends(categoryName = 'ALL') {
    if (isStaticMode()) return staticTrendApi.fetchTrends(categoryName);

    const isAllCategory = !categoryName || categoryName === 'ALL';
    const url = isAllCategory ? TRENDS_API_BASE : `${TRENDS_API_BASE}/category`;

    const response = await axios.get(url, {
        params: isAllCategory ? {} : { categoryName },
    });

    return response.data.map((item, index) => normalizeTrendItem(item, index));
}

export async function fetchPopularTrends(limit = 20) {
    if (isStaticMode()) return staticTrendApi.fetchPopularTrends(limit);

    const response = await axios.get(`${TRENDS_API_BASE}/popular`, {
        params: { limit },
    });

    return response.data.map((item, index) => normalizeTrendItem(item, index));
}

export async function fetchSurgingTrends(limit = 10) {
    if (isStaticMode()) return staticTrendApi.fetchSurgingTrends(limit);

    const response = await axios.get(`${TRENDS_API_BASE}/surging`, {
        params: { limit },
    });

    return response.data.map((item, index) => normalizeTrendItem(item, index));
}

// 프론트엔드 상단 카드에 사용할 최근 24시간 기준 통계를 조회합니다.
// 카테고리가 선택된 경우 해당 카테고리의 24시간 통계만 요청합니다.
export async function fetchTrendStats(categoryName = 'ALL') {
    if (isStaticMode()) return staticTrendApi.fetchTrendStats(categoryName);

    const isAllCategory = !categoryName || categoryName === 'ALL';
    const response = await axios.get(`${TRENDS_API_BASE}/stats`, {
        params: isAllCategory ? {} : { categoryName },
    });

    return normalizeTrendStats(response.data);
}

// 선택한 키워드와 연결된 최신 기사 목록을 조회합니다.
export async function fetchKeywordArticles(keyword) {
    if (isStaticMode()) return staticTrendApi.fetchKeywordArticles(keyword);

    const response = await axios.get(`${TRENDS_API_BASE}/articles`, {
        params: { keyword },
    });

    return response.data;
}

// 선택한 키워드의 최근 7일 점수 추이를 조회합니다.
export async function fetchKeywordHistory(keyword, days = 7) {
    if (isStaticMode()) return staticTrendApi.fetchKeywordHistory(keyword, days);

    const response = await axios.get(`${TRENDS_API_BASE}/history`, {
        params: { keyword, days },
    });

    return response.data;
}

// 두 키워드를 같은 조회 시각과 날짜 범위로 비교합니다.
export async function fetchKeywordHistoryComparison(firstKeyword, secondKeyword, days = 7) {
    if (isStaticMode()) return staticTrendApi.fetchKeywordHistoryComparison(firstKeyword, secondKeyword, days);

    const response = await axios.get(`${TRENDS_API_BASE}/history/compare`, {
        params: { firstKeyword, secondKeyword, days },
    });

    return response.data;
}

// 선택한 날짜에 두 대표 키워드와 연결된 근거 기사 목록을 조회합니다.
export async function fetchKeywordHistoryEvidence(firstKeyword, secondKeyword, date, limit = 5) {
    if (isStaticMode()) return staticTrendApi.fetchKeywordHistoryEvidence(firstKeyword, secondKeyword, date, limit);

    const response = await axios.get(`${TRENDS_API_BASE}/history/evidence`, {
        params: { firstKeyword, secondKeyword, date, limit },
    });

    return response.data;
}

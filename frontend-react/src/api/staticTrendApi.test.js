import fs from 'fs';
import path from 'path';

import {
    clearStaticDataCache,
    fetchCategories,
    fetchKeywordArticles,
    fetchKeywordHistory,
    fetchKeywordHistoryComparison,
    fetchKeywordHistoryEvidence,
    fetchPopularTrends,
    fetchRecentRuns,
    fetchSiteMeta,
    fetchSurgingTrends,
    fetchTrendStats,
    fetchTrends,
    normalizeKeyword,
} from './staticTrendApi';

// 공용 고정 데이터(fixtures/site/data)를 그대로 읽어 fixtures/README.md의 기대값을 확인합니다.
const FIXTURE_DIR = path.resolve(__dirname, '../../../fixtures/site/data');
const SAME_CANONICAL_MESSAGE = '두 입력은 같은 대표 키워드로 해석되어 비교할 수 없습니다. 서로 다른 키워드를 입력해주세요.';

let overrides = {};
let requestedUrls = [];

function respond(status, body) {
    return Promise.resolve({
        ok: status >= 200 && status < 300,
        status,
        json: () => Promise.resolve(body),
    });
}

beforeEach(() => {
    process.env.REACT_APP_STATIC_DATA_BASE = '/base/data';
    overrides = {};
    requestedUrls = [];
    clearStaticDataCache();
    global.fetch = jest.fn((url) => {
        requestedUrls.push(url);
        const relative = url.replace('/base/data/', '');
        if (overrides[relative]) {
            return respond(200, overrides[relative]);
        }
        const file = path.join(FIXTURE_DIR, relative);
        if (!fs.existsSync(file)) {
            return respond(404, null);
        }
        return respond(200, JSON.parse(fs.readFileSync(file, 'utf8')));
    });
});

afterEach(() => {
    delete process.env.REACT_APP_STATIC_DATA_BASE;
    delete global.fetch;
});

async function expectBadRequest(promise, message) {
    await expect(promise).rejects.toMatchObject({
        response: {
            status: 400,
            data: { status: 400, detail: message, message },
        },
    });
}

describe('normalizeKeyword (v1 KeywordNormalizer와 같은 규칙)', () => {
    it.each([
        [' 생성형 AI ', '생성형ai'],
        ['A.I.', 'ai'],
        ['Artificial Intelligence', 'artificialintelligence'],
        ['generative-ai', 'generativeai'],
        [null, ''],
    ])('%p -> %p', (input, expected) => {
        expect(normalizeKeyword(input)).toBe(expected);
    });
});

describe('트렌드 목록·통계', () => {
    it('전체 목록 1위는 alias가 병합된 인공지능(score 3.4, mention 4)이다', async () => {
        const trends = await fetchTrends('ALL');

        expect(trends[0]).toMatchObject({
            keyword: '인공지능',
            category: 'IT/과학',
            rank: 1,
            score: 3.4,
            hotnessScore: 3.4,
            mentionCount: 4,
            changeType: 'up',
        });
        expect(trends.map((trend) => trend.keyword)).not.toContain('AI');
        expect(requestedUrls).toEqual(['/base/data/trends/all.json']);
    });

    it('카테고리 이름을 categories.json의 slug 파일로 찾는다', async () => {
        const trends = await fetchTrends('경제');

        expect(trends.length).toBeGreaterThan(0);
        expect(requestedUrls).toContain('/base/data/trends/category/b88882649917c44e.json');
    });

    it('없는 카테고리는 빈 목록이다', async () => {
        await expect(fetchTrends('스포츠')).resolves.toEqual([]);
    });

    it('카테고리 slug는 화면 URL용으로 API 모드와 같은 값을 쓴다', async () => {
        const categories = await fetchCategories();

        expect(categories.map((category) => [category.id, category.slug])).toEqual([
            ['ALL', 'all'],
            ['IT/과학', 'it-science'],
            ['경제', 'economy'],
        ]);
        expect(categories[0].trendCount).toBe(8);
    });

    it('인기·급상승 목록은 v1 clampLimit 규칙으로 자른다', async () => {
        await expect(fetchPopularTrends(2)).resolves.toHaveLength(2);
        await expect(fetchPopularTrends(0)).resolves.toHaveLength(5);
        await expect(fetchSurgingTrends(10)).resolves.toHaveLength(3);
        expect((await fetchSurgingTrends(1))[0].keyword).toBe('인공지능');
    });

    it('통계는 rising 인공지능(+3), falling 환율(-2)', async () => {
        await expect(fetchTrendStats()).resolves.toEqual({
            analyzedArticles: 6,
            trackedKeywords: 6,
            risingKeyword: { keyword: '인공지능', mentionCount: 4, changeAmount: 3 },
            fallingKeyword: { keyword: '환율', mentionCount: 1, changeAmount: -2 },
            windowHours: 24,
        });
    });

    it('없는 카테고리 통계는 0으로 채운다', async () => {
        await expect(fetchTrendStats('스포츠')).resolves.toMatchObject({
            analyzedArticles: 0,
            trackedKeywords: 0,
            risingKeyword: null,
        });
    });
});

describe('키워드 상세', () => {
    it('alias 입력(A.I.)도 대표 키워드 파일의 기사를 돌려준다', async () => {
        const articles = await fetchKeywordArticles(' A.I. ');

        expect(articles).toHaveLength(6);
        expect(articles[0]).toEqual(expect.objectContaining({ title: '고정 기사 14', source: '다음 뉴스' }));
        expect(requestedUrls).toContain('/base/data/keywords/c597b282778e3c88.json');
    });

    it('색인에 없는 키워드는 기사 빈 배열, 추이는 0으로 채운 N일이다', async () => {
        await expect(fetchKeywordArticles('없는키워드')).resolves.toEqual([]);

        const history = await fetchKeywordHistory('없는키워드', 7);
        expect(history).toHaveLength(7);
        expect(history.every((point) => point.articleCount === 0 && point.weightedScore === 0)).toBe(true);
        expect(history[0].day).toBe('2026-10-18');
        expect(history[6]).toEqual({ day: '2026-10-24', articleCount: 0, weightedScore: 0, partial: true });
    });

    it('추이는 meta.asOf를 오늘로 보고 마지막 N일을 v1 모양으로 만든다', async () => {
        const history = await fetchKeywordHistory('AI', 3);

        expect(history).toEqual([
            { day: '2026-10-22', articleCount: 2, weightedScore: 2.133, partial: false },
            { day: '2026-10-23', articleCount: 3, weightedScore: 3.333, partial: false },
            { day: '2026-10-24', articleCount: 1, weightedScore: 1.1, partial: true },
        ]);
    });

    it('days 범위와 빈 키워드를 v1 문구로 거부한다', async () => {
        await expectBadRequest(fetchKeywordHistory('인공지능', 1), 'days는 2~30 사이여야 합니다.');
        await expectBadRequest(fetchKeywordHistory('인공지능', 31), 'days는 2~30 사이여야 합니다.');
        await expectBadRequest(fetchKeywordHistory('  ', 7), '키워드는 비어 있을 수 없습니다.');
        await expectBadRequest(fetchKeywordArticles(''), '키워드는 비어 있을 수 없습니다.');
    });
});

describe('키워드 비교', () => {
    it('인공지능 vs AI는 같은 대표 키워드라 v1 문구로 거부한다', async () => {
        await expectBadRequest(fetchKeywordHistoryComparison('인공지능', 'AI', 7), SAME_CANONICAL_MESSAGE);
        await expectBadRequest(fetchKeywordHistoryEvidence('인공지능', 'a.i.', '2026-10-23', 5), SAME_CANONICAL_MESSAGE);
    });

    it('대소문자만 다른 미등록 키워드도 같은 키워드로 거부한다(v1 equalsIgnoreCase)', async () => {
        await expectBadRequest(fetchKeywordHistoryComparison('Rust', 'rust', 7), SAME_CANONICAL_MESSAGE);
    });

    it('days를 키워드보다 먼저 검사한다', async () => {
        await expectBadRequest(fetchKeywordHistoryComparison('인공지능', 'AI', 40), 'days는 2~30 사이여야 합니다.');
    });

    it('v1 compare 응답과 같은 필드를 돌려준다', async () => {
        const result = await fetchKeywordHistoryComparison(' AI ', '반도체', 7);

        expect(result).toMatchObject({
            firstRequestedKeyword: 'AI',
            secondRequestedKeyword: '반도체',
            firstCanonicalKeyword: '인공지능',
            secondCanonicalKeyword: '반도체',
            days: 7,
            timezone: 'Asia/Seoul',
            todayPartial: true,
        });
        expect(result.firstHistory).toHaveLength(7);
        expect(result.secondHistory.find((point) => point.day === '2026-10-22')).toMatchObject({
            articleCount: 3,
            weightedScore: 3.293,
        });
    });

    it('한쪽이 색인에 없으면 그쪽만 0 추이다', async () => {
        const result = await fetchKeywordHistoryComparison('인공지능', '없는키워드', 2);

        expect(result.secondCanonicalKeyword).toBe('없는키워드');
        expect(result.secondHistory).toEqual([
            { day: '2026-10-23', articleCount: 0, weightedScore: 0, partial: false },
            { day: '2026-10-24', articleCount: 0, weightedScore: 0, partial: true },
        ]);
    });
});

describe('근거 기사', () => {
    it('날짜별 근거 기사를 limit만큼 돌려준다', async () => {
        const result = await fetchKeywordHistoryEvidence('AI', '반도체', '2026-10-23', 2);

        expect(result).toMatchObject({
            date: '2026-10-23',
            timezone: 'Asia/Seoul',
            firstCanonicalKeyword: '인공지능',
            secondCanonicalKeyword: '반도체',
        });
        expect(result.firstArticles).toHaveLength(2);
        expect(result.secondArticles).toHaveLength(2);
        expect(result.firstArticles[0]).toEqual(expect.objectContaining({
            title: '고정 기사 13',
            sourceUrl: expect.any(String),
            publishedAt: expect.stringMatching(/\+09:00$/),
        }));
    });

    it('근거 기사가 없는 날짜는 빈 배열이다', async () => {
        const result = await fetchKeywordHistoryEvidence('인공지능', '반도체', '2026-10-01', 5);

        expect(result.firstArticles).toEqual([]);
        expect(result.secondArticles).toEqual([]);
    });

    it('근거 기사는 최대 5건이고 limit 범위·date를 v1 문구로 검사한다', async () => {
        const detail = JSON.parse(fs.readFileSync(path.join(FIXTURE_DIR, 'keywords/c597b282778e3c88.json'), 'utf8'));
        const sample = detail.evidenceByDay['2026-10-23'][0];
        detail.evidenceByDay['2026-10-23'] = Array.from({ length: 7 }, (_, index) => ({ ...sample, id: `article-${index}` }));
        overrides['keywords/c597b282778e3c88.json'] = detail;

        const result = await fetchKeywordHistoryEvidence('인공지능', '반도체', '2026-10-23', 5);
        expect(result.firstArticles).toHaveLength(5);

        await expectBadRequest(fetchKeywordHistoryEvidence('인공지능', '반도체', '2026-10-23', 6), 'limit는 1~5 사이여야 합니다.');
        await expectBadRequest(fetchKeywordHistoryEvidence('인공지능', '반도체', '2026-10-23', 0), 'limit는 1~5 사이여야 합니다.');
        await expectBadRequest(fetchKeywordHistoryEvidence('인공지능', '반도체', '', 5), 'date는 필수입니다.');
    });
});

describe('운영 메타데이터와 캐시', () => {
    it('meta.json과 runs/recent.json을 읽는다', async () => {
        await expect(fetchSiteMeta()).resolves.toMatchObject({ freshness: 'ok', asOf: '2026-10-24T12:00:00' });
        const runs = await fetchRecentRuns();
        expect(runs.map((run) => run.outcome)).toEqual(expect.arrayContaining(['SUCCESS', 'EMPTY', 'PARTIAL_FAILURE']));
    });

    it('한 번 받은 파일은 다시 요청하지 않는다', async () => {
        await fetchKeywordHistory('인공지능', 7);
        await fetchKeywordArticles('AI');
        await fetchKeywordHistoryComparison('인공지능', '반도체', 7);

        const counts = requestedUrls.reduce((acc, url) => ({ ...acc, [url]: (acc[url] ?? 0) + 1 }), {});
        expect(Object.values(counts).every((count) => count === 1)).toBe(true);
    });

    it('파일을 받지 못하면 axios 오류 모양으로 던지고, 다음 호출에서 다시 시도한다', async () => {
        global.fetch.mockImplementationOnce(() => respond(503, null));

        await expect(fetchTrends()).rejects.toMatchObject({ response: { status: 503 } });
        await expect(fetchTrends()).resolves.toHaveLength(5);
    });

    it('기본 데이터 위치는 PUBLIC_URL/data다', async () => {
        delete process.env.REACT_APP_STATIC_DATA_BASE;
        const previousPublicUrl = process.env.PUBLIC_URL;
        process.env.PUBLIC_URL = '/trend-analyzer-portfolio';
        try {
            await fetchSiteMeta().catch(() => {});
            expect(global.fetch).toHaveBeenCalledWith('/trend-analyzer-portfolio/data/meta.json');
        } finally {
            if (previousPublicUrl === undefined) {
                delete process.env.PUBLIC_URL;
            } else {
                process.env.PUBLIC_URL = previousPublicUrl;
            }
        }
    });
});

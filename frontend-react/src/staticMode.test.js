import fs from 'fs';
import path from 'path';
import axios from 'axios';
import '@testing-library/jest-dom';
import { render, screen, within } from '@testing-library/react';

import App from './App';
import { clearStaticDataCache } from './api/staticTrendApi';
import { fetchKeywordHistoryComparison, fetchTrends } from './api/trendApi';

jest.mock('axios');

// static 모드(REACT_APP_DATA_MODE=static) 화면 동작을 공용 고정 데이터로 확인합니다.
const FIXTURE_DIR = path.resolve(__dirname, '../../fixtures/site/data');

let metaOverride = null;

beforeEach(() => {
    process.env.REACT_APP_DATA_MODE = 'static';
    process.env.REACT_APP_STATIC_DATA_BASE = '/data';
    metaOverride = null;
    clearStaticDataCache();
    global.fetch = jest.fn((url) => {
        const relative = url.replace('/data/', '');
        const file = path.join(FIXTURE_DIR, relative);
        const exists = fs.existsSync(file);
        let body = exists ? JSON.parse(fs.readFileSync(file, 'utf8')) : null;
        if (relative === 'meta.json' && metaOverride) {
            body = { ...body, ...metaOverride };
        }
        return Promise.resolve({ ok: exists, status: exists ? 200 : 404, json: () => Promise.resolve(body) });
    });
    jest.spyOn(console, 'error').mockImplementation(() => {});
});

afterEach(() => {
    delete process.env.REACT_APP_DATA_MODE;
    delete process.env.REACT_APP_STATIC_DATA_BASE;
    delete global.fetch;
    window.location.hash = '';
    jest.restoreAllMocks();
});

describe('trendApi static 모드 위임', () => {
    it('서버를 부르지 않고 정적 JSON을 읽는다', async () => {
        const trends = await fetchTrends('ALL');

        expect(trends[0]).toMatchObject({ keyword: '인공지능', score: 3.4 });
        expect(axios.get).not.toHaveBeenCalled();
        expect(global.fetch).toHaveBeenCalledWith('/data/trends/all.json');
    });

    it('검증 오류를 화면이 읽는 error.response.data.detail로 던진다', async () => {
        const error = await fetchKeywordHistoryComparison('인공지능', 'AI', 7).catch((caught) => caught);

        expect(error.response.status).toBe(400);
        expect(error.response.data.detail).toBe(
            '두 입력은 같은 대표 키워드로 해석되어 비교할 수 없습니다. 서로 다른 키워드를 입력해주세요.'
        );
    });
});

describe('static 모드 화면', () => {
    it('해시 경로로 운영 현황을 열고, 로그인·내정보 메뉴는 숨긴다', async () => {
        window.location.hash = '#/status';
        render(<App />);

        expect(await screen.findByRole('heading', { name: '운영 현황' })).toBeInTheDocument();
        expect(await screen.findByText('정상')).toBeInTheDocument();
        expect(await screen.findByText('2026-10-24 12:00')).toBeInTheDocument();

        const table = await screen.findByRole('table');
        expect(within(table).getAllByRole('row')).toHaveLength(5);
        expect(within(table).getByText('일부 수집 단계 실패')).toBeInTheDocument();

        expect(screen.getByRole('link', { name: /운영 현황/ })).toHaveAttribute('href', '#/status');
        expect(screen.queryByRole('link', { name: /내정보/ })).not.toBeInTheDocument();
        expect(screen.queryByRole('button', { name: /로그인/ })).not.toBeInTheDocument();
        expect(axios.get).not.toHaveBeenCalled();
        // 수집이 정상이면 상단 안내를 띄우지 않습니다.
        expect(screen.queryByText(/데이터 수집이/)).not.toBeInTheDocument();
    });

    it.each([
        ['stale', 7.5, '데이터 수집이 지연되고 있습니다.'],
        ['down', 30, '데이터 수집이 중단된 상태입니다.'],
    ])('freshness=%s 이면 상단에 안내를 띄운다', async (freshness, freshnessHours, message) => {
        metaOverride = { freshness, freshnessHours };
        window.location.hash = '#/status';
        render(<App />);

        const banner = (await screen.findByText(message)).closest('[role="status"]');
        expect(banner).toHaveTextContent(`${freshnessHours}시간이 지났습니다`);
        expect(within(banner).getByRole('link', { name: '운영 현황 보기' })).toHaveAttribute('href', '#/status');
    });

    it('관리자·내정보 경로는 static 모드에 없다', async () => {
        window.location.hash = '#/my-info';
        render(<App />);

        expect(await screen.findByRole('link', { name: /인기 키워드/ })).toBeInTheDocument();
        expect(window.location.hash).toBe('#/');
    });
});

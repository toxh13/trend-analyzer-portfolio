import '@testing-library/jest-dom';
import React from 'react';
import { act, fireEvent, render, screen, waitFor } from '@testing-library/react';
import { MemoryRouter, Route, Routes, useLocation } from 'react-router-dom';

import { fetchKeywordHistoryComparison, fetchKeywordHistoryEvidence } from '../api/trendApi';
import TrendHistoryPage from './TrendHistoryPage';

jest.mock('../api/trendApi', () => ({
    fetchKeywordHistoryComparison: jest.fn(),
    fetchKeywordHistoryEvidence: jest.fn(),
}));

jest.mock('recharts', () => ({
    CartesianGrid: () => null,
    Legend: () => null,
    Line: () => null,
    ResponsiveContainer: ({ children }) => <div>{children}</div>,
    Tooltip: () => null,
    XAxis: () => null,
    YAxis: () => null,
    LineChart: ({ data, onClick, children }) => (
        <div>
            {children}
            {data.map((row) => (
                <button
                    key={row.rawDay}
                    type="button"
                    onClick={() => onClick({ activePayload: [{ payload: row }] })}
                >
                    그래프 {row.rawDay}
                </button>
            ))}
        </div>
    ),
}));

const comparison = {
    firstCanonicalKeyword: 'AI',
    secondCanonicalKeyword: '반도체',
    days: 3,
    timezone: 'Asia/Seoul',
    todayPartial: true,
    firstHistory: [
        { day: '2026-07-17', articleCount: 3, partial: false },
        { day: '2026-07-18', articleCount: 7, partial: false },
        { day: '2026-07-19', articleCount: 2, partial: true },
    ],
    secondHistory: [
        { day: '2026-07-17', articleCount: 5, partial: false },
        { day: '2026-07-18', articleCount: 4, partial: false },
        { day: '2026-07-19', articleCount: 1, partial: true },
    ],
};

function LocationProbe() {
    const location = useLocation();
    return <div data-testid="location">{location.pathname}{location.search}</div>;
}

function renderPage(initialEntry = '/history') {
    return render(
        <MemoryRouter initialEntries={[initialEntry]}>
            <Routes>
                <Route path="/history" element={<><TrendHistoryPage /><LocationProbe /></>} />
            </Routes>
        </MemoryRouter>
    );
}

describe('TrendHistoryPage', () => {
    beforeEach(() => {
        jest.clearAllMocks();
        fetchKeywordHistoryComparison.mockResolvedValue(comparison);
        fetchKeywordHistoryEvidence.mockResolvedValue({
            date: '2026-07-18',
            timezone: 'Asia/Seoul',
            firstCanonicalKeyword: 'AI',
            secondCanonicalKeyword: '반도체',
            firstArticles: [{
                id: 1,
                title: 'AI 대표 기사',
                summary: 'AI 기사 요약',
                source: '테스트뉴스',
                publishedAt: '2026-07-18T10:00:00+09:00',
                sourceUrl: 'https://example.com/ai',
            }],
            secondArticles: [],
        });
    });

    it('auto-loads a valid shared URL and displays summary metrics', async () => {
        renderPage('/history?first=AI&second=%EB%B0%98%EB%8F%84%EC%B2%B4&days=3');

        expect(await screen.findByText('AI vs 반도체')).toBeInTheDocument();
        expect(fetchKeywordHistoryComparison).toHaveBeenCalledWith('AI', '반도체', 3);
        expect(screen.getByText('누적 12건')).toBeInTheDocument();
        expect(screen.getByText('누적 10건')).toBeInTheDocument();
    });

    it.each(['31', 'abc', '2.5', ''])('shows an error and does not auto-correct invalid URL days=%s', async (invalidDays) => {
        renderPage(`/history?first=AI&second=%EB%B0%98%EB%8F%84%EC%B2%B4&days=${invalidDays}`);

        expect(await screen.findByText('조회 기간은 2일에서 30일 사이여야 합니다.')).toBeInTheDocument();
        expect(fetchKeywordHistoryComparison).not.toHaveBeenCalled();
    });

    it('writes confirmed query params only after a successful comparison', async () => {
        renderPage();

        fireEvent.change(screen.getByLabelText('첫 번째 키워드'), { target: { value: 'AI' } });
        fireEvent.change(screen.getByLabelText('두 번째 키워드'), { target: { value: '반도체' } });
        fireEvent.change(screen.getByLabelText('조회 기간'), { target: { value: '3' } });
        expect(screen.getByTestId('location')).toHaveTextContent('/history');

        fireEvent.click(screen.getByRole('button', { name: '비교 조회' }));

        await waitFor(() => expect(screen.getByTestId('location')).toHaveTextContent('first=AI'));
        expect(screen.getByTestId('location')).toHaveTextContent('days=3');
    });

    it('ignores an older comparison response that finishes after a newer request', async () => {
        let resolveOlderRequest;
        fetchKeywordHistoryComparison
            .mockImplementationOnce(() => new Promise((resolve) => { resolveOlderRequest = resolve; }))
            .mockResolvedValueOnce({ ...comparison, firstCanonicalKeyword: '클라우드' });
        renderPage();
        fireEvent.change(screen.getByLabelText('첫 번째 키워드'), { target: { value: 'AI' } });
        fireEvent.change(screen.getByLabelText('두 번째 키워드'), { target: { value: '반도체' } });
        fireEvent.change(screen.getByLabelText('조회 기간'), { target: { value: '3' } });
        fireEvent.click(screen.getByRole('button', { name: '비교 조회' }));

        fireEvent.change(screen.getByLabelText('첫 번째 키워드'), { target: { value: '클라우드' } });
        fireEvent.click(screen.getByRole('button', { name: '비교 조회' }));
        expect(await screen.findByText('클라우드 vs 반도체')).toBeInTheDocument();

        await act(async () => { resolveOlderRequest(comparison); });
        expect(screen.getByText('클라우드 vs 반도체')).toBeInTheDocument();
        expect(screen.queryByText('AI vs 반도체')).not.toBeInTheDocument();
    });

    it('hides the previous summary while a new comparison is loading', async () => {
        let resolveNewRequest;
        renderPage('/history?first=AI&second=%EB%B0%98%EB%8F%84%EC%B2%B4&days=3');
        await screen.findByText('AI vs 반도체');

        fetchKeywordHistoryComparison.mockImplementationOnce(
            () => new Promise((resolve) => { resolveNewRequest = resolve; })
        );
        fireEvent.change(screen.getByLabelText('첫 번째 키워드'), { target: { value: '클라우드' } });
        fireEvent.click(screen.getByRole('button', { name: '비교 조회' }));

        expect(screen.queryByText('AI vs 반도체')).not.toBeInTheDocument();
        expect(screen.getByText('비교 데이터를 불러오는 중입니다.')).toBeInTheDocument();

        await act(async () => { resolveNewRequest({ ...comparison, firstCanonicalKeyword: '클라우드' }); });
        expect(await screen.findByText('클라우드 vs 반도체')).toBeInTheDocument();
    });

    it('loads evidence after selecting a graph date and renders empty state independently', async () => {
        renderPage('/history?first=AI&second=%EB%B0%98%EB%8F%84%EC%B2%B4&days=3');
        await screen.findByText('AI vs 반도체');

        fireEvent.click(screen.getByRole('button', { name: '그래프 2026-07-18' }));

        expect(await screen.findByText('AI 대표 기사')).toBeInTheDocument();
        expect(screen.getByText('반도체 관련 기사가 없습니다.')).toBeInTheDocument();
        expect(fetchKeywordHistoryEvidence).toHaveBeenCalledWith('AI', '반도체', '2026-07-18', 5);
    });

    it('clears previously loaded evidence when comparison inputs change', async () => {
        renderPage('/history?first=AI&second=%EB%B0%98%EB%8F%84%EC%B2%B4&days=3');
        await screen.findByText('AI vs 반도체');
        fireEvent.click(screen.getByRole('button', { name: '그래프 2026-07-18' }));
        expect(await screen.findByText('AI 대표 기사')).toBeInTheDocument();

        fireEvent.change(screen.getByLabelText('첫 번째 키워드'), { target: { value: '클라우드' } });

        expect(screen.queryByText('AI 대표 기사')).not.toBeInTheDocument();
        expect(screen.getByText('그래프의 날짜를 선택하면 해당 날짜의 근거 기사를 확인할 수 있습니다.')).toBeInTheDocument();
    });

    it('ignores an older evidence response that finishes after a newer request', async () => {
        let resolveOlderRequest;
        fetchKeywordHistoryEvidence
            .mockImplementationOnce(() => new Promise((resolve) => { resolveOlderRequest = resolve; }))
            .mockResolvedValueOnce({
                date: '2026-07-18',
                timezone: 'Asia/Seoul',
                firstCanonicalKeyword: 'AI',
                secondCanonicalKeyword: '반도체',
                firstArticles: [{ id: 2, title: '최신 선택 기사', sourceUrl: 'https://example.com/new' }],
                secondArticles: [],
            });
        renderPage('/history?first=AI&second=%EB%B0%98%EB%8F%84%EC%B2%B4&days=3');
        await screen.findByText('AI vs 반도체');

        fireEvent.click(screen.getByRole('button', { name: '그래프 2026-07-17' }));
        fireEvent.click(screen.getByRole('button', { name: '그래프 2026-07-18' }));
        expect(await screen.findByText('최신 선택 기사')).toBeInTheDocument();

        await act(async () => {
            resolveOlderRequest({
                date: '2026-07-17',
                firstCanonicalKeyword: 'AI',
                secondCanonicalKeyword: '반도체',
                firstArticles: [{ id: 3, title: '오래된 응답 기사', sourceUrl: 'https://example.com/old' }],
                secondArticles: [],
            });
        });
        expect(screen.getByText('최신 선택 기사')).toBeInTheDocument();
        expect(screen.queryByText('오래된 응답 기사')).not.toBeInTheDocument();
    });
});

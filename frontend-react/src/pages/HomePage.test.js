import React from 'react';
import { act, fireEvent, render, screen, waitFor } from '@testing-library/react';

import { fetchPopularTrends, fetchSurgingTrends } from '../api/trendApi';
import HomePage from './HomePage';

const mockNavigate = jest.fn();
const mockRegisterPageRefresh = jest.fn();
let mockRegisteredRefresh;

jest.mock('react-router-dom', () => ({
    useNavigate: () => mockNavigate,
    useOutletContext: () => ({
        stats: { analyzedArticles: 12, trackedKeywords: 34 },
        registerPageRefresh: mockRegisterPageRefresh,
    }),
}));

jest.mock('../api/trendApi', () => ({
    fetchPopularTrends: jest.fn(),
    fetchSurgingTrends: jest.fn(),
}));

jest.mock('../components/StatsStrip', () => ({ stats }) => (
    <div data-testid="stats">{JSON.stringify(stats)}</div>
));

jest.mock('../components/TrendRankingList', () => ({ filteredTrends }) => (
    <div data-testid="ranking">{JSON.stringify(filteredTrends)}</div>
));

describe('HomePage refresh contract', () => {
    let consoleErrorSpy;

    beforeEach(() => {
        jest.clearAllMocks();
        mockRegisteredRefresh = undefined;
        mockRegisterPageRefresh.mockImplementation((handler) => {
            mockRegisteredRefresh = handler;
            return jest.fn();
        });
        consoleErrorSpy = jest.spyOn(console, 'error').mockImplementation(() => {});
    });

    afterEach(() => {
        consoleErrorSpy.mockRestore();
    });

    test('registers the same page refresh flow that reloads popular and surging rankings', async () => {
        fetchPopularTrends.mockResolvedValue([{ keyword: 'popular-initial' }]);
        fetchSurgingTrends.mockResolvedValue([{ keyword: 'surging-initial' }]);

        render(<HomePage />);

        await waitFor(() => expect(fetchPopularTrends).toHaveBeenCalledWith(20));
        await waitFor(() => expect(mockRegisterPageRefresh).toHaveBeenCalledTimes(1));
        expect(typeof mockRegisteredRefresh).toBe('function');

        await act(async () => {
            await mockRegisteredRefresh();
        });

        expect(fetchPopularTrends).toHaveBeenCalledTimes(2);
        expect(fetchSurgingTrends).toHaveBeenCalledTimes(2);
        expect(fetchSurgingTrends).toHaveBeenLastCalledWith(10);
    });

    test('preserves both existing ranking lists when a registered refresh fails', async () => {
        const popular = [{ keyword: 'keep-popular' }];
        const surging = [{ keyword: 'keep-surging' }];
        fetchPopularTrends.mockResolvedValueOnce(popular);
        fetchSurgingTrends.mockResolvedValueOnce(surging);

        render(<HomePage />);

        await waitFor(() => expect(screen.getByTestId('ranking').textContent).toContain('keep-popular'));

        fetchPopularTrends.mockRejectedValueOnce(new Error('popular refresh failed'));
        fetchSurgingTrends.mockRejectedValueOnce(new Error('surging refresh failed'));

        await act(async () => {
            try {
                await mockRegisteredRefresh();
            } catch (error) {
                // The layout handles the propagated refresh failure.
            }
        });

        expect(screen.getByTestId('ranking').textContent).toContain('keep-popular');

        const rankingModeButtons = screen.getAllByRole('button');
        fireEvent.click(rankingModeButtons[1]);
        expect(screen.getByTestId('ranking').textContent).toContain('keep-surging');
    });
});

import React from 'react';
import { act, render, screen, waitFor } from '@testing-library/react';

import { fetchTrendStats } from '../api/trendApi';
import { useTrends } from '../hooks/useTrends';
import CategoryPage from './CategoryPage';

const mockNavigate = jest.fn();
const mockRegisterPageRefresh = jest.fn();
const mockRefreshItTrends = jest.fn();
const mockRefreshEconomyTrends = jest.fn();
let mockCategorySlug = 'it';
let mockRegisteredRefresh;

jest.mock('react-router-dom', () => ({
    useNavigate: () => mockNavigate,
    useOutletContext: () => ({ registerPageRefresh: mockRegisterPageRefresh }),
    useParams: () => ({ categorySlug: mockCategorySlug }),
}));

jest.mock('../api/trendApi', () => ({
    fetchTrendStats: jest.fn(),
}));

jest.mock('../hooks/useTrends', () => ({
    useTrends: jest.fn(),
}));

jest.mock('../utils/trendUtils', () => ({
    buildTrendStats: (trends) => ({ fallbackCount: trends.length }),
    getCategoryBySlug: (slug) => ({
        it: { id: 'IT', label: 'IT', slug: 'it' },
        economy: { id: 'ECONOMY', label: 'Economy', slug: 'economy' },
    }[slug] ?? { id: 'ALL', label: 'All', slug: 'all' }),
    getCategorySlugById: (id) => id.toLowerCase(),
}));

jest.mock('../components/CategoryFilter', () => () => <div data-testid="category-filter" />);
jest.mock('../components/StatsStrip', () => ({ stats }) => (
    <div data-testid="stats">{JSON.stringify(stats)}</div>
));
jest.mock('../components/TrendRankingList', () => ({ filteredTrends }) => (
    <div data-testid="ranking">{JSON.stringify(filteredTrends)}</div>
));
jest.mock('../components/VolatilityPanel', () => () => <div data-testid="volatility" />);

describe('CategoryPage refresh contract', () => {
    let consoleErrorSpy;

    beforeEach(() => {
        jest.clearAllMocks();
        mockCategorySlug = 'it';
        mockRegisteredRefresh = undefined;
        mockRegisterPageRefresh.mockImplementation((handler) => {
            mockRegisteredRefresh = handler;
            return jest.fn();
        });
        mockRefreshItTrends.mockResolvedValue([{ keyword: 'it-refreshed' }]);
        mockRefreshEconomyTrends.mockResolvedValue([{ keyword: 'economy-refreshed' }]);
        useTrends.mockImplementation((categoryId) => ({
            trends: [{ keyword: `${categoryId}-trend` }],
            loadingTrends: false,
            refreshTrends: categoryId === 'ECONOMY'
                ? mockRefreshEconomyTrends
                : mockRefreshItTrends,
        }));
        fetchTrendStats.mockImplementation((categoryId) => Promise.resolve({
            categoryId,
            analyzedArticles: categoryId === 'ECONOMY' ? 22 : 11,
        }));
        consoleErrorSpy = jest.spyOn(console, 'error').mockImplementation(() => {});
    });

    afterEach(() => {
        consoleErrorSpy.mockRestore();
    });

    test('registers a refresh for the current category and refreshes its trends and stats', async () => {
        render(<CategoryPage />);

        await waitFor(() => expect(fetchTrendStats).toHaveBeenCalledWith('IT'));
        await waitFor(() => expect(mockRegisterPageRefresh).toHaveBeenCalledTimes(1));
        expect(typeof mockRegisteredRefresh).toBe('function');

        await act(async () => {
            await mockRegisteredRefresh();
        });

        expect(mockRefreshItTrends).toHaveBeenCalledTimes(1);
        expect(fetchTrendStats).toHaveBeenCalledTimes(2);
        expect(fetchTrendStats).toHaveBeenLastCalledWith('IT');
    });

    test('preserves existing category stats when a registered refresh fails', async () => {
        render(<CategoryPage />);

        await waitFor(() => expect(screen.getByTestId('stats').textContent).toContain('"analyzedArticles":11'));

        fetchTrendStats.mockRejectedValueOnce(new Error('category stats refresh failed'));
        await act(async () => {
            try {
                await mockRegisteredRefresh();
            } catch (error) {
                // The layout handles the propagated refresh failure.
            }
        });

        expect(screen.getByTestId('stats').textContent).toContain('"categoryId":"IT"');
        expect(screen.getByTestId('stats').textContent).toContain('"analyzedArticles":11');
    });

    test('loads trends and stats for a new category when the route category changes', async () => {
        const { rerender } = render(<CategoryPage />);

        await waitFor(() => expect(fetchTrendStats).toHaveBeenCalledWith('IT'));

        mockCategorySlug = 'economy';
        rerender(<CategoryPage />);

        await waitFor(() => {
            expect(useTrends).toHaveBeenCalledWith('ECONOMY', { enabled: true });
        });
        await waitFor(() => expect(fetchTrendStats).toHaveBeenCalledWith('ECONOMY'));
        await waitFor(() => {
            expect(screen.getByTestId('stats').textContent).toContain('"categoryId":"ECONOMY"');
        });
    });
});

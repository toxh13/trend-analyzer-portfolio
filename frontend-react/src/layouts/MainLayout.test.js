import React, { useEffect, useState } from 'react';
import { act, fireEvent, render, screen, waitFor } from '@testing-library/react';

import { fetchTrendStats } from '../api/trendApi';
import { useTrends } from '../hooks/useTrends';
import MainLayout from './MainLayout';

const mockRefreshTrends = jest.fn();
const mockPageRefresh = jest.fn();
const mockNextPageRefresh = jest.fn();

jest.mock('../api/trendApi', () => ({
    fetchTrendStats: jest.fn(),
}));

jest.mock('../hooks/useTrends', () => ({
    useTrends: jest.fn(),
}));

jest.mock('../components/SidebarNav', () => () => <aside data-testid="sidebar" />);

jest.mock('../components/DashboardHeader', () => (props) => {
    const refresh = props.onRefresh ?? props.onManualRefresh ?? props.refreshDashboard;
    const refreshing = props.isRefreshing ?? props.refreshing ?? false;

    return (
        <header>
            <output data-testid="updated-at">{props.updatedAt}</output>
            <output data-testid="refreshing">{String(refreshing)}</output>
            <button type="button" onClick={refresh} disabled={refreshing}>
                refresh
            </button>
        </header>
    );
});

jest.mock('react-router-dom', () => ({
    Outlet: ({ context }) => <MockOutlet context={context} />,
}));

function MockOutlet({ context }) {
    const [pageRefresh, setPageRefresh] = useState(() => mockPageRefresh);
    const register = context.registerPageRefresh
        ?? context.registerRefreshHandler
        ?? context.setPageRefreshHandler;

    useEffect(() => {
        if (typeof register !== 'function') {
            return undefined;
        }

        const unregister = register(pageRefresh);
        return typeof unregister === 'function' ? unregister : undefined;
    }, [pageRefresh, register]);

    return (
        <div data-testid="outlet">
            <button type="button" onClick={() => setPageRefresh(() => mockNextPageRefresh)}>
                switch page
            </button>
        </div>
    );
}

function deferred() {
    let resolve;
    let reject;
    const promise = new Promise((resolvePromise, rejectPromise) => {
        resolve = resolvePromise;
        reject = rejectPromise;
    });
    return { promise, resolve, reject };
}

async function flushMicrotasks() {
    await act(async () => {
        await Promise.resolve();
    });
}

describe('MainLayout dashboard refresh orchestration', () => {
    beforeEach(() => {
        jest.useFakeTimers();
        jest.setSystemTime(new Date('2026-07-22T01:00:00.000Z'));
        jest.clearAllMocks();
        Object.defineProperty(document, 'visibilityState', {
            configurable: true,
            value: 'visible',
        });

        fetchTrendStats.mockResolvedValue({ analyzedArticles: 10, trackedKeywords: 20 });
        mockRefreshTrends.mockResolvedValue([{ keyword: 'refreshed' }]);
        mockPageRefresh.mockResolvedValue(undefined);
        mockNextPageRefresh.mockResolvedValue(undefined);
        useTrends.mockReturnValue({
            trends: [{ keyword: 'initial' }],
            loadingTrends: false,
            trendError: null,
            refreshTrends: mockRefreshTrends,
        });
    });

    afterEach(() => {
        jest.useRealTimers();
    });

    test('sets updatedAt only after a successful request and does not tick after one second', async () => {
        const initialRequest = deferred();
        fetchTrendStats.mockReturnValueOnce(initialRequest.promise);

        render(<MainLayout />);

        expect(screen.getByTestId('updated-at').textContent).toBe('');
        expect(screen.getByRole('button', { name: 'refresh' }).disabled).toBe(true);

        initialRequest.resolve({ analyzedArticles: 10, trackedKeywords: 20 });
        await flushMicrotasks();

        const successfulUpdatedAt = screen.getByTestId('updated-at').textContent;
        expect(successfulUpdatedAt).not.toBe('');

        act(() => {
            jest.advanceTimersByTime(1000);
        });

        expect(screen.getByTestId('updated-at').textContent).toBe(successfulUpdatedAt);
    });

    test('refreshes stats, trends, and the registered page handler every five minutes', async () => {
        render(<MainLayout />);
        await flushMicrotasks();

        expect(fetchTrendStats).toHaveBeenCalledTimes(1);
        expect(mockRefreshTrends).toHaveBeenCalledTimes(1);
        expect(mockPageRefresh).toHaveBeenCalledTimes(1);

        act(() => {
            jest.advanceTimersByTime(5 * 60 * 1000);
        });
        await flushMicrotasks();

        expect(fetchTrendStats).toHaveBeenCalledTimes(2);
        expect(mockRefreshTrends).toHaveBeenCalledTimes(2);
        expect(mockPageRefresh).toHaveBeenCalledTimes(2);
    });

    test('stops polling after the layout unmounts', async () => {
        const { unmount } = render(<MainLayout />);
        await flushMicrotasks();

        unmount();
        act(() => {
            jest.advanceTimersByTime(10 * 60 * 1000);
        });
        await flushMicrotasks();

        expect(fetchTrendStats).toHaveBeenCalledTimes(1);
        expect(mockRefreshTrends).toHaveBeenCalledTimes(1);
        expect(mockPageRefresh).toHaveBeenCalledTimes(1);
    });

    test('refreshes when the document becomes visible', async () => {
        render(<MainLayout />);
        await flushMicrotasks();

        Object.defineProperty(document, 'visibilityState', {
            configurable: true,
            value: 'visible',
        });

        act(() => {
            document.dispatchEvent(new Event('visibilitychange'));
        });
        await flushMicrotasks();

        expect(fetchTrendStats).toHaveBeenCalledTimes(2);
        expect(mockRefreshTrends).toHaveBeenCalledTimes(2);
        expect(mockPageRefresh).toHaveBeenCalledTimes(2);
    });

    test('manual refresh deduplicates clicks while the first refresh is in flight', async () => {
        render(<MainLayout />);
        await flushMicrotasks();

        const pendingStats = deferred();
        fetchTrendStats.mockReturnValueOnce(pendingStats.promise);

        const refreshButton = screen.getByRole('button', { name: 'refresh' });
        fireEvent.click(refreshButton);
        fireEvent.click(refreshButton);
        await flushMicrotasks();

        expect(fetchTrendStats).toHaveBeenCalledTimes(2);
        expect(mockRefreshTrends).toHaveBeenCalledTimes(2);
        expect(mockPageRefresh).toHaveBeenCalledTimes(2);
        expect(screen.getByTestId('refreshing').textContent).toBe('true');

        pendingStats.resolve({ analyzedArticles: 11, trackedKeywords: 21 });
        await flushMicrotasks();

        await waitFor(() => {
            expect(screen.getByTestId('refreshing').textContent).toBe('false');
        });
    });

    test('keeps the last successful timestamp when a later refresh fails', async () => {
        const consoleErrorSpy = jest.spyOn(console, 'error').mockImplementation(() => {});

        render(<MainLayout />);
        await flushMicrotasks();
        const successfulUpdatedAt = screen.getByTestId('updated-at').textContent;

        jest.setSystemTime(new Date('2026-07-22T01:05:00.000Z'));
        fetchTrendStats.mockRejectedValueOnce(new Error('temporary stats failure'));

        fireEvent.click(screen.getByRole('button', { name: 'refresh' }));
        await flushMicrotasks();

        expect(screen.getByTestId('updated-at').textContent).toBe(successfulUpdatedAt);
        consoleErrorSpy.mockRestore();
    });

    test('does not set the initial timestamp when the current page refresh fails', async () => {
        const consoleErrorSpy = jest.spyOn(console, 'error').mockImplementation(() => {});
        mockPageRefresh.mockRejectedValueOnce(new Error('page refresh failed'));

        render(<MainLayout />);
        await flushMicrotasks();

        expect(screen.getByTestId('updated-at').textContent).toBe('');
        consoleErrorSpy.mockRestore();
    });

    test('skips interval polling while the document is hidden', async () => {
        render(<MainLayout />);
        await flushMicrotasks();

        Object.defineProperty(document, 'visibilityState', {
            configurable: true,
            value: 'hidden',
        });
        act(() => {
            jest.advanceTimersByTime(5 * 60 * 1000);
        });
        await flushMicrotasks();

        expect(fetchTrendStats).toHaveBeenCalledTimes(1);
        expect(mockRefreshTrends).toHaveBeenCalledTimes(1);
        expect(mockPageRefresh).toHaveBeenCalledTimes(1);
    });

    test('queues the new page refresh and timestamps only the current page after route change', async () => {
        render(<MainLayout />);
        await flushMicrotasks();

        const previousPageRequest = deferred();
        const nextPageRequest = deferred();
        mockPageRefresh.mockReturnValueOnce(previousPageRequest.promise);
        mockNextPageRefresh.mockReturnValueOnce(nextPageRequest.promise);

        fireEvent.click(screen.getByRole('button', { name: 'refresh' }));
        await flushMicrotasks();
        fireEvent.click(screen.getByRole('button', { name: 'switch page' }));
        await flushMicrotasks();

        expect(screen.getByTestId('updated-at').textContent).toBe('');

        previousPageRequest.resolve();
        await flushMicrotasks();

        expect(mockNextPageRefresh).toHaveBeenCalledTimes(1);
        expect(screen.getByTestId('updated-at').textContent).toBe('');

        nextPageRequest.resolve();
        await flushMicrotasks();

        expect(screen.getByTestId('updated-at').textContent).not.toBe('');
    });
});

import { act, renderHook, waitFor } from '@testing-library/react';

import { fetchTrends } from '../api/trendApi';
import { useTrends } from './useTrends';

jest.mock('../api/trendApi', () => ({
    fetchTrends: jest.fn(),
}));

describe('useTrends refresh contract', () => {
    let consoleErrorSpy;

    beforeEach(() => {
        jest.clearAllMocks();
        consoleErrorSpy = jest.spyOn(console, 'error').mockImplementation(() => {});
    });

    afterEach(() => {
        consoleErrorSpy.mockRestore();
    });

    test('exposes refreshTrends and replaces data after a successful refresh', async () => {
        const initialTrends = [{ keyword: 'initial' }];
        const refreshedTrends = [{ keyword: 'refreshed' }];
        fetchTrends
            .mockResolvedValueOnce(initialTrends)
            .mockResolvedValueOnce(refreshedTrends);

        const { result } = renderHook(() => useTrends('ALL'));

        await waitFor(() => expect(result.current.trends).toEqual(initialTrends));
        expect(typeof result.current.refreshTrends).toBe('function');

        await act(async () => {
            try {
                await result.current.refreshTrends();
            } catch (error) {
                // The hook may rethrow so its caller can keep the dashboard timestamp unchanged.
            }
        });

        expect(fetchTrends).toHaveBeenNthCalledWith(1, 'ALL');
        expect(fetchTrends).toHaveBeenNthCalledWith(2, 'ALL');
        expect(result.current.trends).toEqual(refreshedTrends);
        expect(result.current.trendError).toBeNull();
    });

    test('preserves the previous successful data when a refresh fails', async () => {
        const initialTrends = [{ keyword: 'keep-me' }];
        const refreshError = new Error('temporary network failure');
        fetchTrends
            .mockResolvedValueOnce(initialTrends)
            .mockRejectedValueOnce(refreshError);

        const { result } = renderHook(() => useTrends('IT/과학'));

        await waitFor(() => expect(result.current.trends).toEqual(initialTrends));

        await act(async () => {
            try {
                await result.current.refreshTrends();
            } catch (error) {
                // State preservation is the contract; propagation is the caller's concern.
            }
        });

        expect(result.current.trends).toEqual(initialTrends);
        expect(result.current.trendError).toBe(refreshError);
        expect(result.current.loadingTrends).toBe(false);
    });
});

import axios from 'axios';

import { fetchCrawlRun, fetchCrawlRuns } from './crawlRunApi';

jest.mock('axios');

describe('crawlRunApi', () => {
    beforeEach(() => jest.clearAllMocks());

    it('loads the latest 20 runs with admin credentials', async () => {
        axios.get.mockResolvedValue({ data: [{ runId: 'run-1' }] });

        await expect(fetchCrawlRuns(20)).resolves.toEqual([{ runId: 'run-1' }]);
        expect(axios.get).toHaveBeenCalledWith(
            expect.stringContaining('/api/v1/admin/crawling/runs?limit=20'),
            { withCredentials: true }
        );
    });

    it('loads one run detail with admin credentials', async () => {
        axios.get.mockResolvedValue({ data: { runId: 'run/1' } });

        await expect(fetchCrawlRun('run/1')).resolves.toEqual({ runId: 'run/1' });
        expect(axios.get).toHaveBeenCalledWith(
            expect.stringContaining('/api/v1/admin/crawling/runs/run%2F1'),
            { withCredentials: true }
        );
    });
});

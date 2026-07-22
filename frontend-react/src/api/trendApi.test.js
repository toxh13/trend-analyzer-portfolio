import axios from 'axios';

import { fetchKeywordHistoryEvidence } from './trendApi';

jest.mock('axios');

describe('fetchKeywordHistoryEvidence', () => {
    it('calls the evidence endpoint with both keywords, date, and limit', async () => {
        const payload = {
            date: '2026-07-18',
            timezone: 'Asia/Seoul',
            firstCanonicalKeyword: 'AI',
            secondCanonicalKeyword: '반도체',
            firstArticles: [],
            secondArticles: [],
        };
        axios.get.mockResolvedValue({ data: payload });

        await expect(fetchKeywordHistoryEvidence('AI', '반도체', '2026-07-18', 5)).resolves.toEqual(payload);
        expect(axios.get).toHaveBeenCalledWith(expect.stringContaining('/history/evidence'), {
            params: {
                firstKeyword: 'AI',
                secondKeyword: '반도체',
                date: '2026-07-18',
                limit: 5,
            },
        });
    });
});

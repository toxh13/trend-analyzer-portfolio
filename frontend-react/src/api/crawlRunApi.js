import axios from 'axios';

import { buildApiUrl } from '../utils/apiBaseUrl';

export async function fetchCrawlRuns(limit = 20) {
    const response = await axios.get(
        buildApiUrl(`/api/v1/admin/crawling/runs?limit=${limit}`),
        { withCredentials: true }
    );
    return response.data || [];
}

export async function fetchCrawlRun(runId) {
    const response = await axios.get(
        buildApiUrl(`/api/v1/admin/crawling/runs/${encodeURIComponent(runId)}`),
        { withCredentials: true }
    );
    return response.data;
}

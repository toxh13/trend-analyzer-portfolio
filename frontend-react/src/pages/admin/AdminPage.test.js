import '@testing-library/jest-dom';
import React from 'react';
import { fireEvent, render, screen, waitFor } from '@testing-library/react';
import axios from 'axios';

import { fetchCrawlRuns } from '../../api/crawlRunApi';
import AdminPage from './AdminPage';

jest.mock('axios');
jest.mock('../../api/crawlRunApi', () => ({
    fetchCrawlRun: jest.fn(),
    fetchCrawlRuns: jest.fn(),
}));
jest.mock('../../components/admin/AdminHeader', () => () => <div>관리자 헤더</div>);
jest.mock('../../components/admin/AdminSummaryCards', () => () => <div>기존 요약</div>);
jest.mock('../../components/admin/AdminKeywordTab', () => () => <div>키워드 탭</div>);
jest.mock('../../components/admin/AdminKeywordGroupsTab', () => () => <div>그룹 탭</div>);
jest.mock('../../components/admin/AdminMergeSuggestionsTab', () => () => <div>추천 탭</div>);

describe('AdminPage crawl runs loading', () => {
    beforeEach(() => {
        jest.clearAllMocks();
        axios.get.mockResolvedValue({ data: [] });
        fetchCrawlRuns.mockResolvedValue([]);
    });

    it('loads crawl runs only after the crawl tab is opened and does not reload on tab return', async () => {
        render(<AdminPage />);

        await waitFor(() => expect(axios.get).toHaveBeenCalledTimes(4));
        expect(fetchCrawlRuns).not.toHaveBeenCalled();

        fireEvent.click(screen.getByRole('button', { name: '수집 현황' }));
        await waitFor(() => expect(fetchCrawlRuns).toHaveBeenCalledWith(20));
        expect(screen.queryByText('기존 요약')).not.toBeInTheDocument();

        fireEvent.click(screen.getByRole('button', { name: /그룹/ }));
        fireEvent.click(screen.getByRole('button', { name: '수집 현황' }));
        expect(fetchCrawlRuns).toHaveBeenCalledTimes(1);
    });
});

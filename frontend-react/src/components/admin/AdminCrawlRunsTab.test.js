import '@testing-library/jest-dom';
import React from 'react';
import { fireEvent, render, screen } from '@testing-library/react';

import AdminCrawlRunsTab, { formatCrawlRunTime } from './AdminCrawlRunsTab';

const run = {
    runId: 'run-1',
    completedAt: '2026-07-20T00:04:12Z',
    outcome: 'SUCCESS',
    crawlerOutputCount: 83,
    sourceInvalidCount: 4,
    validationRejectedCount: 7,
    duplicateUrlCount: 13,
    eligibleCount: 63,
    selectedCount: 50,
    droppedByLimitCount: 13,
    preprocessingFailedCount: 1,
    backendAcknowledgedCount: 48,
    httpFailedCount: 1,
    transportFailedCount: 0,
    reconciliationOk: true,
    channels: [{
        channel: 'naver',
        outcome: 'PARTIAL_FAILURE',
        validatedArticleCount: 30,
        sourceInvalidCount: 2,
    }],
};

const defaultProps = {
    runs: [run],
    loading: false,
    error: null,
    selectedRun: null,
    detailLoading: false,
    detailError: null,
    onRefresh: jest.fn(),
    onSelectRun: jest.fn(),
    onRetryDetail: jest.fn(),
};

describe('AdminCrawlRunsTab', () => {
    beforeEach(() => jest.clearAllMocks());

    it('shows loading, empty, and list error states with retry', () => {
        const { rerender } = render(<AdminCrawlRunsTab {...defaultProps} runs={[]} loading />);
        expect(screen.getByText('수집 실행 이력을 불러오는 중입니다.')).toBeInTheDocument();

        rerender(<AdminCrawlRunsTab {...defaultProps} runs={[]} />);
        expect(screen.getByText(/아직 저장된 수집 실행 이력이 없습니다/)).toBeInTheDocument();

        rerender(<AdminCrawlRunsTab {...defaultProps} runs={[]} error="목록 오류" />);
        fireEvent.click(screen.getByRole('button', { name: '다시 시도' }));
        expect(defaultProps.onRefresh).toHaveBeenCalled();
    });

    it.each([
        ['RUNNING', '실행 중'],
        ['SUCCESS', '정상 완료'],
        ['EMPTY', '정상 완료 · 수집 결과 없음'],
        ['PARTIAL_FAILURE', '일부 수집 단계 실패'],
        ['FAILURE', '배치 실패'],
    ])('renders %s with a Korean status label', (outcome, label) => {
        render(<AdminCrawlRunsTab {...defaultProps} runs={[{ ...run, outcome }]} />);
        expect(screen.getAllByText(label).length).toBeGreaterThan(0);
    });

    it('shows the start time while a batch is running', () => {
        render(<AdminCrawlRunsTab {...defaultProps} runs={[{
            ...run,
            outcome: 'RUNNING',
            startedAt: '2026-07-20T00:00:00Z',
            completedAt: null,
        }]} />);

        expect(screen.getByText('실행 시작 시각')).toBeInTheDocument();
        expect(screen.getByText('실행 시작 후 경과')).toBeInTheDocument();
        expect(screen.getAllByText('실행 중').length).toBeGreaterThan(0);
        expect(screen.getAllByText(formatCrawlRunTime('2026-07-20T00:00:00Z'))).toHaveLength(2);
    });

    it('shows the observed-scope limitation, timestamp, and request acknowledgement meaning', () => {
        render(<AdminCrawlRunsTab {...defaultProps} />);

        expect(screen.getByText(/관측된 수집 범위/)).toBeInTheDocument();
        expect(screen.getByText(/신규 저장 건수가 아니라/)).toBeInTheDocument();
        expect(screen.getAllByText(formatCrawlRunTime(run.completedAt))).toHaveLength(2);
        expect(formatCrawlRunTime(run.completedAt)).toContain('09:04:12');
    });

    it('selects a list row and renders separated counts and channel status in detail', () => {
        const { rerender } = render(<AdminCrawlRunsTab {...defaultProps} />);
        fireEvent.click(screen.getAllByText(formatCrawlRunTime(run.completedAt))[1]);
        expect(defaultProps.onSelectRun).toHaveBeenCalledWith('run-1');

        rerender(<AdminCrawlRunsTab {...defaultProps} selectedRun={run} />);
        expect(screen.getByText(/수집원 내부 탈락 4건/)).toBeInTheDocument();
        expect(screen.getByText('공통 검증 탈락')).toBeInTheDocument();
        expect(screen.getByText('7건')).toBeInTheDocument();
        expect(screen.getByText('naver')).toBeInTheDocument();
        expect(screen.getAllByText('일부 수집 단계 실패').length).toBeGreaterThan(0);
    });

    it('keeps the list visible when detail loading fails and retries the detail', () => {
        render(<AdminCrawlRunsTab {...defaultProps} detailError="상세 오류" />);

        expect(screen.getAllByText(formatCrawlRunTime(run.completedAt))).toHaveLength(2);
        expect(screen.getByText('최근 실행 목록은 그대로 유지됩니다.')).toBeInTheDocument();
        fireEvent.click(screen.getByRole('button', { name: '상세 다시 시도' }));
        expect(defaultProps.onRetryDetail).toHaveBeenCalled();
    });
});

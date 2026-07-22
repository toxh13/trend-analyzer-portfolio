import {
    buildComparisonInterpretation,
    buildComparisonSummary,
    normalizeHistoryRows,
} from './trendComparison';

const firstHistory = [
    { day: '2026-07-17', articleCount: 3, partial: false },
    { day: '2026-07-18', articleCount: 7, partial: false },
    { day: '2026-07-19', articleCount: 2, partial: true },
];

const secondHistory = [
    { day: '2026-07-17', articleCount: 5, partial: false },
    { day: '2026-07-18', articleCount: 4, partial: false },
    { day: '2026-07-19', articleCount: 1, partial: true },
];

describe('trendComparison', () => {
    it('normalizes both histories without exposing weightedScore', () => {
        expect(normalizeHistoryRows('AI', firstHistory, '반도체', secondHistory)).toEqual([
            { day: '07.17', rawDay: '2026-07-17', partial: false, AI: 3, 반도체: 5 },
            { day: '07.18', rawDay: '2026-07-18', partial: false, AI: 7, 반도체: 4 },
            { day: '07.19', rawDay: '2026-07-19', partial: true, AI: 2, 반도체: 1 },
        ]);
    });

    it('calculates totals, difference, peaks, leading days, ties, and completed-day changes', () => {
        const rows = normalizeHistoryRows('AI', firstHistory, '반도체', secondHistory);
        const summary = buildComparisonSummary(rows, 'AI', '반도체');

        expect(summary.first).toMatchObject({ total: 12, peakDay: '2026-07-18', peakCount: 7, peakDays: ['2026-07-18'], leadingDays: 1 });
        expect(summary.second).toMatchObject({ total: 10, peakDay: '2026-07-17', peakCount: 5, leadingDays: 1 });
        expect(summary.difference).toBe(2);
        expect(summary.tieDays).toBe(0);
        expect(summary.first.recentCompletedChange).toMatchObject({
            value: 4,
            previousDay: '2026-07-17',
            currentDay: '2026-07-18',
        });
        expect(summary.second.recentCompletedChange.value).toBe(-1);
    });

    it('returns safe zero values and no change when completed data is insufficient', () => {
        const rows = normalizeHistoryRows(
            'AI',
            [{ day: '2026-07-19', articleCount: 0, partial: true }],
            '반도체',
            [{ day: '2026-07-19', articleCount: 0, partial: true }]
        );
        const summary = buildComparisonSummary(rows, 'AI', '반도체');

        expect(summary.first.total).toBe(0);
        expect(summary.second.total).toBe(0);
        expect(summary.tieDays).toBe(0);
        expect(summary.first.peakDay).toBeNull();
        expect(summary.first.peakDays).toEqual([]);
        expect(summary.first.recentCompletedChange).toBeNull();
        expect(summary.second.recentCompletedChange).toBeNull();
    });

    it('keeps every completed date tied at the non-zero peak', () => {
        const rows = normalizeHistoryRows(
            'AI',
            [
                { day: '2026-07-17', articleCount: 4, partial: false },
                { day: '2026-07-18', articleCount: 4, partial: false },
            ],
            '반도체',
            [
                { day: '2026-07-17', articleCount: 1, partial: false },
                { day: '2026-07-18', articleCount: 2, partial: false },
            ]
        );

        expect(buildComparisonSummary(rows, 'AI', '반도체').first).toMatchObject({
            peakDay: '2026-07-17',
            peakCount: 4,
            peakDays: ['2026-07-17', '2026-07-18'],
        });
    });

    it('builds a factual interpretation without claiming a cause', () => {
        const rows = normalizeHistoryRows('AI', firstHistory, '반도체', secondHistory);
        const summary = buildComparisonSummary(rows, 'AI', '반도체');
        const interpretation = buildComparisonInterpretation(summary, 'AI', '반도체', 3, true);

        expect(interpretation).toContain('AI는 12건');
        expect(interpretation).toContain('반도체는 10건');
        expect(interpretation).toContain('오늘 부분 집계');
        expect(interpretation).not.toMatch(/원인|때문|영향/);
    });
});

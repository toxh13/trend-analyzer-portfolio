function toCount(value) {
    const count = Number(value ?? 0);
    return Number.isFinite(count) ? count : 0;
}

export function normalizeHistoryRows(firstKeyword, firstHistory = [], secondKeyword, secondHistory = []) {
    const rowMap = new Map();

    const mergeHistory = (history, keyword) => {
        history.forEach((item) => {
            const rawDay = item.day ?? item.date;
            if (!rawDay) return;

            const row = rowMap.get(rawDay) ?? {
                day: rawDay.slice(5).replace('-', '.'),
                rawDay,
                partial: false,
            };
            row.partial = row.partial || Boolean(item.partial);
            row[keyword] = toCount(item.articleCount);
            rowMap.set(rawDay, row);
        });
    };

    mergeHistory(firstHistory, firstKeyword);
    mergeHistory(secondHistory, secondKeyword);

    return Array.from(rowMap.values())
        .sort((left, right) => left.rawDay.localeCompare(right.rawDay))
        .map((row) => ({
            ...row,
            [firstKeyword]: row[firstKeyword] ?? 0,
            [secondKeyword]: row[secondKeyword] ?? 0,
        }));
}

function findPeak(rows, keyword) {
    const peakCount = rows.reduce((peak, row) => Math.max(peak, toCount(row[keyword])), 0);
    if (peakCount === 0) return { peakDay: null, peakCount: 0, peakDays: [] };

    const peakDays = rows
        .filter((row) => toCount(row[keyword]) === peakCount)
        .map((row) => row.rawDay);
    return { peakDay: peakDays[0], peakCount, peakDays };
}

function findRecentCompletedChange(rows, keyword) {
    const completedRows = rows.filter((row) => !row.partial);
    if (completedRows.length < 2) return null;

    const previous = completedRows[completedRows.length - 2];
    const current = completedRows[completedRows.length - 1];
    return {
        value: toCount(current[keyword]) - toCount(previous[keyword]),
        previousDay: previous.rawDay,
        currentDay: current.rawDay,
    };
}

export function buildComparisonSummary(rows = [], firstKeyword, secondKeyword) {
    const firstTotal = rows.reduce((sum, row) => sum + toCount(row[firstKeyword]), 0);
    const secondTotal = rows.reduce((sum, row) => sum + toCount(row[secondKeyword]), 0);
    let firstLeadingDays = 0;
    let secondLeadingDays = 0;
    let tieDays = 0;

    rows.filter((row) => !row.partial).forEach((row) => {
        const firstCount = toCount(row[firstKeyword]);
        const secondCount = toCount(row[secondKeyword]);
        if (firstCount > secondCount) firstLeadingDays += 1;
        else if (secondCount > firstCount) secondLeadingDays += 1;
        else tieDays += 1;
    });

    return {
        first: {
            total: firstTotal,
            ...findPeak(rows, firstKeyword),
            leadingDays: firstLeadingDays,
            recentCompletedChange: findRecentCompletedChange(rows, firstKeyword),
        },
        second: {
            total: secondTotal,
            ...findPeak(rows, secondKeyword),
            leadingDays: secondLeadingDays,
            recentCompletedChange: findRecentCompletedChange(rows, secondKeyword),
        },
        difference: firstTotal - secondTotal,
        tieDays,
    };
}

export function buildComparisonInterpretation(summary, firstKeyword, secondKeyword, days, todayPartial) {
    if (!summary) return '';

    const difference = Math.abs(summary.difference);
    let comparisonSentence = '두 키워드의 누적 언급량이 같습니다.';
    if (summary.difference > 0) {
        comparisonSentence = `${firstKeyword}가 ${difference.toLocaleString()}건 더 많이 언급됐습니다.`;
    } else if (summary.difference < 0) {
        comparisonSentence = `${secondKeyword}가 ${difference.toLocaleString()}건 더 많이 언급됐습니다.`;
    }

    const partialSentence = todayPartial
        ? ' 누적값에는 현재 시각까지의 오늘 부분 집계가 포함됩니다.'
        : '';

    return `최근 ${days}일 동안 ${firstKeyword}는 ${summary.first.total.toLocaleString()}건, ${secondKeyword}는 ${summary.second.total.toLocaleString()}건의 기사에서 언급됐습니다. ${comparisonSentence}${partialSentence}`;
}

package com.example.backendspring.service;

import com.example.backendspring.entity.TrendMetric;
import com.example.backendspring.repository.ArticleKeywordRepository;
import com.example.backendspring.repository.TrendMetricRepository;
import jakarta.transaction.Transactional;
import lombok.RequiredArgsConstructor;
import lombok.extern.slf4j.Slf4j;
import org.springframework.scheduling.annotation.Scheduled;
import org.springframework.stereotype.Service;

import java.time.Clock;
import java.time.LocalDateTime;
import java.time.ZoneId;
import java.util.Comparator;
import java.util.HashMap;
import java.util.HashSet;
import java.util.List;
import java.util.Locale;
import java.util.Map;
import java.util.Set;

@Service
@RequiredArgsConstructor
@Slf4j
public class TrendAnalysticService {
    private static final int TREND_WINDOW_HOURS = 24;
    private static final ZoneId TREND_ZONE = ZoneId.of("Asia/Seoul");

    private final ArticleKeywordRepository articleKeywordRepository;
    private final CrawlerKeywordService crawlerKeywordService;
    private final TrendMetricRepository trendMetricRepository;
    private final KeywordAliasCacheService keywordAliasCacheService;
    private final Clock clock;
    private final TrendBatchMetrics trendBatchMetrics;

    /**
     * 최근 24시간과 직전 24시간의 고유 기사 수를 비교해 최신 트렌드 스냅샷을 만든다.
     */
    @Scheduled(cron = "0 0 * * * *")
    @Transactional
    public synchronized void analyzeAndUpdateTrends() {
        TrendBatchMetrics.BatchRun batchRun = trendBatchMetrics.start();
        try {
            analyzeAndReplaceSnapshot(batchRun);
        } catch (RuntimeException error) {
            trendBatchMetrics.recordFailure(batchRun, error);
            log.error("트렌드 집계 실패", error);
            throw error;
        }
    }

    private void analyzeAndReplaceSnapshot(TrendBatchMetrics.BatchRun batchRun) {
        LocalDateTime endDate = LocalDateTime.ofInstant(clock.instant(), TREND_ZONE);
        LocalDateTime currentStart = endDate.minusHours(TREND_WINDOW_HOURS);
        LocalDateTime previousStart = currentStart.minusHours(TREND_WINDOW_HOURS);

        log.info(
                "트렌드 집계 시작 - previous=[{}, {}), current=[{}, {})",
                previousStart,
                currentStart,
                currentStart,
                endDate
        );

        List<Object[]> evidenceRows = articleKeywordRepository
                .findTrendEvidenceWithinWindow(previousStart, endDate);
        Set<String> blockedKeywords = crawlerKeywordService.getActiveBlockedKeywordSet();
        Map<MetricKey, WindowCounts> countsByMetric = new HashMap<>();
        Set<Long> evidenceArticleIds = new HashSet<>();
        Set<ArticleMetricKey> uniqueArticleMetrics = new HashSet<>();

        for (Object[] row : evidenceRows) {
            if (row == null || row.length < 4 || !(row[0] instanceof Number articleId)) {
                continue;
            }
            evidenceArticleIds.add(articleId.longValue());

            LocalDateTime publishedAt = row[1] instanceof LocalDateTime value ? value : null;
            String category = row[2] == null ? null : String.valueOf(row[2]).trim();
            String rawKeyword = row[3] == null ? null : String.valueOf(row[3]).trim();
            WindowType windowType = resolveWindow(publishedAt, previousStart, currentStart, endDate);
            MetricKey metricKey = resolveMetricKey(rawKeyword, category, blockedKeywords);

            if (windowType != null && metricKey != null) {
                uniqueArticleMetrics.add(new ArticleMetricKey(articleId.longValue(), metricKey, windowType));
            }
        }

        for (ArticleMetricKey articleMetric : uniqueArticleMetrics) {
            WindowCounts counts = countsByMetric.computeIfAbsent(articleMetric.metricKey, key -> new WindowCounts());
            if (articleMetric.windowType == WindowType.CURRENT) {
                counts.currentArticleCount++;
            } else {
                counts.previousArticleCount++;
            }
        }

        List<TrendMetric> latestSnapshot = countsByMetric.entrySet().stream()
                .sorted(Map.Entry.comparingByKey(
                        Comparator.comparing(MetricKey::category).thenComparing(MetricKey::keyword)
                ))
                .map(entry -> createMetric(entry.getKey(), entry.getValue()))
                .toList();

        // 최신 두 구간에서 사라진 키워드가 과거 점수로 남지 않도록 스냅샷 전체를 교체한다.
        trendMetricRepository.deleteSnapshotRows();
        trendMetricRepository.saveAll(latestSnapshot);

        trendBatchMetrics.completeAfterTransaction(
                batchRun,
                evidenceRows.size(),
                evidenceArticleIds.size(),
                uniqueArticleMetrics.size(),
                latestSnapshot.size()
        );

        log.info(
                "트렌드 스냅샷 저장 준비 완료 - 근거 행: {}, 기사: {}, 고유 기사-키워드: {}, 스냅샷 행: {}",
                evidenceRows.size(),
                evidenceArticleIds.size(),
                uniqueArticleMetrics.size(),
                latestSnapshot.size()
        );
    }

    private MetricKey resolveMetricKey(String rawKeyword, String category, Set<String> blockedKeywords) {
        if (rawKeyword == null || rawKeyword.isBlank() || category == null || category.isBlank()) {
            return null;
        }

        String canonicalKeyword = keywordAliasCacheService.resolveKeyword(rawKeyword);
        if (canonicalKeyword == null || canonicalKeyword.isBlank()) {
            return null;
        }

        if (blockedKeywords.contains(normalizeForCompare(rawKeyword))
                || blockedKeywords.contains(normalizeForCompare(canonicalKeyword))) {
            return null;
        }

        return new MetricKey(canonicalKeyword.trim(), category);
    }

    private WindowType resolveWindow(
            LocalDateTime publishedAt,
            LocalDateTime previousStart,
            LocalDateTime currentStart,
            LocalDateTime endDate
    ) {
        if (publishedAt == null || publishedAt.isBefore(previousStart) || !publishedAt.isBefore(endDate)) {
            return null;
        }
        return publishedAt.isBefore(currentStart) ? WindowType.PREVIOUS : WindowType.CURRENT;
    }

    private TrendMetric createMetric(MetricKey key, WindowCounts counts) {
        int velocityScore = counts.currentArticleCount - counts.previousArticleCount;
        float hotnessScore = (counts.currentArticleCount * 0.4F) + (velocityScore * 0.6F);

        return TrendMetric.builder()
                .keyword(key.keyword)
                .category(key.category)
                .mentionCount(counts.currentArticleCount)
                .velocityScore(velocityScore)
                .hotnessScore(hotnessScore)
                .build();
    }

    private String normalizeForCompare(String value) {
        return value == null ? "" : value.trim().toLowerCase(Locale.ROOT);
    }

    private enum WindowType {
        PREVIOUS,
        CURRENT
    }

    private record MetricKey(String keyword, String category) {
    }

    private record ArticleMetricKey(long articleId, MetricKey metricKey, WindowType windowType) {
    }

    private static class WindowCounts {
        private int currentArticleCount;
        private int previousArticleCount;
    }
}

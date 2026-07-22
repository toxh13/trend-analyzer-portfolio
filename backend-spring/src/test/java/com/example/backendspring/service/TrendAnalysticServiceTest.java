package com.example.backendspring.service;

import com.example.backendspring.entity.TrendMetric;
import com.example.backendspring.repository.ArticleKeywordRepository;
import com.example.backendspring.repository.TrendMetricRepository;
import org.junit.jupiter.api.DisplayName;
import org.junit.jupiter.api.Test;
import org.junit.jupiter.api.extension.ExtendWith;
import org.mockito.InjectMocks;
import org.mockito.Mock;
import org.mockito.ArgumentCaptor;
import org.mockito.junit.jupiter.MockitoExtension;

import java.time.Clock;
import java.time.Instant;
import java.time.LocalDateTime;
import java.util.ArrayList;
import java.util.List;
import java.util.Set;

import static org.assertj.core.api.Assertions.assertThat;
import static org.assertj.core.api.Assertions.assertThatThrownBy;
import static org.assertj.core.api.Assertions.within;
import static org.mockito.ArgumentMatchers.any;
import static org.mockito.ArgumentMatchers.anyString;
import static org.mockito.Mockito.*;

@ExtendWith(MockitoExtension.class)
class TrendAnalysticServiceTest {

    @Mock
    private ArticleKeywordRepository articleKeywordRepository;

    @Mock
    private CrawlerKeywordService crawlerKeywordService;

    @Mock
    private TrendMetricRepository trendMetricRepository;

    @Mock
    private KeywordAliasCacheService keywordAliasCacheService;

    @Mock
    private Clock clock;

    @Mock
    private TrendBatchMetrics trendBatchMetrics;

    @InjectMocks
    private TrendAnalysticService trendAnalysticService;

    @Test
    @DisplayName("두 24시간 구간을 비교하고 같은 기사의 alias는 대표 키워드 1건으로 집계한다")
    void analyzeAndUpdateTrendsUsesCanonicalArticleGrainAndNonOverlappingWindows() {
        fixClockAt2026July18At1530Kst();

        when(articleKeywordRepository.findTrendEvidenceWithinWindow(any(), any()))
                .thenReturn(List.of(
                        evidence(1L, LocalDateTime.of(2026, 7, 18, 14, 0), "IT", "AI"),
                        evidence(1L, LocalDateTime.of(2026, 7, 18, 14, 0), "IT", "인공지능"),
                        evidence(2L, LocalDateTime.of(2026, 7, 18, 13, 0), "경제", "AI"),
                        evidence(3L, LocalDateTime.of(2026, 7, 17, 14, 0), "IT", "AI")
                ));
        when(crawlerKeywordService.getActiveBlockedKeywordSet()).thenReturn(Set.of());
        when(keywordAliasCacheService.resolveKeyword("AI")).thenReturn("인공지능");
        when(keywordAliasCacheService.resolveKeyword("인공지능")).thenReturn("인공지능");

        trendAnalysticService.analyzeAndUpdateTrends();

        verify(trendBatchMetrics).completeAfterTransaction(any(), eq(4), eq(3), eq(3), eq(2));

        ArgumentCaptor<LocalDateTime> startCaptor = ArgumentCaptor.forClass(LocalDateTime.class);
        ArgumentCaptor<LocalDateTime> endCaptor = ArgumentCaptor.forClass(LocalDateTime.class);
        verify(articleKeywordRepository).findTrendEvidenceWithinWindow(
                startCaptor.capture(),
                endCaptor.capture()
        );
        assertThat(startCaptor.getValue()).isEqualTo(LocalDateTime.of(2026, 7, 16, 15, 30));
        assertThat(endCaptor.getValue()).isEqualTo(LocalDateTime.of(2026, 7, 18, 15, 30));

        List<TrendMetric> metrics = captureSavedMetrics();
        assertThat(metrics).hasSize(2);
        assertThat(metrics).anySatisfy(metric -> {
            assertThat(metric.getKeyword()).isEqualTo("인공지능");
            assertThat(metric.getCategory()).isEqualTo("IT");
            assertThat(metric.getMentionCount()).isEqualTo(1);
            assertThat(metric.getVelocityScore()).isZero();
            assertThat(metric.getHotnessScore()).isEqualTo(0.4F);
        });
        assertThat(metrics).anySatisfy(metric -> {
            assertThat(metric.getKeyword()).isEqualTo("인공지능");
            assertThat(metric.getCategory()).isEqualTo("경제");
            assertThat(metric.getMentionCount()).isEqualTo(1);
            assertThat(metric.getVelocityScore()).isEqualTo(1.0F);
            assertThat(metric.getHotnessScore()).isEqualTo(1.0F);
        });
    }

    @Test
    @DisplayName("이전 구간에만 있던 키워드는 0건과 음수 변화량으로 남기고 오래된 스냅샷은 교체한다")
    void analyzeAndUpdateTrendsKeepsFallingKeywordAndReplacesStaleSnapshot() {
        fixClockAt2026July18At1530Kst();
        when(articleKeywordRepository.findTrendEvidenceWithinWindow(any(), any()))
                .thenReturn(List.<Object[]>of(
                        evidence(1L, LocalDateTime.of(2026, 7, 17, 14, 0), "IT", "레거시")
                ));
        when(crawlerKeywordService.getActiveBlockedKeywordSet()).thenReturn(Set.of());
        when(keywordAliasCacheService.resolveKeyword(anyString()))
                .thenAnswer(invocation -> invocation.getArgument(0));

        trendAnalysticService.analyzeAndUpdateTrends();

        verify(trendMetricRepository).deleteSnapshotRows();
        List<TrendMetric> metrics = captureSavedMetrics();
        assertThat(metrics).singleElement().satisfies(metric -> {
            assertThat(metric.getMentionCount()).isZero();
            assertThat(metric.getVelocityScore()).isEqualTo(-1.0F);
            assertThat(metric.getHotnessScore()).isEqualTo(-0.6F);
        });
    }

    @Test
    @DisplayName("최근 24시간 7건과 직전 24시간 11건을 비교해 하락량 -4를 저장한다")
    void analyzeAndUpdateTrendsStoresActualArticleCountDecrease() {
        fixClockAt2026July18At1530Kst();
        List<Object[]> evidenceRows = new ArrayList<>();
        for (long articleId = 1; articleId <= 11; articleId++) {
            evidenceRows.add(evidence(
                    articleId,
                    LocalDateTime.of(2026, 7, 17, 14, 0).plusMinutes(articleId),
                    "경제",
                    "미국"
            ));
        }
        for (long articleId = 12; articleId <= 18; articleId++) {
            evidenceRows.add(evidence(
                    articleId,
                    LocalDateTime.of(2026, 7, 18, 14, 0).plusMinutes(articleId),
                    "경제",
                    "미국"
            ));
        }

        when(articleKeywordRepository.findTrendEvidenceWithinWindow(any(), any()))
                .thenReturn(evidenceRows);
        when(crawlerKeywordService.getActiveBlockedKeywordSet()).thenReturn(Set.of());
        when(keywordAliasCacheService.resolveKeyword("미국")).thenReturn("미국");

        trendAnalysticService.analyzeAndUpdateTrends();

        assertThat(captureSavedMetrics()).singleElement().satisfies(metric -> {
            assertThat(metric.getKeyword()).isEqualTo("미국");
            assertThat(metric.getMentionCount()).isEqualTo(7);
            assertThat(metric.getVelocityScore()).isEqualTo(-4.0F);
            assertThat(metric.getHotnessScore()).isCloseTo(0.4F, within(0.0001F));
        });
    }

    @Test
    @DisplayName("차단 키워드는 대표 키워드 변환 전후 모두 스냅샷에서 제외한다")
    void analyzeAndUpdateTrendsExcludesBlockedRawAndCanonicalKeywords() {
        fixClockAt2026July18At1530Kst();
        when(articleKeywordRepository.findTrendEvidenceWithinWindow(any(), any()))
                .thenReturn(List.of(
                        evidence(1L, LocalDateTime.of(2026, 7, 18, 14, 0), "IT", "광고"),
                        evidence(1L, LocalDateTime.of(2026, 7, 18, 14, 0), "IT", "AI")
                ));
        when(crawlerKeywordService.getActiveBlockedKeywordSet()).thenReturn(Set.of("광고", "인공지능"));
        when(keywordAliasCacheService.resolveKeyword("광고")).thenReturn("광고");
        when(keywordAliasCacheService.resolveKeyword("AI")).thenReturn("인공지능");

        trendAnalysticService.analyzeAndUpdateTrends();

        verify(trendMetricRepository).deleteSnapshotRows();
        assertThat(captureSavedMetrics()).isEmpty();
    }

    @Test
    @DisplayName("24시간 경계는 시작을 포함하고 끝을 제외해 두 구간에 중복 집계하지 않는다")
    void analyzeAndUpdateTrendsUsesHalfOpenWindowBoundaries() {
        fixClockAt2026July18At1530Kst();
        when(articleKeywordRepository.findTrendEvidenceWithinWindow(any(), any()))
                .thenReturn(List.of(
                        evidence(1L, LocalDateTime.of(2026, 7, 16, 15, 30), "IT", "LLM"),
                        evidence(2L, LocalDateTime.of(2026, 7, 17, 15, 30), "IT", "LLM"),
                        evidence(3L, LocalDateTime.of(2026, 7, 18, 15, 30), "IT", "LLM")
                ));
        when(crawlerKeywordService.getActiveBlockedKeywordSet()).thenReturn(Set.of());
        when(keywordAliasCacheService.resolveKeyword("LLM")).thenReturn("LLM");

        trendAnalysticService.analyzeAndUpdateTrends();

        assertThat(captureSavedMetrics()).singleElement().satisfies(metric -> {
            assertThat(metric.getMentionCount()).isEqualTo(1);
            assertThat(metric.getVelocityScore()).isZero();
        });
    }

    @Test
    @DisplayName("집계 실패는 실패 지표를 기록하고 예외를 다시 전달한다")
    void analyzeAndUpdateTrendsRecordsFailureAndRethrows() {
        fixClockAt2026July18At1530Kst();
        IllegalStateException failure = new IllegalStateException("database unavailable");
        when(articleKeywordRepository.findTrendEvidenceWithinWindow(any(), any())).thenThrow(failure);

        assertThatThrownBy(() -> trendAnalysticService.analyzeAndUpdateTrends())
                .isSameAs(failure);

        verify(trendBatchMetrics).recordFailure(any(), same(failure));
        verify(trendMetricRepository, never()).deleteAllInBatch();
    }

    private void fixClockAt2026July18At1530Kst() {
        when(clock.instant()).thenReturn(Instant.parse("2026-07-18T06:30:00Z"));
    }

    private Object[] evidence(long articleId, LocalDateTime publishedAt, String category, String keyword) {
        return new Object[]{articleId, publishedAt, category, keyword};
    }

    @SuppressWarnings({"rawtypes", "unchecked"})
    private List<TrendMetric> captureSavedMetrics() {
        ArgumentCaptor<Iterable> captor = ArgumentCaptor.forClass(Iterable.class);
        verify(trendMetricRepository).saveAll(captor.capture());
        List<TrendMetric> metrics = new ArrayList<>();
        captor.getValue().forEach(value -> metrics.add((TrendMetric) value));
        return metrics;
    }
}

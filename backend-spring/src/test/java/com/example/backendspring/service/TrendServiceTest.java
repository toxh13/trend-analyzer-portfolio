package com.example.backendspring.service;

import com.example.backendspring.dto.ArticleResponseDto;
import com.example.backendspring.dto.TrendHistoryDto;
import com.example.backendspring.dto.TrendHistoryComparisonResponseDto;
import com.example.backendspring.dto.TrendingResponseDto;
import com.example.backendspring.entity.Article;
import com.example.backendspring.entity.TrendMetric;
import com.example.backendspring.repository.ArticleKeywordRepository;
import com.example.backendspring.repository.ArticleRepository;
import com.example.backendspring.repository.TrendMetricRepository;
import org.junit.jupiter.api.DisplayName;
import org.junit.jupiter.api.Test;
import org.junit.jupiter.api.extension.ExtendWith;
import org.mockito.InjectMocks;
import org.mockito.Mock;
import org.mockito.ArgumentCaptor;
import org.mockito.junit.jupiter.MockitoExtension;
import org.springframework.web.server.ResponseStatusException;

import java.time.Clock;
import java.time.Instant;
import java.time.LocalDateTime;
import java.util.List;
import java.util.Set;

import static org.assertj.core.api.Assertions.assertThat;
import static org.assertj.core.api.Assertions.assertThatThrownBy;
import static org.mockito.ArgumentMatchers.*;
import static org.mockito.Mockito.verify;
import static org.mockito.Mockito.when;

@ExtendWith(MockitoExtension.class)
class TrendServiceTest {

    @Mock
    private TrendMetricRepository trendMetricRepository;

    @Mock
    private ArticleRepository articleRepository;

    @Mock
    private ArticleKeywordRepository articleKeywordRepository;

    @Mock
    private KeywordAliasCacheService keywordAliasCacheService;

    @Mock
    private Clock clock;

    @InjectMocks
    private TrendService trendService;

    @Test
    @DisplayName("키워드 7일 히스토리는 서울 달력 00시부터 현재까지 집계하고 누락 날짜를 0으로 채운다")
    void getKeyword7DaysHistoryUsesSeoulCalendarWindow() {
        String targetKeyword = "LLM";
        fixClockAt2026July18At1530Kst();

        when(keywordAliasCacheService.resolveSearchKeywords(targetKeyword))
                .thenReturn(Set.of(targetKeyword));
        when(articleRepository.findDailyKeywordEvidence(anyCollection(), any(), any()))
                .thenReturn(List.of(
                        new Object[]{"2026-07-16", 101L, 5L},
                        new Object[]{"2026-07-18", 102L, 1L}
                ));

        List<TrendHistoryDto> result = trendService.getKeyword7DaysHistory(targetKeyword);

        assertThat(result).hasSize(7);
        assertThat(result.get(0).getDay()).isEqualTo("2026-07-12");
        assertThat(result.get(4).getArticleCount()).isEqualTo(1L);
        assertThat(result.get(4).getWeightedScore()).isEqualTo(1.16);
        assertThat(result.get(5).getArticleCount()).isZero();
        assertThat(result.get(5).getWeightedScore()).isZero();
        assertThat(result.get(6).getDay()).isEqualTo("2026-07-18");
        assertThat(result.get(6).getArticleCount()).isEqualTo(1L);
        assertThat(result.get(6).isPartial()).isTrue();
        assertThat(result.get(5).isPartial()).isFalse();

        ArgumentCaptor<LocalDateTime> startCaptor = ArgumentCaptor.forClass(LocalDateTime.class);
        ArgumentCaptor<LocalDateTime> endCaptor = ArgumentCaptor.forClass(LocalDateTime.class);
        verify(articleRepository).findDailyKeywordEvidence(anyCollection(), startCaptor.capture(), endCaptor.capture());
        assertThat(startCaptor.getValue()).isEqualTo(LocalDateTime.of(2026, 7, 12, 0, 0));
        assertThat(endCaptor.getValue()).isEqualTo(LocalDateTime.of(2026, 7, 18, 15, 30));
    }

    @Test
    @DisplayName("한 날짜의 기본 언급량은 고유 기사 수이고 반복 언급은 보조 점수에만 작게 반영한다")
    void getKeywordHistorySeparatesArticleCountAndWeightedScore() {
        fixClockAt2026July18At1530Kst();
        when(keywordAliasCacheService.resolveSearchKeywords("AI")).thenReturn(Set.of("AI", "인공지능"));
        when(articleRepository.findDailyKeywordEvidence(anyCollection(), any(), any()))
                .thenReturn(List.of(
                        new Object[]{"2026-07-18", 201L, 5L},
                        new Object[]{"2026-07-18", 202L, 1L}
                ));

        TrendHistoryDto today = trendService.getKeywordHistory("AI", 2).get(1);

        assertThat(today.getArticleCount()).isEqualTo(2L);
        assertThat(today.getWeightedScore()).isEqualTo(2.16);
    }

    @Test
    @DisplayName("조회 기간이 2일에서 30일 사이가 아니면 400 오류를 반환한다")
    void getKeywordHistoryRejectsDaysOutsideRange() {
        assertThatThrownBy(() -> trendService.getKeywordHistory("AI", 1))
                .isInstanceOf(ResponseStatusException.class)
                .hasMessageContaining("2~30");
        assertThatThrownBy(() -> trendService.getKeywordHistory("AI", 31))
                .isInstanceOf(ResponseStatusException.class)
                .hasMessageContaining("2~30");
    }

    @Test
    @DisplayName("두 입력이 같은 대표 키워드이면 비교를 400 오류로 차단한다")
    void compareKeywordHistoryRejectsSameCanonicalKeyword() {
        when(keywordAliasCacheService.resolveKeyword("AI")).thenReturn("인공지능");
        when(keywordAliasCacheService.resolveKeyword("인공지능")).thenReturn("인공지능");

        assertThatThrownBy(() -> trendService.compareKeywordHistory("AI", " 인공지능 ", 7))
                .isInstanceOf(ResponseStatusException.class)
                .hasMessageContaining("같은 대표 키워드");
    }

    @Test
    @DisplayName("비교 시계열은 같은 서울 기준 조회 구간을 공유한다")
    void compareKeywordHistorySharesOneWindow() {
        fixClockAt2026July18At1530Kst();
        when(keywordAliasCacheService.resolveKeyword("AI")).thenReturn("인공지능");
        when(keywordAliasCacheService.resolveKeyword("반도체")).thenReturn("반도체");
        when(keywordAliasCacheService.resolveSearchKeywords("인공지능")).thenReturn(Set.of("AI", "인공지능"));
        when(keywordAliasCacheService.resolveSearchKeywords("반도체")).thenReturn(Set.of("반도체"));
        when(articleRepository.findDailyKeywordEvidence(anyCollection(), any(), any())).thenReturn(List.of());

        TrendHistoryComparisonResponseDto response = trendService.compareKeywordHistory("AI", "반도체", 7);

        assertThat(response.getFirstCanonicalKeyword()).isEqualTo("인공지능");
        assertThat(response.getSecondCanonicalKeyword()).isEqualTo("반도체");
        assertThat(response.getTimezone()).isEqualTo("Asia/Seoul");
        assertThat(response.isTodayPartial()).isTrue();
        assertThat(response.getFirstHistory()).hasSize(7);
        assertThat(response.getSecondHistory()).hasSize(7);

        ArgumentCaptor<LocalDateTime> startCaptor = ArgumentCaptor.forClass(LocalDateTime.class);
        ArgumentCaptor<LocalDateTime> endCaptor = ArgumentCaptor.forClass(LocalDateTime.class);
        verify(articleRepository, org.mockito.Mockito.times(2))
                .findDailyKeywordEvidence(anyCollection(), startCaptor.capture(), endCaptor.capture());
        assertThat(startCaptor.getAllValues()).containsOnly(LocalDateTime.of(2026, 7, 12, 0, 0));
        assertThat(endCaptor.getAllValues()).containsOnly(LocalDateTime.of(2026, 7, 18, 15, 30));
    }

    private void fixClockAt2026July18At1530Kst() {
        when(clock.instant()).thenReturn(Instant.parse("2026-07-18T06:30:00Z"));
    }

    @Test
    @DisplayName("전체 트렌드는 alias 병합 후 Hotness Score 순으로 상위 20개를 반환한다")
    void getTop20TrendTest() {
        TrendMetric metric1 = TrendMetric.builder()
                .keyword("AI")
                .category("TECH")
                .hotnessScore(95.5F)
                .velocityScore(2.5F)
                .mentionCount(150)
                .build();

        TrendMetric metric2 = TrendMetric.builder()
                .keyword("Crypto")
                .category("FINANCE")
                .hotnessScore(88.0F)
                .velocityScore(-1.2F)
                .mentionCount(90)
                .build();

        when(trendMetricRepository.findAllByOrderByHotnessScoreDesc())
                .thenReturn(List.of(metric1, metric2));
        when(keywordAliasCacheService.resolveKeyword(anyString()))
                .thenAnswer(invocation -> invocation.getArgument(0));

        List<TrendingResponseDto> result = trendService.getTop20Trend();

        assertThat(result).hasSize(2);
        assertThat(result.get(0).getRank()).isEqualTo(1);
        assertThat(result.get(0).getKeyword()).isEqualTo("AI");
        assertThat(result.get(0).getChangeType()).isEqualTo("up");
        assertThat(result.get(0).getChangeValue()).isEqualTo(2);

        assertThat(result.get(1).getRank()).isEqualTo(2);
        assertThat(result.get(1).getKeyword()).isEqualTo("Crypto");
        assertThat(result.get(1).getChangeType()).isEqualTo("down");
        assertThat(result.get(1).getChangeValue()).isEqualTo(1);
    }

    @Test
    @DisplayName("카테고리 트렌드는 해당 카테고리 안에서 alias 병합 후 순위를 매긴다")
    void getTop20CategoryTrendTest() {
        TrendMetric metric1 = TrendMetric.builder()
                .keyword("AI")
                .category("TECH")
                .hotnessScore(95.5F)
                .velocityScore(2.5F)
                .mentionCount(150)
                .build();

        TrendMetric metric2 = TrendMetric.builder()
                .keyword("Docker")
                .category("TECH")
                .hotnessScore(88.0F)
                .velocityScore(-1.2F)
                .mentionCount(90)
                .build();

        TrendMetric metric3 = TrendMetric.builder()
                .keyword("Spring")
                .category("TECH")
                .hotnessScore(82.3F)
                .velocityScore(0.0F)
                .mentionCount(60)
                .build();

        when(trendMetricRepository.findByCategoryOrderByHotnessScoreDesc("TECH"))
                .thenReturn(List.of(metric1, metric2, metric3));
        when(keywordAliasCacheService.resolveKeyword(anyString()))
                .thenAnswer(invocation -> invocation.getArgument(0));

        List<TrendingResponseDto> result = trendService.getTop20CategoryTrend("TECH");

        assertThat(result).hasSize(3);
        assertThat(result.get(0).getRank()).isEqualTo(1);
        assertThat(result.get(0).getKeyword()).isEqualTo("AI");
        assertThat(result.get(0).getChangeType()).isEqualTo("up");
        assertThat(result.get(1).getRank()).isEqualTo(2);
        assertThat(result.get(1).getChangeType()).isEqualTo("down");
        assertThat(result.get(2).getRank()).isEqualTo(3);
        assertThat(result.get(2).getChangeType()).isEqualTo("same");
    }

    @Test
    @DisplayName("관련 기사 조회는 대표 키워드와 alias 묶음을 함께 검색한다")
    void getArticlesContainingKeywordTest() {
        Article article1 = Article.builder()
                .title("AI 플랫폼 출시")
                .sourceUrl("https://test1.com/news/1")
                .source("네이버")
                .category("IT")
                .publishedAt(LocalDateTime.now())
                .build();

        Article article2 = Article.builder()
                .title("인공지능 투자 확대")
                .sourceUrl("https://test2.com/news/2")
                .source("다음")
                .category("TECH")
                .publishedAt(LocalDateTime.now())
                .build();

        Set<String> searchKeywords = Set.of("인공지능", "AI", "Artificial Intelligence");
        when(keywordAliasCacheService.resolveSearchKeywords("인공지능"))
                .thenReturn(searchKeywords);
        when(articleRepository.findDistinctByKeywordsKeywordInOrderByPublishedAtDesc(searchKeywords))
                .thenReturn(List.of(article1, article2));

        List<ArticleResponseDto> result = trendService.getArticlesContainingKeyword("인공지능");

        assertThat(result).hasSize(2);
        assertThat(result)
                .extracting(ArticleResponseDto::getTitle)
                .containsExactly("AI 플랫폼 출시", "인공지능 투자 확대");
    }

    @Test
    @DisplayName("alias가 같은 대표 키워드로 해석되면 트렌드 점수를 합산한다")
    void getTop20TrendMergesAliases() {
        TrendMetric ai = TrendMetric.builder()
                .keyword("AI")
                .category("TECH")
                .hotnessScore(10.0F)
                .velocityScore(2.0F)
                .mentionCount(5)
                .build();

        TrendMetric artificialIntelligence = TrendMetric.builder()
                .keyword("Artificial Intelligence")
                .category("TECH")
                .hotnessScore(20.0F)
                .velocityScore(3.0F)
                .mentionCount(7)
                .build();

        when(trendMetricRepository.findAllByOrderByHotnessScoreDesc())
                .thenReturn(List.of(ai, artificialIntelligence));
        when(keywordAliasCacheService.resolveKeyword("AI")).thenReturn("인공지능");
        when(keywordAliasCacheService.resolveKeyword("Artificial Intelligence")).thenReturn("인공지능");

        List<TrendingResponseDto> result = trendService.getTop20Trend();

        assertThat(result).hasSize(1);
        assertThat(result.get(0).getKeyword()).isEqualTo("인공지능");
        assertThat(result.get(0).getMention_count()).isEqualTo(12);
        assertThat(result.get(0).getScore()).isEqualTo(30.0F);
        assertThat(result.get(0).getChangeValue()).isEqualTo(5);
    }

    @Test
    @DisplayName("급상승은 카테고리별 스냅샷을 대표 키워드로 합친 뒤 최종 변화량으로 정렬한다")
    void getTopSurgingTrendsUsesCanonicalSnapshot() {
        TrendMetric aiTech = TrendMetric.builder()
                .keyword("AI")
                .category("IT")
                .mentionCount(3)
                .velocityScore(2.0F)
                .hotnessScore(2.4F)
                .build();
        TrendMetric artificialIntelligenceEconomy = TrendMetric.builder()
                .keyword("인공지능")
                .category("경제")
                .mentionCount(4)
                .velocityScore(-1.0F)
                .hotnessScore(1.0F)
                .build();
        TrendMetric cloud = TrendMetric.builder()
                .keyword("클라우드")
                .category("IT")
                .mentionCount(2)
                .velocityScore(3.0F)
                .hotnessScore(2.6F)
                .build();

        when(trendMetricRepository.findAllByOrderByHotnessScoreDesc())
                .thenReturn(List.of(aiTech, artificialIntelligenceEconomy, cloud));
        when(keywordAliasCacheService.resolveKeyword("AI")).thenReturn("인공지능");
        when(keywordAliasCacheService.resolveKeyword("인공지능")).thenReturn("인공지능");
        when(keywordAliasCacheService.resolveKeyword("클라우드")).thenReturn("클라우드");

        List<TrendingResponseDto> result = trendService.getTopSurgingTrends(10, "ALL");

        assertThat(result).extracting(TrendingResponseDto::getKeyword)
                .containsExactly("클라우드", "인공지능");
        assertThat(result.get(1).getMention_count()).isEqualTo(7);
        assertThat(result.get(1).getChangeValue()).isEqualTo(1);
    }

    @Test
    @DisplayName("현재 24시간 0건인 이전 구간 전용 키워드는 인기 목록에서 제외한다")
    void getTopMentionedTrendsExcludesPreviousOnlyMetrics() {
        TrendMetric current = TrendMetric.builder()
                .keyword("LLM")
                .category("IT")
                .mentionCount(2)
                .velocityScore(1.0F)
                .hotnessScore(1.4F)
                .build();
        TrendMetric previousOnly = TrendMetric.builder()
                .keyword("레거시")
                .category("IT")
                .mentionCount(0)
                .velocityScore(-3.0F)
                .hotnessScore(-1.8F)
                .build();

        when(trendMetricRepository.findAllByOrderByHotnessScoreDesc())
                .thenReturn(List.of(current, previousOnly));
        when(keywordAliasCacheService.resolveKeyword(anyString()))
                .thenAnswer(invocation -> invocation.getArgument(0));

        List<TrendingResponseDto> result = trendService.getTopMentionedTrends(20);

        assertThat(result).singleElement()
                .extracting(TrendingResponseDto::getKeyword)
                .isEqualTo("LLM");
    }

    @Test
    @DisplayName("상단 통계는 서울 기준 24시간과 같은 스냅샷의 상승·하락 키워드를 사용한다")
    void getDashboardStatsUsesKstClockAndMetricSnapshot() {
        fixClockAt2026July18At1530Kst();
        TrendMetric rising = TrendMetric.builder()
                .keyword("LLM")
                .category("IT")
                .mentionCount(5)
                .velocityScore(3.0F)
                .hotnessScore(3.8F)
                .build();
        TrendMetric falling = TrendMetric.builder()
                .keyword("블록체인")
                .category("IT")
                .mentionCount(1)
                .velocityScore(-4.0F)
                .hotnessScore(-2.0F)
                .build();

        when(articleRepository.countArticlesWithinWindow(any(), any(), isNull())).thenReturn(6L);
        when(articleKeywordRepository.countDistinctKeywordsWithinWindow(any(), any(), isNull())).thenReturn(2L);
        when(trendMetricRepository.findAllByOrderByHotnessScoreDesc())
                .thenReturn(List.of(rising, falling));
        when(keywordAliasCacheService.resolveKeyword(anyString()))
                .thenAnswer(invocation -> invocation.getArgument(0));

        var result = trendService.getDashboardStatsWithin24Hours("ALL");

        assertThat(result.getRisingKeyword().getKeyword()).isEqualTo("LLM");
        assertThat(result.getRisingKeyword().getChangeAmount()).isEqualTo(3L);
        assertThat(result.getFallingKeyword().getKeyword()).isEqualTo("블록체인");
        assertThat(result.getFallingKeyword().getChangeAmount()).isEqualTo(-4L);

        ArgumentCaptor<LocalDateTime> startCaptor = ArgumentCaptor.forClass(LocalDateTime.class);
        ArgumentCaptor<LocalDateTime> endCaptor = ArgumentCaptor.forClass(LocalDateTime.class);
        verify(articleRepository).countArticlesWithinWindow(startCaptor.capture(), endCaptor.capture(), isNull());
        assertThat(startCaptor.getValue()).isEqualTo(LocalDateTime.of(2026, 7, 17, 15, 30));
        assertThat(endCaptor.getValue()).isEqualTo(LocalDateTime.of(2026, 7, 18, 15, 30));
    }
}

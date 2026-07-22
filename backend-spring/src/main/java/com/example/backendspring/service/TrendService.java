package com.example.backendspring.service;

import com.example.backendspring.dto.ArticleResponseDto;
import com.example.backendspring.dto.ArticleEvidenceDto;
import com.example.backendspring.dto.TrendHistoryDto;
import com.example.backendspring.dto.TrendHistoryComparisonResponseDto;
import com.example.backendspring.dto.TrendHistoryEvidenceResponseDto;
import com.example.backendspring.dto.TrendStatsKeywordDto;
import com.example.backendspring.dto.TrendStatsResponseDto;
import com.example.backendspring.dto.TrendingResponseDto;
import com.example.backendspring.entity.Article;
import com.example.backendspring.entity.TrendMetric;
import com.example.backendspring.repository.ArticleKeywordRepository;
import com.example.backendspring.repository.ArticleRepository;
import com.example.backendspring.repository.TrendMetricRepository;
import lombok.RequiredArgsConstructor;
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;
import org.springframework.http.HttpStatus;
import org.springframework.data.domain.PageRequest;
import org.springframework.web.server.ResponseStatusException;

import java.time.Clock;
import java.time.LocalDate;
import java.time.LocalDateTime;
import java.time.ZoneId;
import java.util.*;
import java.util.stream.Collectors;

/**
 * TrendService - 트렌드 관련 비즈니스 로직을 처리하는 서비스 클래스
 * 전체 트렌드, 카테고리별 트렌드 조회 및 키워드 관련 기사 조회 기능 제공
 */
@Service
@RequiredArgsConstructor
@Transactional(readOnly = true)
public class TrendService {
    private static final int DASHBOARD_STATS_WINDOW_HOURS = 24;
    private static final int MIN_HISTORY_DAYS = 2;
    private static final int MAX_HISTORY_DAYS = 30;
    private static final int MIN_EVIDENCE_LIMIT = 1;
    private static final int MAX_EVIDENCE_LIMIT = 5;
    private static final double REPEATED_MENTION_BONUS_LIMIT = 0.2;
    private static final ZoneId TREND_ZONE = ZoneId.of("Asia/Seoul");

    // 트렌드 메트릭 데이터에 접근하는 Repository
    private final TrendMetricRepository trendMetricRepository;
    // 뉴스 기사 데이터에 접근하는 Repository
    private final ArticleRepository articleRepository;
    // 기사별 키워드 데이터에 접근하는 Repository
    private final ArticleKeywordRepository articleKeywordRepository;

    /**
     * 승인된 alias를 대표 키워드로 변환하기 위한 캐시 서비스입니다.
     * 예: AI -> 인공지능
     */
    private final KeywordAliasCacheService keywordAliasCacheService;
    private final Clock clock;
    /**
     * 전체 트렌드 상위 20개 조회
     * 핫스코어(Hotness Score) 기준으로 내림차순 정렬하여 상위 20개의 트렌드 메트릭 조회
     *
     * @return TrendingResponseDto 리스트 - 전체 상위 20개 트렌드 정보
     */
    public List<TrendingResponseDto> getTop20Trend() {
        // alias 병합 후 순위를 다시 계산해야 하므로 Top20이 아니라 전체 목록을 조회합니다.
        List<TrendMetric> trendMetricList = trendMetricRepository.findAllByOrderByHotnessScoreDesc();

        // 승인된 alias를 대표 키워드로 합산한 뒤 Top20을 반환합니다.
        return mergeAliasesAndConvertToDtoList(trendMetricList);
    }
    /**
     * 카테고리별 트렌드 상위 20개 조회
     * 특정 카테고리에서 핫스코어 기준으로 내림차순 정렬하여 상위 20개의 트렌드 조회
     *
     * @param category 조회할 카테고리명
     * @return TrendingResponseDto 리스트 - 해당 카테고리의 상위 20개 트렌드 정보
     */
    public List<TrendingResponseDto> getTop20CategoryTrend(String category) {
        // 카테고리별로도 alias 병합 후 순위를 다시 계산해야 합니다.
        List<TrendMetric> trendMetricList = trendMetricRepository.findByCategoryOrderByHotnessScoreDesc(category);

        return mergeAliasesAndConvertToDtoList(trendMetricList);
    }

    public List<TrendingResponseDto> getTopMentionedTrends(int limit) {
        int safeLimit = clampLimit(limit, 20);
        List<MergedTrendSummary> sortedSummaries = mergeAliases(trendMetricRepository.findAllByOrderByHotnessScoreDesc())
                .stream()
                .filter(summary -> summary.mentionCount > 0)
                .sorted(Comparator
                        .comparingInt((MergedTrendSummary summary) -> summary.mentionCount)
                        .thenComparing(summary -> summary.hotnessScore)
                        .reversed()
                )
                .limit(safeLimit)
                .toList();

        return convertSummariesToDtoList(sortedSummaries);
    }

    public List<TrendingResponseDto> getTopSurgingTrends(int limit, String categoryName) {
        int safeLimit = clampLimit(limit, 10);
        String normalizedCategoryName = normalizeCategoryName(categoryName);
        List<MergedTrendSummary> sortedSummaries = mergeAliases(loadMetricSnapshot(normalizedCategoryName))
                .stream()
                .filter(summary -> summary.mentionCount > 0 && summary.velocityScore > 0)
                .sorted(Comparator
                        .comparingDouble((MergedTrendSummary summary) -> summary.velocityScore)
                        .thenComparingInt(summary -> summary.mentionCount)
                        .reversed()
                )
                .limit(safeLimit)
                .toList();

        return convertSummariesToDtoList(sortedSummaries);
    }

    /**
     * 프론트엔드 상단 통계 카드에 필요한 값을 최근 24시간 기준으로 계산합니다.
     * categoryName이 ALL 또는 빈 값이면 전체 카테고리, 특정 값이면 해당 카테고리만 집계합니다.
     */
    public TrendStatsResponseDto getDashboardStatsWithin24Hours(String categoryName) {
        String normalizedCategoryName = normalizeCategoryName(categoryName);
        LocalDateTime endDate = LocalDateTime.ofInstant(clock.instant(), TREND_ZONE);
        LocalDateTime currentStart = endDate.minusHours(DASHBOARD_STATS_WINDOW_HOURS);

        long analyzedArticles = articleRepository.countArticlesWithinWindow(
                currentStart,
                endDate,
                normalizedCategoryName
        );
        long trackedKeywords = articleKeywordRepository.countDistinctKeywordsWithinWindow(
                currentStart,
                endDate,
                normalizedCategoryName
        );

        Collection<MergedTrendSummary> snapshot = mergeAliases(loadMetricSnapshot(normalizedCategoryName));
        TrendStatsKeywordDto risingKeyword = findTopChangedKeyword(snapshot, true).orElse(null);
        TrendStatsKeywordDto fallingKeyword = findTopChangedKeyword(snapshot, false).orElse(null);

        return TrendStatsResponseDto.builder()
                .analyzedArticles(analyzedArticles)
                .trackedKeywords(trackedKeywords)
                .risingKeyword(risingKeyword)
                .fallingKeyword(fallingKeyword)
                .windowHours(DASHBOARD_STATS_WINDOW_HOURS)
                .build();
    }

    /**
     * 특정 키워드 관련 뉴스 기사 목록 조회
     * 입력한 키워드와 관련된 모든 뉴스 기사를 발행일 기준 최신순으로 조회
     *
     * @param keyword 검색 키워드
     * @return Article 리스트 - 해당 키워드와 연관된 기사 목록 (최신순)
     */
    public List<ArticleResponseDto> getArticlesContainingKeyword(String keyword) {

        // 메인 페이지에 표시된 대표 키워드를 기준으로 실제 조회해야 할 원본 키워드 묶음을 가져옵니다.
        // 예: "인공지능" -> ["인공지능", "AI", "Artificial Intelligence"]
        Set<String> searchKeywords = keywordAliasCacheService.resolveSearchKeywords(keyword);

        List<Article> articles = articleRepository.findDistinctByKeywordsKeywordInOrderByPublishedAtDesc(searchKeywords);
        return articles.stream()
                .map(article -> ArticleResponseDto.builder()
                        .id("article -" + article.getId())
                        .title(article.getTitle())
                        .source(article.getSource())
                        .date(article.getPublishedAt().toString())
                        .url(article.getSourceUrl())
                        .build())
                .collect(Collectors.toList());
    }

    public List<TrendHistoryDto> getKeywordHistory(String keyword, int days) {
        HistoryWindow window = createHistoryWindow(days);
        Set<String> searchKeywords = keywordAliasCacheService.resolveSearchKeywords(normalizeHistoryKeyword(keyword));
        return buildKeywordHistory(searchKeywords, window);
    }

    public TrendHistoryComparisonResponseDto compareKeywordHistory(
            String firstKeyword,
            String secondKeyword,
            int days
    ) {
        validateHistoryDays(days);
        String normalizedFirstKeyword = normalizeHistoryKeyword(firstKeyword);
        String normalizedSecondKeyword = normalizeHistoryKeyword(secondKeyword);
        String firstCanonicalKeyword = keywordAliasCacheService.resolveKeyword(normalizedFirstKeyword).trim();
        String secondCanonicalKeyword = keywordAliasCacheService.resolveKeyword(normalizedSecondKeyword).trim();

        if (firstCanonicalKeyword.equalsIgnoreCase(secondCanonicalKeyword)) {
            throw new ResponseStatusException(
                    HttpStatus.BAD_REQUEST,
                    "두 입력은 같은 대표 키워드로 해석되어 비교할 수 없습니다. 서로 다른 키워드를 입력해주세요."
            );
        }

        HistoryWindow window = createHistoryWindow(days);
        List<TrendHistoryDto> firstHistory = buildKeywordHistory(
                keywordAliasCacheService.resolveSearchKeywords(firstCanonicalKeyword),
                window
        );
        List<TrendHistoryDto> secondHistory = buildKeywordHistory(
                keywordAliasCacheService.resolveSearchKeywords(secondCanonicalKeyword),
                window
        );

        return TrendHistoryComparisonResponseDto.builder()
                .firstRequestedKeyword(normalizedFirstKeyword)
                .secondRequestedKeyword(normalizedSecondKeyword)
                .firstCanonicalKeyword(firstCanonicalKeyword)
                .secondCanonicalKeyword(secondCanonicalKeyword)
                .days(days)
                .timezone(TREND_ZONE.getId())
                .todayPartial(true)
                .firstHistory(firstHistory)
                .secondHistory(secondHistory)
                .build();
    }

    public TrendHistoryEvidenceResponseDto getKeywordHistoryEvidence(
            String firstKeyword,
            String secondKeyword,
            LocalDate date,
            int limit
    ) {
        validateEvidenceLimit(limit);
        if (date == null) {
            throw new ResponseStatusException(HttpStatus.BAD_REQUEST, "date는 필수입니다.");
        }

        String normalizedFirstKeyword = normalizeHistoryKeyword(firstKeyword);
        String normalizedSecondKeyword = normalizeHistoryKeyword(secondKeyword);
        String firstCanonicalKeyword = keywordAliasCacheService.resolveKeyword(normalizedFirstKeyword).trim();
        String secondCanonicalKeyword = keywordAliasCacheService.resolveKeyword(normalizedSecondKeyword).trim();

        if (firstCanonicalKeyword.equalsIgnoreCase(secondCanonicalKeyword)) {
            throw new ResponseStatusException(
                    HttpStatus.BAD_REQUEST,
                    "두 입력은 같은 대표 키워드로 해석되어 비교할 수 없습니다. 서로 다른 키워드를 입력해주세요."
            );
        }

        LocalDateTime startDateTime = date.atStartOfDay();
        LocalDateTime endDateTime = date.plusDays(1).atStartOfDay();
        PageRequest pageRequest = PageRequest.of(0, limit);

        List<ArticleEvidenceDto> firstArticles = loadEvidenceArticles(
                firstCanonicalKeyword, startDateTime, endDateTime, pageRequest
        );
        List<ArticleEvidenceDto> secondArticles = loadEvidenceArticles(
                secondCanonicalKeyword, startDateTime, endDateTime, pageRequest
        );

        return TrendHistoryEvidenceResponseDto.builder()
                .date(date.toString())
                .timezone(TREND_ZONE.getId())
                .firstCanonicalKeyword(firstCanonicalKeyword)
                .secondCanonicalKeyword(secondCanonicalKeyword)
                .firstArticles(firstArticles)
                .secondArticles(secondArticles)
                .build();
    }

    private List<ArticleEvidenceDto> loadEvidenceArticles(
            String canonicalKeyword,
            LocalDateTime startDateTime,
            LocalDateTime endDateTime,
            PageRequest pageRequest
    ) {
        return articleRepository.findEvidenceByKeywordsWithinWindow(
                        keywordAliasCacheService.resolveSearchKeywords(canonicalKeyword),
                        startDateTime,
                        endDateTime,
                        pageRequest
                ).stream()
                .map(article -> ArticleEvidenceDto.builder()
                        .id(article.getId())
                        .title(article.getTitle())
                        .summary(article.getSummary())
                        .source(article.getSource())
                        .publishedAt(article.getPublishedAt() == null
                                ? null
                                : article.getPublishedAt().atZone(TREND_ZONE).toOffsetDateTime())
                        .sourceUrl(article.getSourceUrl())
                        .build())
                .toList();
    }

    private List<TrendHistoryDto> buildKeywordHistory(Set<String> searchKeywords, HistoryWindow window) {
        List<Object[]> dbData = articleRepository.findDailyKeywordEvidence(
                searchKeywords,
                window.startDateTime,
                window.endDateTime
        );
        Map<String, DailyHistorySummary> summaryByDay = new HashMap<>();

        if (dbData != null) {
            for (Object[] row : dbData) {
                if (row == null || row.length < 3 || row[0] == null) {
                    continue;
                }

                String day = String.valueOf(row[0]).trim();
                long occurrenceCount = Math.max(1L, toLong(row[2]));
                DailyHistorySummary summary = summaryByDay.computeIfAbsent(day, key -> new DailyHistorySummary());
                summary.articleCount++;
                summary.weightedScore += calculateArticleWeight(occurrenceCount);
            }
        }

        List<TrendHistoryDto> history = new ArrayList<>();
        for (int i = 0; i < window.days; i++) {
            LocalDate day = window.startDate.plusDays(i);
            DailyHistorySummary summary = summaryByDay.getOrDefault(day.toString(), new DailyHistorySummary());
            history.add(TrendHistoryDto.builder()
                    .day(day.toString())
                    .articleCount(summary.articleCount)
                    .weightedScore(roundToThreeDecimals(summary.weightedScore))
                    .partial(day.equals(window.today))
                    .build());
        }
        return history;
    }

    public List<TrendHistoryDto> getKeyword7DaysHistory(String keyword) {
        return getKeywordHistory(keyword, 7);
    }

    private HistoryWindow createHistoryWindow(int days) {
        validateHistoryDays(days);
        LocalDateTime nowInSeoul = LocalDateTime.ofInstant(clock.instant(), TREND_ZONE);
        LocalDate today = nowInSeoul.toLocalDate();
        LocalDate startDate = today.minusDays(days - 1L);
        return new HistoryWindow(days, today, startDate, startDate.atStartOfDay(), nowInSeoul);
    }

    private void validateHistoryDays(int days) {
        if (days < MIN_HISTORY_DAYS || days > MAX_HISTORY_DAYS) {
            throw new ResponseStatusException(HttpStatus.BAD_REQUEST, "days는 2~30 사이여야 합니다.");
        }
    }

    private void validateEvidenceLimit(int limit) {
        if (limit < MIN_EVIDENCE_LIMIT || limit > MAX_EVIDENCE_LIMIT) {
            throw new ResponseStatusException(HttpStatus.BAD_REQUEST, "limit는 1~5 사이여야 합니다.");
        }
    }

    private String normalizeHistoryKeyword(String keyword) {
        if (keyword == null || keyword.isBlank()) {
            throw new ResponseStatusException(HttpStatus.BAD_REQUEST, "키워드는 비어 있을 수 없습니다.");
        }
        return keyword.trim();
    }

    private double calculateArticleWeight(long occurrenceCount) {
        return 1.0 + REPEATED_MENTION_BONUS_LIMIT * (1.0 - (1.0 / occurrenceCount));
    }

    private double roundToThreeDecimals(double value) {
        return Math.round(value * 1000.0) / 1000.0;
    }

    /**
     * TrendMetric 엔티티 리스트를 TrendingResponseDto 리스트로 변환하는 헬퍼 메서드
     * 각 트렌드의 순위, 변화 추이, 변화값 등을 계산하여 DTO 생성
     *
     * @param trendMetricList 변환할 TrendMetric 엔티티 리스트
     * @return TrendingResponseDto 리스트 - 변환된 응답 DTO
     */
    private List<TrendingResponseDto> convertToDtoList(List<TrendMetric> trendMetricList) {
        // 변환된 DTO를 저장할 리스트 초기화
        List<TrendingResponseDto> trendingResponseDtoList = new ArrayList<>();

        // 현재 순위를 추적하는 변수 (1부터 시작)
        int currentRank = 1;

        // 각 트렌드 메트릭을 순회하며 DTO로 변환
        for (TrendMetric trendMetric : trendMetricList) {
            // 속도 점수(Velocity Score)를 기반으로 변화 추이 결정
            String changeType = "same";  // 기본값: 변화 없음
            if (trendMetric.getVelocityScore() > 0) {
                changeType = "up";  // 상승
            } else if (trendMetric.getVelocityScore() < 0) {
                changeType = "down";  // 하강
            }

            // TrendingResponseDto 빌더 패턴으로 객체 생성
            TrendingResponseDto dto = TrendingResponseDto.builder()
                    .id(String.valueOf(trendMetric.getId()))
                    .keyword(trendMetric.getKeyword())  // 키워드
                    .category(trendMetric.getCategory())  // 카테고리
                    .changeType(changeType)  // 변화 추이 (up, down, same)
                    .score(trendMetric.getHotnessScore())  // 핫스코어
                    .rank(currentRank++)  // 순위 (1, 2, 3, ...)
                    .mention_count(trendMetric.getMentionCount())  // 언급 횟수
                    .changeValue((int) Math.abs(trendMetric.getVelocityScore()))  // 변화값 (절댓값)
                    .build();

            // 생성된 DTO를 리스트에 추가
            trendingResponseDtoList.add(dto);
        }

        // 변환된 DTO 리스트 반환
        return trendingResponseDtoList;
    }

    private String normalizeCategoryName(String categoryName) {
        if (categoryName == null || categoryName.isBlank() || "ALL".equalsIgnoreCase(categoryName)) {
            return null;
        }
        return categoryName.trim();
    }

    private int clampLimit(int limit, int defaultLimit) {
        if (limit <= 0) {
            return defaultLimit;
        }
        return Math.min(limit, 50);
    }

    private List<TrendMetric> loadMetricSnapshot(String categoryName) {
        if (categoryName == null) {
            return trendMetricRepository.findAllByOrderByHotnessScoreDesc();
        }
        return trendMetricRepository.findByCategoryOrderByHotnessScoreDesc(categoryName);
    }

    private Optional<TrendStatsKeywordDto> findTopChangedKeyword(
            Collection<MergedTrendSummary> snapshot,
            boolean rising
    ) {
        Comparator<MergedTrendSummary> comparator = Comparator
                .comparingDouble((MergedTrendSummary summary) -> Math.abs(summary.velocityScore))
                .thenComparingInt(summary -> summary.mentionCount)
                .reversed();

        return snapshot.stream()
                .filter(summary -> rising ? summary.velocityScore > 0 : summary.velocityScore < 0)
                .sorted(comparator)
                .findFirst()
                .map(summary -> TrendStatsKeywordDto.builder()
                        .keyword(summary.keyword)
                        .mentionCount(summary.mentionCount)
                        .changeAmount((long) summary.velocityScore)
                        .build());
    }

    private long toLong(Object value) {
        if (value instanceof Number number) {
            return number.longValue();
        }
        if (value == null) {
            return 0L;
        }
        return Long.parseLong(String.valueOf(value));
    }

    private static class DailyHistorySummary {
        private long articleCount;
        private double weightedScore;
    }

    private record HistoryWindow(
            int days,
            LocalDate today,
            LocalDate startDate,
            LocalDateTime startDateTime,
            LocalDateTime endDateTime
    ) {
    }

    /**
     * alias 병합 후 하나의 대표 키워드로 합쳐진 트렌드 요약 객체입니다.
     *
     * 예:
     * AI: 10
     * 인공지능: 15
     * Artificial Intelligence: 5
     *
     * alias 적용 후:
     * 인공지능: 30
     */
    private static class MergedTrendSummary {

        private final String keyword;
        private String category;
        private int mentionCount;
        private float velocityScore;
        private float hotnessScore;

        private MergedTrendSummary(String keyword, String category) {
            this.keyword = keyword;
            this.category = category;
        }

        /**
         * 같은 대표 키워드로 묶인 TrendMetric 값을 합산합니다.
         */
        private void add(TrendMetric metric) {
            this.mentionCount += metric.getMentionCount();
            this.velocityScore += metric.getVelocityScore();
            this.hotnessScore += metric.getHotnessScore();

            // 카테고리가 비어 있으면 새 metric의 카테고리를 사용합니다.
            if ((this.category == null || this.category.isBlank()) && metric.getCategory() != null) {
                this.category = metric.getCategory();
            }
        }
    }
    /**
     * trend_metrics 목록에 alias 병합 규칙을 적용한 뒤 TrendingResponseDto로 변환합니다.
     *
     * 핵심 순서:
     * 1. 원본 키워드를 alias cache로 대표 키워드 변환
     * 2. 같은 대표 키워드끼리 mentionCount / velocityScore / hotnessScore 합산
     * 3. 합산된 hotnessScore 기준으로 다시 정렬
     * 4. 최종 Top20 반환
     */
    private Collection<MergedTrendSummary> mergeAliases(List<TrendMetric> trendMetricList) {
        Map<String, MergedTrendSummary> mergedMap = new HashMap<>();

        for (TrendMetric trendMetric : trendMetricList) {
            String displayKeyword = keywordAliasCacheService.resolveKeyword(trendMetric.getKeyword());

            MergedTrendSummary summary = mergedMap.computeIfAbsent(
                    displayKeyword,
                    key -> new MergedTrendSummary(displayKeyword, trendMetric.getCategory())
            );

            summary.add(trendMetric);
        }

        return mergedMap.values();
    }

    private List<TrendingResponseDto> convertSummariesToDtoList(List<MergedTrendSummary> sortedSummaries) {
        List<TrendingResponseDto> result = new ArrayList<>();

        int currentRank = 1;
        for (MergedTrendSummary summary : sortedSummaries) {
            String changeType = "same";

            if (summary.velocityScore > 0) {
                changeType = "up";
            } else if (summary.velocityScore < 0) {
                changeType = "down";
            }

            result.add(TrendingResponseDto.builder()
                    .id("keyword-" + summary.keyword)
                    .keyword(summary.keyword)
                    .category(summary.category)
                    .changeType(changeType)
                    .score(summary.hotnessScore)
                    .rank(currentRank++)
                    .mention_count(summary.mentionCount)
                    .changeValue((int) Math.abs(summary.velocityScore))
                    .build());
        }

        return result;
    }

    private List<TrendingResponseDto> mergeAliasesAndConvertToDtoList(List<TrendMetric> trendMetricList) {
        Map<String, MergedTrendSummary> mergedMap = new HashMap<>();

        for (TrendMetric trendMetric : trendMetricList) {
            // 승인된 alias가 있으면 대표 키워드로 변환하고,
            // alias가 없으면 원본 키워드를 그대로 사용합니다.
            String displayKeyword = keywordAliasCacheService.resolveKeyword(trendMetric.getKeyword());

            MergedTrendSummary summary = mergedMap.computeIfAbsent(
                    displayKeyword,
                    key -> new MergedTrendSummary(displayKeyword, trendMetric.getCategory())
            );

            summary.add(trendMetric);
        }

        List<MergedTrendSummary> sortedSummaries = mergedMap.values()
                .stream()
                .filter(summary -> summary.mentionCount > 0)
                // 대표 키워드 기준으로 합산한 뒤 hotnessScore 기준으로 다시 정렬합니다.
                .sorted((a, b) -> Float.compare(b.hotnessScore, a.hotnessScore))
                .limit(20)
                .toList();

        List<TrendingResponseDto> result = new ArrayList<>();

        int currentRank = 1;
        for (MergedTrendSummary summary : sortedSummaries) {
            String changeType = "same";

            if (summary.velocityScore > 0) {
                changeType = "up";
            } else if (summary.velocityScore < 0) {
                changeType = "down";
            }

            result.add(TrendingResponseDto.builder()
                    // 병합된 결과는 특정 trend_metrics id 하나로 표현하기 어렵기 때문에
                    // 프론트 key 충돌을 피하기 위해 대표 키워드 기반 id를 사용합니다.
                    .id("keyword-" + summary.keyword)
                    .keyword(summary.keyword)
                    .category(summary.category)
                    .changeType(changeType)
                    .score(summary.hotnessScore)
                    .rank(currentRank++)
                    .mention_count(summary.mentionCount)
                    .changeValue((int) Math.abs(summary.velocityScore))
                    .build());
        }

        return result;
    }
}

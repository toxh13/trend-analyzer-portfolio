package com.example.backendspring.controller;

import com.example.backendspring.dto.ArticleResponseDto;
import com.example.backendspring.dto.TrendHistoryDto;
import com.example.backendspring.dto.TrendHistoryComparisonResponseDto;
import com.example.backendspring.dto.TrendHistoryEvidenceResponseDto;
import com.example.backendspring.dto.TrendStatsResponseDto;
import com.example.backendspring.dto.TrendingResponseDto;
import com.example.backendspring.service.TrendService;
import lombok.RequiredArgsConstructor;
import lombok.extern.slf4j.Slf4j;
import org.springframework.format.annotation.DateTimeFormat;
import org.springframework.http.ResponseEntity;
import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.RequestMapping;
import org.springframework.web.bind.annotation.RequestParam;
import org.springframework.web.bind.annotation.RestController;

import java.time.LocalDate;
import java.util.List;

@RestController
@RequiredArgsConstructor
@Slf4j
@RequestMapping("/api/v1/trends")
public class TrendController {

    private final TrendService trendService;

    @GetMapping
    public ResponseEntity<List<TrendingResponseDto>> getTrends() {
        log.info("전체 트렌드 조회");
        List<TrendingResponseDto> dtoList = trendService.getTop20Trend();
        return ResponseEntity.ok(dtoList);
    }

    @GetMapping("/popular")
    public ResponseEntity<List<TrendingResponseDto>> getPopularTrends(
            @RequestParam(defaultValue = "20") int limit
    ) {
        log.info("언급량 기준 인기 키워드 조회: limit={}", limit);
        List<TrendingResponseDto> dtoList = trendService.getTopMentionedTrends(limit);
        return ResponseEntity.ok(dtoList);
    }

    @GetMapping("/surging")
    public ResponseEntity<List<TrendingResponseDto>> getSurgingTrends(
            @RequestParam(defaultValue = "10") int limit,
            @RequestParam(required = false) String categoryName
    ) {
        log.info("급상승 키워드 조회: limit={}, categoryName={}", limit, categoryName);
        List<TrendingResponseDto> dtoList = trendService.getTopSurgingTrends(limit, categoryName);
        return ResponseEntity.ok(dtoList);
    }

    @GetMapping("/category")
    public ResponseEntity<List<TrendingResponseDto>> getTrendsByCategory(@RequestParam String categoryName) {
        log.info("카테고리별 트렌드 조회: {}", categoryName);
        List<TrendingResponseDto> dtoList = trendService.getTop20CategoryTrend(categoryName);
        return ResponseEntity.ok(dtoList);
    }

    @GetMapping("/stats")
    public ResponseEntity<TrendStatsResponseDto> getDashboardStats(
            @RequestParam(required = false) String categoryName
    ) {
        log.info("24시간 대시보드 통계 조회: categoryName={}", categoryName);
        TrendStatsResponseDto stats = trendService.getDashboardStatsWithin24Hours(categoryName);
        return ResponseEntity.ok(stats);
    }

    @GetMapping("/articles")
    public ResponseEntity<List<ArticleResponseDto>> getTrendArticles(@RequestParam String keyword) {
        log.info("키워드 관련 기사 조회: {}", keyword);
        List<ArticleResponseDto> dtoList = trendService.getArticlesContainingKeyword(keyword);
        return ResponseEntity.ok(dtoList);
    }

    @GetMapping("/history")
    public ResponseEntity<List<TrendHistoryDto>> getKeywordHistory(
            @RequestParam String keyword,
            @RequestParam(defaultValue = "7") int days
    ) {
        log.info("키워드 스코어 추이 조회: keyword={}, days={}", keyword, days);
        List<TrendHistoryDto> historyList = trendService.getKeywordHistory(keyword, days);
        return ResponseEntity.ok(historyList);
    }

    @GetMapping("/history/compare")
    public ResponseEntity<TrendHistoryComparisonResponseDto> compareKeywordHistory(
            @RequestParam String firstKeyword,
            @RequestParam String secondKeyword,
            @RequestParam(defaultValue = "7") int days
    ) {
        log.info("키워드 스코어 비교 조회: firstKeyword={}, secondKeyword={}, days={}",
                firstKeyword, secondKeyword, days);
        return ResponseEntity.ok(trendService.compareKeywordHistory(firstKeyword, secondKeyword, days));
    }

    @GetMapping("/history/evidence")
    public ResponseEntity<TrendHistoryEvidenceResponseDto> getKeywordHistoryEvidence(
            @RequestParam String firstKeyword,
            @RequestParam String secondKeyword,
            @RequestParam @DateTimeFormat(iso = DateTimeFormat.ISO.DATE) LocalDate date,
            @RequestParam(defaultValue = "5") int limit
    ) {
        log.info("키워드 날짜별 기사 근거 조회: firstKeyword={}, secondKeyword={}, date={}, limit={}",
                firstKeyword, secondKeyword, date, limit);
        return ResponseEntity.ok(
                trendService.getKeywordHistoryEvidence(firstKeyword, secondKeyword, date, limit)
        );
    }
}

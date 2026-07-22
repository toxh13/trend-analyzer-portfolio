package com.example.backendspring.service;

import com.example.backendspring.repository.ArticleKeywordRepository;
import com.example.backendspring.repository.ArticleRepository;
import jakarta.transaction.Transactional;
import lombok.RequiredArgsConstructor;
import lombok.extern.slf4j.Slf4j;
import org.springframework.beans.factory.annotation.Value;
import org.springframework.scheduling.annotation.Scheduled;
import org.springframework.stereotype.Service;

import java.time.LocalDateTime;

/**
 * 뉴스 원천 데이터 보관 정책 정리 배치입니다.
 *
 * 정책:
 * - articles: 30일 보관
 * - article_keywords: 45일 보관
 * - trend_metrics: 트렌드 배치가 최신 스냅샷으로 교체하므로 이 보관 배치에서는 삭제하지 않음
 *
 * 주의:
 * - articles 삭제 전 FK로 연결된 article_keywords를 먼저 삭제합니다.
 * - trend_metrics의 생성·교체 책임은 TrendAnalysticService에 있습니다.
 */
@Service
@RequiredArgsConstructor
@Slf4j
public class DataRetentionCleanupService {

    private final ArticleRepository articleRepository;
    private final ArticleKeywordRepository articleKeywordRepository;

    @Value("${app.retention.article-days:30}")
    private int articleRetentionDays;

    @Value("${app.retention.article-keyword-days:45}")
    private int articleKeywordRetentionDays;

    /**
     * 매일 새벽 3시 30분에 오래된 기사/키워드 원천 데이터를 정리합니다.
     * 서버 부하가 낮은 시간대에 실행하도록 설정했습니다.
     */
    @Scheduled(cron = "${app.retention.cleanup-cron:0 30 3 * * *}")
    @Transactional
    public void cleanupExpiredSourceData() {
        LocalDateTime now = LocalDateTime.now();
        LocalDateTime articleCutoffDate = now.minusDays(articleRetentionDays);
        LocalDateTime keywordCutoffDate = now.minusDays(articleKeywordRetentionDays);

        log.info(
                "🧹 데이터 보관정책 정리 시작 - articles: {}일, article_keywords: {}일, trend_metrics: 유지",
                articleRetentionDays,
                articleKeywordRetentionDays
        );

        // 1. 30일이 지난 기사에 연결된 키워드를 먼저 삭제합니다.
        //    FK 제약 때문에 article 삭제보다 먼저 실행해야 합니다.
        int keywordsDeletedByExpiredArticles = articleKeywordRepository.deleteKeywordsOfExpiredArticles(articleCutoffDate);

        // 2. 기사 자체는 30일이 지난 데이터를 삭제합니다.
        int expiredArticlesDeleted = articleRepository.deleteExpiredArticles(articleCutoffDate);

        // 3. article_keyword 자체 보관기간 45일을 초과한 데이터를 정리합니다.
        //    현재 articles 30일 정책 때문에 대부분 1번에서 먼저 정리되지만, 정책 변경에 대비해 유지합니다.
        int expiredKeywordsDeleted = articleKeywordRepository.deleteExpiredKeywords(keywordCutoffDate);

        // 4. 방어적으로 부모 기사 없이 남은 키워드를 정리합니다.
        int orphanKeywordsDeleted = articleKeywordRepository.deleteOrphanKeywords();

        log.info(
                "✅ 데이터 보관정책 정리 완료 - expiredArticleKeywords: {}, expiredArticles: {}, expiredKeywords: {}, orphanKeywords: {}",
                keywordsDeletedByExpiredArticles,
                expiredArticlesDeleted,
                expiredKeywordsDeleted,
                orphanKeywordsDeleted
        );
    }
}

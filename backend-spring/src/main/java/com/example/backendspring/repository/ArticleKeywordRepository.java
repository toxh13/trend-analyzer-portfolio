package com.example.backendspring.repository;

import com.example.backendspring.entity.ArticleKeyword;
import org.springframework.data.jpa.repository.JpaRepository;
import org.springframework.data.jpa.repository.Modifying;
import org.springframework.data.jpa.repository.Query;
import org.springframework.data.repository.query.Param;

import java.time.LocalDateTime;
import java.util.List;

public interface ArticleKeywordRepository extends JpaRepository<ArticleKeyword, Long> {

    /**
     * 트렌드 배치에 필요한 최소 근거만 조회합니다.
     * 반환 컬럼: articleId, publishedAt, category, rawKeyword
     */
    @Query("SELECT a.id, a.publishedAt, a.category, k.keyword " +
            "FROM ArticleKeyword k JOIN k.article a " +
            "WHERE a.publishedAt >= :startDate AND a.publishedAt < :endDate")
    List<Object[]> findTrendEvidenceWithinWindow(
            @Param("startDate") LocalDateTime startDate,
            @Param("endDate") LocalDateTime endDate
    );

    /**
     * 최근 24시간 안에 등장한 고유 키워드 수를 계산합니다.
     * 프론트엔드 '추적 키워드' 카드를 24시간 기준으로 맞추기 위한 집계입니다.
     */
    @Query(value = "SELECT COUNT(DISTINCT k.keyword) " +
            "FROM article_keywords k " +
            "JOIN articles a ON a.id = k.article_id " +
            "WHERE a.published_at >= :startDate " +
            "AND a.published_at < :endDate " +
            "AND (:categoryName IS NULL OR a.category = :categoryName)", nativeQuery = true)
    long countDistinctKeywordsWithinWindow(
            @Param("startDate") LocalDateTime startDate,
            @Param("endDate") LocalDateTime endDate,
            @Param("categoryName") String categoryName
    );

    /**
     * 기사 보관기간이 지난 parent article에 연결된 키워드를 먼저 삭제합니다.
     * FK 제약 때문에 기사 삭제 전에 article_keywords를 선삭제해야 안전합니다.
     */
    @Modifying
    @Query(value = "DELETE FROM article_keywords " +
            "WHERE article_id IN ( " +
            "    SELECT id FROM articles " +
            "    WHERE NVL(crawled_at, published_at) < :articleCutoffDate " +
            ")", nativeQuery = true)
    int deleteKeywordsOfExpiredArticles(@Param("articleCutoffDate") LocalDateTime articleCutoffDate);

    /**
     * article_keyword 자체 보관기간 45일을 초과한 데이터를 삭제합니다.
     * created_at이 비어 있는 기존 데이터는 parent article의 적재/발행일을 보조 기준으로 사용합니다.
     */
    @Modifying
    @Query(value = "DELETE FROM article_keywords " +
            "WHERE NVL(created_at, ( " +
            "    SELECT NVL(a.crawled_at, a.published_at) " +
            "    FROM articles a " +
            "    WHERE a.id = article_keywords.article_id " +
            ")) < :keywordCutoffDate", nativeQuery = true)
    int deleteExpiredKeywords(@Param("keywordCutoffDate") LocalDateTime keywordCutoffDate);

    /**
     * 방어적 정리 쿼리입니다.
     * 정상 FK 상태에서는 발생하지 않지만, 수동 DB 조작 등으로 parent article이 사라진 키워드를 정리합니다.
     */
    @Modifying
    @Query(value = "DELETE FROM article_keywords " +
            "WHERE NOT EXISTS ( " +
            "    SELECT 1 FROM articles a " +
            "    WHERE a.id = article_keywords.article_id " +
            ")", nativeQuery = true)
    int deleteOrphanKeywords();

    /**
     * AI 병합 추천 배치에서 최근 기간 내 등장한 고유 키워드를 조회합니다.
     */
    @Query(value = "SELECT keyword FROM (" +
            "    SELECT k.keyword AS keyword, COUNT(*) AS mention_count " +
            "    FROM article_keywords k " +
            "    JOIN articles a ON a.id = k.article_id " +
            "    WHERE a.published_at >= :startDate " +
            "    AND k.keyword IS NOT NULL " +
            "    GROUP BY k.keyword " +
            "    ORDER BY COUNT(*) DESC, k.keyword ASC" +
            ") WHERE ROWNUM <= 200", nativeQuery = true)
    List<String> findTopKeywordsByMentionCountPublishedAfter(@Param("startDate") LocalDateTime startDate);
}

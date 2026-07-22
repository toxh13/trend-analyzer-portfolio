package com.example.backendspring.repository;

import com.example.backendspring.entity.Article;
import org.springframework.data.jpa.repository.JpaRepository;
import org.springframework.data.jpa.repository.Modifying;
import org.springframework.data.jpa.repository.Query;
import org.springframework.data.repository.query.Param;
import org.springframework.data.domain.Pageable;

import java.time.LocalDateTime;
import java.util.Collection;
import java.util.List;

public interface ArticleRepository extends JpaRepository<Article, Long> {

    boolean existsBySourceUrl(String sourceUrl);

    List<Article> findByKeywordsKeywordOrderByPublishedAtDesc(String keyword);
    /**
     * 여러 키워드 중 하나라도 포함한 기사를 최신순으로 조회합니다.
     *
     * 필요한 이유:
     * - 메인 페이지에서는 "AI", "Artificial Intelligence"가 "인공지능"으로 합산됩니다.
     * - 사용자가 "인공지능"을 클릭했을 때도 alias에 연결된 기사까지 함께 보여줘야 합니다.
     *
     * distinct:
     * - 한 기사에 "AI"와 "인공지능"이 동시에 들어있는 경우 중복 반환을 방지합니다.
     */
    @Query(value = "SELECT a.* " +
            "FROM articles a " +
            "WHERE EXISTS (" +
            "    SELECT 1 " +
            "    FROM article_keywords k " +
            "    WHERE k.article_id = a.id " +
            "    AND k.keyword IN (:keywords)" +
            ") " +
            "ORDER BY a.published_at DESC", nativeQuery = true)
    List<Article> findDistinctByKeywordsKeywordInOrderByPublishedAtDesc(@Param("keywords") Collection<String> keywords);

    /**
     * 대표 키워드와 alias 중 하나를 포함한 기사를 서울 날짜 경계 안에서 최신순으로 조회합니다.
     * EXISTS를 사용해 한 기사에 alias가 여러 개 있어도 기사 행은 한 번만 반환합니다.
     */
    @Query(value = "SELECT a.* " +
            "FROM articles a " +
            "WHERE a.published_at >= :startDate " +
            "AND a.published_at < :endDate " +
            "AND EXISTS (" +
            "    SELECT 1 " +
            "    FROM article_keywords k " +
            "    WHERE k.article_id = a.id " +
            "    AND k.keyword IN (:keywords)" +
            ") " +
            "ORDER BY a.published_at DESC, a.id DESC", nativeQuery = true)
    List<Article> findEvidenceByKeywordsWithinWindow(
            @Param("keywords") Collection<String> keywords,
            @Param("startDate") LocalDateTime startDate,
            @Param("endDate") LocalDateTime endDate,
            Pageable pageable
    );

    /**
     * 여러 키워드를 하나의 대표 키워드 묶음으로 보고 최근 7일 일자별 언급량을 집계합니다.
     *
     * 예:
     * keyword 묶음 = [인공지능, AI, Artificial Intelligence]
     *
     * 그러면 세 키워드의 일자별 언급량을 합산해 반환합니다.
     */
    @Query(value = "SELECT TO_CHAR(TRUNC(a.published_at), 'YYYY-MM-DD') as dayDate, " +
            "a.id as articleId, SUM(k.weight) as occurrenceCount " +
            "FROM articles a " +
            "JOIN article_keywords k ON a.id = k.article_id " +
            "WHERE k.keyword IN (:keywords) " +
            "AND a.published_at >= :startDate " +
            "AND a.published_at < :endDate " +
            "GROUP BY TRUNC(a.published_at), a.id " +
            "ORDER BY dayDate ASC, articleId ASC", nativeQuery = true)
    List<Object[]> findDailyKeywordEvidence(
            @Param("keywords") Collection<String> keywords,
            @Param("startDate") LocalDateTime startDate,
            @Param("endDate") LocalDateTime endDate
    );
    /**
     * 기사 테이블에 실제 저장된 카테고리를 중복 없이 조회합니다.
     * 새 크롤러 카테고리가 추가되면 별도 프론트 수정 없이 필터 목록에 반영하기 위한 쿼리입니다.
     */
    @Query("SELECT DISTINCT a.category FROM Article a WHERE a.category IS NOT NULL ORDER BY a.category ASC")
    List<String> findDistinctCategories();


    /**
     * 최근 24시간 통계 카드의 '분석 기사' 수를 계산합니다.
     * categoryName이 null이면 전체, 값이 있으면 해당 카테고리만 집계합니다.
     */
    @Query(value = "SELECT COUNT(*) " +
            "FROM articles a " +
            "WHERE a.published_at >= :startDate " +
            "AND a.published_at < :endDate " +
            "AND (:categoryName IS NULL OR a.category = :categoryName)", nativeQuery = true)
    long countArticlesWithinWindow(
            @Param("startDate") LocalDateTime startDate,
            @Param("endDate") LocalDateTime endDate,
            @Param("categoryName") String categoryName
    );

    /**
     * [최적화 및 오라클 튜닝] 특정 키워드의 최근 7일간 일자별 언급량 통계 집계
     * * * [보안/무결성] @Param 바인딩을 통해 SQL Injection 공격을 방어합니다.
     * * [최적화] 기존 PostgreSQL 전용 'DATE' 함수를 오라클 전용 날짜 절삭 함수인 'TRUNC'로 전면 교체하여
     * 대시보드 차트 시계열 연산 속도를 인덱싱 가속화합니다.
     */
    @Query(value = "SELECT TO_CHAR(TRUNC(a.published_at), 'YYYY-MM-DD') as dayDate, COUNT(k.id) as dailyScore " +
            "FROM articles a " +
            "JOIN article_keywords k ON a.id = k.article_id " +
            "WHERE k.keyword = :keyword AND a.published_at >= :startDate " +
            "GROUP BY TRUNC(a.published_at) " +
            "ORDER BY dayDate ASC", nativeQuery = true) // 🌟 하이버네이트 검증 락을 완벽히 깨부수기 위해 안전한 Native Query 처리로 전환 최적화
    List<Object[]> findDailyScoreByKeywordWithin7Days(
            @Param("keyword") String keyword,
            @Param("startDate") LocalDateTime startDate
    );

    /**
     * 기사 보관 정책에 따라 30일이 지난 기사를 삭제합니다.
     * crawled_at이 비어 있는 기존 데이터는 published_at을 보조 기준으로 사용합니다.
     * trend_metrics는 별도 테이블이므로 이 삭제 대상에 포함하지 않습니다.
     */
    @Modifying
    @Query(value = "DELETE FROM articles " +
            "WHERE NVL(crawled_at, published_at) < :cutoffDate", nativeQuery = true)
    int deleteExpiredArticles(@Param("cutoffDate") LocalDateTime cutoffDate);
}

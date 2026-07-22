package com.example.backendspring.repository;

import com.example.backendspring.entity.TrendMetric;
import org.springframework.data.jpa.repository.JpaRepository;
import org.springframework.data.jpa.repository.Modifying;
import org.springframework.data.jpa.repository.Query;

import java.util.List;

public interface TrendMetricRepository extends JpaRepository<TrendMetric, Long> {

    /**
     * Oracle parallel DML cannot be followed by inserts into the same table in one transaction.
     * The snapshot is small, so force a serial delete and keep delete + insert atomic.
     */
    @Modifying(clearAutomatically = true, flushAutomatically = true)
    @Query(value = "DELETE /*+ NO_PARALLEL */ FROM trend_metrics", nativeQuery = true)
    int deleteSnapshotRows();

    List<TrendMetric> findTop20ByOrderByHotnessScoreDesc();
    List<TrendMetric> findTop20ByCategoryOrderByHotnessScoreDesc(String category);

    /**
     * trend_metrics 기준 카테고리별 트렌드 개수를 조회합니다.
     * 프론트 카테고리 버튼의 건수 표시를 DB 집계값으로 동적으로 표시하기 위한 쿼리입니다.
     */
    @Query("SELECT tm.category, COUNT(tm.id) FROM TrendMetric tm WHERE tm.category IS NOT NULL AND tm.mentionCount > 0 GROUP BY tm.category ORDER BY tm.category ASC")
    List<Object[]> findCategoryCounts();

    /**
     * alias 병합 처리를 위해 전체 트렌드 메트릭을 조회합니다.
     *
     * 주의:
     * - Top20만 먼저 조회한 뒤 alias를 합치면 순위가 틀어질 수 있습니다.
     * - 예를 들어 AI, 인공지능, Artificial Intelligence가 각각 낮은 순위라도
     *   합치면 Top20 안으로 들어올 수 있기 때문입니다.
     */
    List<TrendMetric> findAllByOrderByHotnessScoreDesc();

    /**
     * 카테고리별 alias 병합 처리를 위해 해당 카테고리의 전체 트렌드 메트릭을 조회합니다.
     */
    List<TrendMetric> findByCategoryOrderByHotnessScoreDesc(String category);
}

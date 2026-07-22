package com.example.backendspring.entity;

import jakarta.persistence.*;
import lombok.*;
import org.springframework.data.annotation.LastModifiedDate;
import org.springframework.data.jpa.domain.support.AuditingEntityListener;

import java.time.LocalDateTime;

/**
 * 트렌드 메트릭 엔티티
 * 특정 키워드에 대한 트렌드 지표 정보를 관리하는 엔티티
 * 언급 횟수, 속도 점수, 인기도 점수 등의 메트릭을 저장한다.
 */
@Getter
@Setter
@Builder
@NoArgsConstructor
@AllArgsConstructor
@Entity
@Table(
        name = "trend_metrics",
        uniqueConstraints = @UniqueConstraint(
                name = "uk_trend_metrics_keyword_category",
                columnNames = {"keyword", "category"}
        )
)
@EntityListeners(AuditingEntityListener.class) // 추가: 데이터 변경 감지 리스너
public class TrendMetric {

    // Article.java, ArticleKeyword.java 등 변경
    @Id
    @GeneratedValue(strategy = GenerationType.SEQUENCE, generator = "trend_seq")
    @SequenceGenerator(name = "trend_seq", sequenceName = "TREND_SEQ", allocationSize = 1)
    private Long id;

    /**
     * 추적 중인 키워드
     * 예: "인공지능", "머신러닝" 등
     */
    @Column(nullable = false, length = 100)
    private String keyword;

    /**
     * 키워드의 카테고리
     * 예: "기술", "트렌드" 등
     */
    @Column(nullable = false, length = 100)
    private String category;

    /**
     * 현재 24시간 구간에서 대표 키워드를 언급한 고유 기사 수
     */
    @Column(nullable = false)
    private int mentionCount;

    /**
     * 현재 24시간 고유 기사 수에서 직전 24시간 고유 기사 수를 뺀 변화량
     */
    @Column(nullable = false)
    private float velocityScore;

    /**
     * mentionCount 40%와 velocityScore 60%를 결합한 상대적 순위 점수
     */
    @Column(nullable = false)
    private float hotnessScore;

    /**
     * 마지막 업데이트 시간
     * Spring Data JPA의 @LastModifiedDate로 자동 관리되며, 레코드 수정 시 자동 갱신된다.
     */
    @LastModifiedDate
    @Column(name = "updated_at", nullable = false)
    private LocalDateTime updatedAt;

}

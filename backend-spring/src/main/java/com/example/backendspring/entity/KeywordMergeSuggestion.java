package com.example.backendspring.entity;

import jakarta.persistence.*;
import lombok.*;

import java.math.BigDecimal;
import java.time.LocalDateTime;

/**
 * AI 또는 배치가 제안한 키워드 병합 후보 엔티티입니다.
 *
 * <p>추천이 생성되었다고 해서 바로 트렌드 집계에 반영하지 않습니다.
 * 관리자가 승인한 추천만 실제 활성 alias로 전환됩니다.</p>
 */
@Entity
@Table(name = "keyword_merge_suggestions")
@Getter
@Setter
@Builder
@NoArgsConstructor
@AllArgsConstructor
public class KeywordMergeSuggestion {

    @Id
    @GeneratedValue(strategy = GenerationType.SEQUENCE, generator = "keyword_merge_suggestion_seq")
    @SequenceGenerator(
            name = "keyword_merge_suggestion_seq",
            sequenceName = "KEYWORD_MERGE_SUGGESTION_SEQ",
            allocationSize = 1
    )
    private Long id;

    /**
     * 모델이 병합 대상으로 추천한 원본 키워드입니다.
     */
    @Column(name = "source_keyword", nullable = false, length = 100)
    private String sourceKeyword;

    /**
     * 같은 원본 키워드가 반복 추천되지 않도록 비교할 때 사용하는 정규화 값입니다.
     */
    @Column(name = "normalized_source_keyword", nullable = false, length = 100)
    private String normalizedSourceKeyword;

    /**
     * 원본 키워드를 연결하라고 추천된 대상 대표 키워드 그룹입니다.
     */
    @ManyToOne(fetch = FetchType.LAZY)
    @JoinColumn(name = "target_group_id", nullable = false)
    private KeywordGroup targetGroup;

    /**
     * 추천이 만들어진 시점의 대상 대표 키워드명입니다.
     *
     * <p>나중에 대표 키워드명이 바뀌더라도 당시 어떤 기준으로 추천됐는지
     * 확인할 수 있도록 스냅샷으로 저장합니다.</p>
     */
    @Column(name = "target_keyword", nullable = false, length = 100)
    private String targetKeyword;

    /**
     * 추천 생성 과정에서 계산한 유사도 점수입니다.
     */
    @Column(name = "similarity_score", nullable = false, precision = 5, scale = 4)
    private BigDecimal similarityScore;

    /**
     * 관리자가 검토할 수 있도록 제공하는 추천 이유입니다.
     */
    @Column(length = 1000)
    private String reason;

    @Enumerated(EnumType.STRING)
    @Column(nullable = false, length = 30)
    private KeywordMergeSuggestionStatus status;

    @Column(name = "model_name", length = 200)
    private String modelName;

    @Column(name = "model_version", length = 100)
    private String modelVersion;

    /**
     * 추천을 승인하거나 거절한 관리자 식별자입니다.
     */
    @Column(name = "reviewed_by", length = 100)
    private String reviewedBy;

    @Column(name = "reviewed_at")
    private LocalDateTime reviewedAt;

    @Column(name = "created_at", nullable = false)
    private LocalDateTime createdAt;

    @Column(name = "updated_at", nullable = false)
    private LocalDateTime updatedAt;
}

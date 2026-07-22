package com.example.backendspring.entity;

import jakarta.persistence.Column;
import jakarta.persistence.Entity;
import jakarta.persistence.EnumType;
import jakarta.persistence.Enumerated;
import jakarta.persistence.FetchType;
import jakarta.persistence.GeneratedValue;
import jakarta.persistence.GenerationType;
import jakarta.persistence.Id;
import jakarta.persistence.JoinColumn;
import jakarta.persistence.ManyToOne;
import jakarta.persistence.SequenceGenerator;
import jakarta.persistence.Table;
import lombok.AllArgsConstructor;
import lombok.Builder;
import lombok.Getter;
import lombok.NoArgsConstructor;
import lombok.Setter;

import java.time.LocalDateTime;

@Entity
@Table(name = "keyword_recommendation_runs")
@Getter
@Setter
@Builder
@NoArgsConstructor
@AllArgsConstructor
public class KeywordRecommendationRun {

    @Id
    @GeneratedValue(strategy = GenerationType.SEQUENCE, generator = "keyword_recommendation_run_seq")
    @SequenceGenerator(name = "keyword_recommendation_run_seq", sequenceName = "KEYWORD_RECOMMENDATION_RUN_SEQ", allocationSize = 1)
    private Long id;

    @ManyToOne(fetch = FetchType.LAZY)
    @JoinColumn(name = "target_group_id", nullable = false)
    private KeywordGroup targetGroup;

    @Enumerated(EnumType.STRING)
    @Column(nullable = false, length = 20)
    private KeywordRecommendationRunStatus status;

    @Column(name = "active_slot", unique = true)
    private Integer activeSlot;

    @Column(name = "candidate_count")
    private Integer candidateCount;

    @Column(name = "requested_suggestion_count")
    private Integer requestedSuggestionCount;

    @Column(name = "saved_suggestion_count")
    private Integer savedSuggestionCount;

    @Column(name = "failure_code", length = 100)
    private String failureCode;

    @Column(name = "requested_by", length = 100)
    private String requestedBy;

    @Column(name = "requested_at", nullable = false)
    private LocalDateTime requestedAt;

    @Column(name = "started_at")
    private LocalDateTime startedAt;

    @Column(name = "completed_at")
    private LocalDateTime completedAt;
}

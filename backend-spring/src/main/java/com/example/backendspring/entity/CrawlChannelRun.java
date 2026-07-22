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

@Entity
@Table(name = "crawl_channel_runs")
@Getter
@Builder
@NoArgsConstructor
@AllArgsConstructor
public class CrawlChannelRun {

    @Id
    @GeneratedValue(strategy = GenerationType.SEQUENCE, generator = "crawl_channel_run_seq")
    @SequenceGenerator(name = "crawl_channel_run_seq", sequenceName = "CRAWL_CHANNEL_RUN_SEQ", allocationSize = 1)
    private Long id;

    @ManyToOne(fetch = FetchType.LAZY, optional = false)
    @JoinColumn(name = "batch_run_id", nullable = false)
    private CrawlBatchRun batchRun;

    @Column(nullable = false, length = 20)
    private String channel;

    @Enumerated(EnumType.STRING)
    @Column(nullable = false, length = 30)
    private CrawlRunOutcome outcome;

    @Column(name = "validated_article_count", nullable = false)
    private long validatedArticleCount;
    @Column(name = "source_invalid_count", nullable = false)
    private long sourceInvalidCount;
    @Column(name = "successful_units", nullable = false)
    private long successfulUnits;
    @Column(name = "partial_units", nullable = false)
    private long partialUnits;
    @Column(name = "empty_units", nullable = false)
    private long emptyUnits;
    @Column(name = "failed_units", nullable = false)
    private long failedUnits;

    void assignBatchRun(CrawlBatchRun batchRun) {
        this.batchRun = batchRun;
    }
}

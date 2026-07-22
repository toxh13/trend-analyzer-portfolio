package com.example.backendspring.entity;

import jakarta.persistence.CascadeType;
import jakarta.persistence.Column;
import jakarta.persistence.Entity;
import jakarta.persistence.EnumType;
import jakarta.persistence.Enumerated;
import jakarta.persistence.FetchType;
import jakarta.persistence.GeneratedValue;
import jakarta.persistence.GenerationType;
import jakarta.persistence.Id;
import jakarta.persistence.OneToMany;
import jakarta.persistence.OrderBy;
import jakarta.persistence.SequenceGenerator;
import jakarta.persistence.Table;
import lombok.AllArgsConstructor;
import lombok.Builder;
import lombok.Getter;
import lombok.NoArgsConstructor;
import java.time.LocalDateTime;
import java.util.ArrayList;
import java.util.List;

@Entity
@Table(name = "crawl_batch_runs")
@Getter
@Builder
@NoArgsConstructor
@AllArgsConstructor
public class CrawlBatchRun {

    @Id
    @GeneratedValue(strategy = GenerationType.SEQUENCE, generator = "crawl_batch_run_seq")
    @SequenceGenerator(name = "crawl_batch_run_seq", sequenceName = "CRAWL_BATCH_RUN_SEQ", allocationSize = 1)
    private Long id;

    @Column(name = "run_id", nullable = false, unique = true, length = 36)
    private String runId;

    @Column(name = "started_at", nullable = false)
    private LocalDateTime startedAt;

    @Column(name = "completed_at")
    private LocalDateTime completedAt;

    @Enumerated(EnumType.STRING)
    @Column(nullable = false, length = 30)
    private CrawlRunOutcome outcome;

    @Column(name = "crawler_output_count", nullable = false)
    private long crawlerOutputCount;
    @Column(name = "source_invalid_count", nullable = false)
    private long sourceInvalidCount;
    @Column(name = "validation_rejected_count", nullable = false)
    private long validationRejectedCount;
    @Column(name = "duplicate_url_count", nullable = false)
    private long duplicateUrlCount;
    @Column(name = "eligible_count", nullable = false)
    private long eligibleCount;
    @Column(name = "selected_count", nullable = false)
    private long selectedCount;
    @Column(name = "dropped_by_limit_count", nullable = false)
    private long droppedByLimitCount;
    @Column(name = "preprocessing_failed_count", nullable = false)
    private long preprocessingFailedCount;
    @Column(name = "backend_acknowledged_count", nullable = false)
    private long backendAcknowledgedCount;
    @Column(name = "http_failed_count", nullable = false)
    private long httpFailedCount;
    @Column(name = "transport_failed_count", nullable = false)
    private long transportFailedCount;
    @Column(name = "successful_channel_count", nullable = false)
    private long successfulChannelCount;
    @Column(name = "partial_channel_count", nullable = false)
    private long partialChannelCount;
    @Column(name = "empty_channel_count", nullable = false)
    private long emptyChannelCount;
    @Column(name = "failed_channel_count", nullable = false)
    private long failedChannelCount;
    @Column(name = "successful_unit_count", nullable = false)
    private long successfulUnitCount;
    @Column(name = "partial_unit_count", nullable = false)
    private long partialUnitCount;
    @Column(name = "empty_unit_count", nullable = false)
    private long emptyUnitCount;
    @Column(name = "failed_unit_count", nullable = false)
    private long failedUnitCount;
    @Column(name = "duration_ms", nullable = false)
    private long durationMs;

    @Column(name = "created_at", nullable = false)
    private LocalDateTime createdAt;

    @OneToMany(mappedBy = "batchRun", cascade = CascadeType.ALL, fetch = FetchType.LAZY, orphanRemoval = true)
    @OrderBy("channel ASC")
    @Builder.Default
    private List<CrawlChannelRun> channels = new ArrayList<>();

    public void addChannel(CrawlChannelRun channel) {
        channels.add(channel);
        channel.assignBatchRun(this);
    }

    public void completeFrom(CrawlBatchRun completed) {
        this.completedAt = completed.completedAt;
        this.outcome = completed.outcome;
        this.crawlerOutputCount = completed.crawlerOutputCount;
        this.sourceInvalidCount = completed.sourceInvalidCount;
        this.validationRejectedCount = completed.validationRejectedCount;
        this.duplicateUrlCount = completed.duplicateUrlCount;
        this.eligibleCount = completed.eligibleCount;
        this.selectedCount = completed.selectedCount;
        this.droppedByLimitCount = completed.droppedByLimitCount;
        this.preprocessingFailedCount = completed.preprocessingFailedCount;
        this.backendAcknowledgedCount = completed.backendAcknowledgedCount;
        this.httpFailedCount = completed.httpFailedCount;
        this.transportFailedCount = completed.transportFailedCount;
        this.successfulChannelCount = completed.successfulChannelCount;
        this.partialChannelCount = completed.partialChannelCount;
        this.emptyChannelCount = completed.emptyChannelCount;
        this.failedChannelCount = completed.failedChannelCount;
        this.successfulUnitCount = completed.successfulUnitCount;
        this.partialUnitCount = completed.partialUnitCount;
        this.emptyUnitCount = completed.emptyUnitCount;
        this.failedUnitCount = completed.failedUnitCount;
        this.durationMs = completed.durationMs;
        this.channels.clear();
        completed.channels.forEach(this::addChannel);
    }
}

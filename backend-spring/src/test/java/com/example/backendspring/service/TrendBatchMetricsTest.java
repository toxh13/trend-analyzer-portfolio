package com.example.backendspring.service;

import io.micrometer.core.instrument.simple.SimpleMeterRegistry;
import org.junit.jupiter.api.DisplayName;
import org.junit.jupiter.api.Test;
import org.springframework.transaction.support.TransactionSynchronization;
import org.springframework.transaction.support.TransactionSynchronizationManager;

import java.time.Clock;
import java.time.Instant;
import java.time.ZoneOffset;

import static org.assertj.core.api.Assertions.assertThat;

class TrendBatchMetricsTest {

    @Test
    @DisplayName("커밋된 배치는 성공 횟수와 최근 처리량을 기록한다")
    void committedBatchRecordsSuccessAndLastCounts() {
        SimpleMeterRegistry registry = new SimpleMeterRegistry();
        Clock clock = Clock.fixed(Instant.parse("2026-07-18T06:30:00Z"), ZoneOffset.UTC);
        TrendBatchMetrics metrics = new TrendBatchMetrics(registry, clock);
        TrendBatchMetrics.BatchRun run = metrics.start();

        TransactionSynchronizationManager.initSynchronization();
        try {
            metrics.completeAfterTransaction(run, 10, 6, 7, 3);
            assertThat(registry.counter("trend.batch.runs", "outcome", "success").count()).isZero();

            TransactionSynchronizationManager.getSynchronizations()
                    .forEach(synchronization -> synchronization.afterCompletion(
                            TransactionSynchronization.STATUS_COMMITTED
                    ));
        } finally {
            TransactionSynchronizationManager.clearSynchronization();
        }

        assertThat(registry.counter("trend.batch.runs", "outcome", "success").count()).isEqualTo(1.0);
        assertThat(registry.timer("trend.batch.duration", "outcome", "success").count()).isEqualTo(1L);
        assertThat(registry.get("trend.batch.last.success.epoch.seconds").gauge().value())
                .isEqualTo(clock.instant().getEpochSecond());
        assertThat(registry.get("trend.batch.last.evidence.rows").gauge().value()).isEqualTo(10.0);
        assertThat(registry.get("trend.batch.last.articles").gauge().value()).isEqualTo(6.0);
        assertThat(registry.get("trend.batch.last.unique.article.metrics").gauge().value()).isEqualTo(7.0);
        assertThat(registry.get("trend.batch.last.snapshot.rows").gauge().value()).isEqualTo(3.0);
    }

    @Test
    @DisplayName("실패한 배치는 실패 횟수를 기록하고 마지막 성공 시각을 변경하지 않는다")
    void failedBatchRecordsFailureWithoutChangingLastSuccess() {
        SimpleMeterRegistry registry = new SimpleMeterRegistry();
        TrendBatchMetrics metrics = new TrendBatchMetrics(registry, Clock.systemUTC());

        metrics.recordFailure(metrics.start(), new IllegalStateException("database unavailable"));

        assertThat(registry.counter("trend.batch.runs", "outcome", "failure").count()).isEqualTo(1.0);
        assertThat(registry.timer("trend.batch.duration", "outcome", "failure").count()).isEqualTo(1L);
        assertThat(registry.get("trend.batch.last.success.epoch.seconds").gauge().value()).isZero();
    }
}

package com.example.backendspring.service;

import io.micrometer.core.instrument.Counter;
import io.micrometer.core.instrument.Gauge;
import io.micrometer.core.instrument.MeterRegistry;
import io.micrometer.core.instrument.Timer;
import lombok.extern.slf4j.Slf4j;
import org.springframework.stereotype.Component;
import org.springframework.transaction.support.TransactionSynchronization;
import org.springframework.transaction.support.TransactionSynchronizationManager;

import java.time.Clock;
import java.time.Duration;
import java.util.concurrent.TimeUnit;
import java.util.concurrent.atomic.AtomicBoolean;
import java.util.concurrent.atomic.AtomicLong;

@Component
@Slf4j
public class TrendBatchMetrics {
    private static final String SUCCESS = "success";
    private static final String FAILURE = "failure";

    private final MeterRegistry meterRegistry;
    private final Clock clock;
    private final AtomicLong lastSuccessEpochSeconds = new AtomicLong();
    private final AtomicLong lastEvidenceRows = new AtomicLong();
    private final AtomicLong lastArticleCount = new AtomicLong();
    private final AtomicLong lastUniqueArticleMetrics = new AtomicLong();
    private final AtomicLong lastSnapshotRows = new AtomicLong();

    public TrendBatchMetrics(MeterRegistry meterRegistry, Clock clock) {
        this.meterRegistry = meterRegistry;
        this.clock = clock;
        Gauge.builder("trend.batch.last.success.epoch.seconds", lastSuccessEpochSeconds, AtomicLong::get)
                .description("Epoch seconds of the last committed trend batch")
                .register(meterRegistry);
        Gauge.builder("trend.batch.last.evidence.rows", lastEvidenceRows, AtomicLong::get)
                .description("Evidence rows read by the last successful trend batch")
                .register(meterRegistry);
        Gauge.builder("trend.batch.last.articles", lastArticleCount, AtomicLong::get)
                .description("Distinct articles processed by the last successful trend batch")
                .register(meterRegistry);
        Gauge.builder("trend.batch.last.unique.article.metrics", lastUniqueArticleMetrics, AtomicLong::get)
                .description("Unique article-keyword-category rows in the last successful trend batch")
                .register(meterRegistry);
        Gauge.builder("trend.batch.last.snapshot.rows", lastSnapshotRows, AtomicLong::get)
                .description("Snapshot rows written by the last successful trend batch")
                .register(meterRegistry);
    }

    public BatchRun start() {
        return new BatchRun(System.nanoTime());
    }

    /**
     * 트랜잭션 커밋까지 성공해야 성공 지표를 기록한다.
     */
    public void completeAfterTransaction(
            BatchRun run,
            int evidenceRows,
            int articleCount,
            int uniqueArticleMetrics,
            int snapshotRows
    ) {
        if (!TransactionSynchronizationManager.isSynchronizationActive()) {
            recordSuccess(run, evidenceRows, articleCount, uniqueArticleMetrics, snapshotRows);
            return;
        }

        TransactionSynchronizationManager.registerSynchronization(new TransactionSynchronization() {
            @Override
            public void afterCompletion(int status) {
                if (status == STATUS_COMMITTED) {
                    recordSuccess(run, evidenceRows, articleCount, uniqueArticleMetrics, snapshotRows);
                } else {
                    recordFailure(run, "transaction_rolled_back");
                }
            }
        });
    }

    public void recordFailure(BatchRun run, RuntimeException error) {
        recordFailure(run, error.getClass().getSimpleName());
    }

    private void recordSuccess(
            BatchRun run,
            int evidenceRows,
            int articleCount,
            int uniqueArticleMetrics,
            int snapshotRows
    ) {
        if (!run.completed.compareAndSet(false, true)) {
            return;
        }

        long durationNanos = elapsedNanos(run);
        recordRun(SUCCESS, durationNanos);
        lastSuccessEpochSeconds.set(clock.instant().getEpochSecond());
        lastEvidenceRows.set(evidenceRows);
        lastArticleCount.set(articleCount);
        lastUniqueArticleMetrics.set(uniqueArticleMetrics);
        lastSnapshotRows.set(snapshotRows);

        log.info(
                "event=trend_batch_completed outcome=success durationMs={} evidenceRows={} articleCount={} uniqueArticleMetrics={} snapshotRows={}",
                TimeUnit.NANOSECONDS.toMillis(durationNanos),
                evidenceRows,
                articleCount,
                uniqueArticleMetrics,
                snapshotRows
        );
    }

    private void recordFailure(BatchRun run, String reason) {
        if (!run.completed.compareAndSet(false, true)) {
            return;
        }

        long durationNanos = elapsedNanos(run);
        recordRun(FAILURE, durationNanos);
        log.error(
                "event=trend_batch_completed outcome=failure durationMs={} reason={}",
                TimeUnit.NANOSECONDS.toMillis(durationNanos),
                reason
        );
    }

    private void recordRun(String outcome, long durationNanos) {
        Counter.builder("trend.batch.runs")
                .description("Number of trend batch executions")
                .tag("outcome", outcome)
                .register(meterRegistry)
                .increment();
        Timer.builder("trend.batch.duration")
                .description("Trend batch execution duration")
                .tag("outcome", outcome)
                .register(meterRegistry)
                .record(Duration.ofNanos(durationNanos));
    }

    private long elapsedNanos(BatchRun run) {
        return Math.max(0L, System.nanoTime() - run.startedAtNanos);
    }

    public static final class BatchRun {
        private final long startedAtNanos;
        private final AtomicBoolean completed = new AtomicBoolean();

        private BatchRun(long startedAtNanos) {
            this.startedAtNanos = startedAtNanos;
        }
    }
}

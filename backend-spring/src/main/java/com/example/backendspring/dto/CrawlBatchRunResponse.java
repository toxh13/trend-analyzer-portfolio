package com.example.backendspring.dto;

import com.example.backendspring.entity.CrawlBatchRun;
import com.example.backendspring.entity.CrawlRunOutcome;

import java.time.OffsetDateTime;
import java.time.ZoneOffset;
import java.util.List;

public record CrawlBatchRunResponse(
        String runId,
        OffsetDateTime startedAt,
        OffsetDateTime completedAt,
        CrawlRunOutcome outcome,
        long crawlerOutputCount,
        long sourceInvalidCount,
        long validationRejectedCount,
        long duplicateUrlCount,
        long eligibleCount,
        long selectedCount,
        long droppedByLimitCount,
        long preprocessingFailedCount,
        long backendAcknowledgedCount,
        long httpFailedCount,
        long transportFailedCount,
        long successfulChannelCount,
        long partialChannelCount,
        long emptyChannelCount,
        long failedChannelCount,
        long successfulUnitCount,
        long partialUnitCount,
        long emptyUnitCount,
        long failedUnitCount,
        long durationMs,
        boolean reconciliationOk,
        OffsetDateTime createdAt,
        List<CrawlChannelRunResponse> channels
) {
    public static CrawlBatchRunResponse from(CrawlBatchRun run) {
        return from(run, true);
    }

    public static CrawlBatchRunResponse summaryFrom(CrawlBatchRun run) {
        return from(run, false);
    }

    private static CrawlBatchRunResponse from(CrawlBatchRun run, boolean includeChannels) {
        return new CrawlBatchRunResponse(
                run.getRunId(), run.getStartedAt().atOffset(ZoneOffset.UTC),
                run.getCompletedAt() == null ? null : run.getCompletedAt().atOffset(ZoneOffset.UTC), run.getOutcome(),
                run.getCrawlerOutputCount(), run.getSourceInvalidCount(), run.getValidationRejectedCount(),
                run.getDuplicateUrlCount(), run.getEligibleCount(), run.getSelectedCount(),
                run.getDroppedByLimitCount(), run.getPreprocessingFailedCount(),
                run.getBackendAcknowledgedCount(), run.getHttpFailedCount(), run.getTransportFailedCount(),
                run.getSuccessfulChannelCount(), run.getPartialChannelCount(), run.getEmptyChannelCount(),
                run.getFailedChannelCount(), run.getSuccessfulUnitCount(), run.getPartialUnitCount(),
                run.getEmptyUnitCount(), run.getFailedUnitCount(), run.getDurationMs(),
                reconciles(run, includeChannels),
                run.getCreatedAt().atOffset(ZoneOffset.UTC),
                includeChannels
                        ? run.getChannels().stream().map(CrawlChannelRunResponse::from).toList()
                        : List.of()
        );
    }

    private static boolean reconciles(CrawlBatchRun run, boolean includeChannels) {
        if (run.getOutcome() == CrawlRunOutcome.RUNNING) {
            return run.getCompletedAt() == null
                    && run.getCrawlerOutputCount() == 0
                    && run.getSelectedCount() == 0;
        }
        boolean parentReconciles = run.getCompletedAt() != null
                && run.getCrawlerOutputCount()
                == run.getValidationRejectedCount() + run.getDuplicateUrlCount() + run.getEligibleCount()
                && run.getEligibleCount() == run.getSelectedCount() + run.getDroppedByLimitCount()
                && run.getSelectedCount()
                == run.getPreprocessingFailedCount() + run.getBackendAcknowledgedCount()
                + run.getHttpFailedCount() + run.getTransportFailedCount()
                && run.getSuccessfulChannelCount() + run.getPartialChannelCount()
                + run.getEmptyChannelCount() + run.getFailedChannelCount() == 3;
        if (!parentReconciles || !includeChannels) {
            return parentReconciles;
        }
        return run.getChannels().size() == 3
                && run.getChannels().stream().map(CrawlChannelRunResponse::from)
                .map(CrawlChannelRunResponse::channel).collect(java.util.stream.Collectors.toSet())
                .equals(java.util.Set.of("naver", "daum", "rss"))
                && run.getChannels().stream().mapToLong(channel -> channel.getValidatedArticleCount()).sum()
                == run.getDuplicateUrlCount() + run.getEligibleCount()
                && run.getChannels().stream().mapToLong(channel -> channel.getSourceInvalidCount()).sum()
                == run.getSourceInvalidCount()
                && run.getChannels().stream().mapToLong(channel -> channel.getSuccessfulUnits()).sum()
                == run.getSuccessfulUnitCount()
                && run.getChannels().stream().mapToLong(channel -> channel.getPartialUnits()).sum()
                == run.getPartialUnitCount()
                && run.getChannels().stream().mapToLong(channel -> channel.getEmptyUnits()).sum()
                == run.getEmptyUnitCount()
                && run.getChannels().stream().mapToLong(channel -> channel.getFailedUnits()).sum()
                == run.getFailedUnitCount()
                && run.getChannels().stream().filter(channel -> channel.getOutcome() == CrawlRunOutcome.SUCCESS).count()
                == run.getSuccessfulChannelCount()
                && run.getChannels().stream().filter(channel -> channel.getOutcome() == CrawlRunOutcome.PARTIAL_FAILURE).count()
                == run.getPartialChannelCount()
                && run.getChannels().stream().filter(channel -> channel.getOutcome() == CrawlRunOutcome.EMPTY).count()
                == run.getEmptyChannelCount()
                && run.getChannels().stream().filter(channel -> channel.getOutcome() == CrawlRunOutcome.FAILURE).count()
                == run.getFailedChannelCount();
    }
}

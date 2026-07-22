package com.example.backendspring.dto;

import com.example.backendspring.entity.CrawlRunOutcome;
import jakarta.validation.Valid;
import jakarta.validation.constraints.NotBlank;
import jakarta.validation.constraints.NotEmpty;
import jakarta.validation.constraints.NotNull;
import jakarta.validation.constraints.PositiveOrZero;
import jakarta.validation.constraints.Size;

import java.time.OffsetDateTime;
import java.util.List;

public record CrawlBatchRunCompleteRequest(
        @NotBlank @Size(max = 36) String runId,
        @NotNull OffsetDateTime startedAt,
        @NotNull OffsetDateTime completedAt,
        @NotNull CrawlRunOutcome outcome,
        @NotNull @PositiveOrZero Long crawlerOutputCount,
        @NotNull @PositiveOrZero Long validationRejectedCount,
        @NotNull @PositiveOrZero Long duplicateUrlCount,
        @NotNull @PositiveOrZero Long eligibleCount,
        @NotNull @PositiveOrZero Long selectedCount,
        @NotNull @PositiveOrZero Long droppedByLimitCount,
        @NotNull @PositiveOrZero Long preprocessingFailedCount,
        @NotNull @PositiveOrZero Long backendAcknowledgedCount,
        @NotNull @PositiveOrZero Long httpFailedCount,
        @NotNull @PositiveOrZero Long transportFailedCount,
        @NotNull @PositiveOrZero Long durationMs,
        @NotEmpty @Size(min = 3, max = 3) List<@Valid CrawlChannelRunRequest> channels
) {
}

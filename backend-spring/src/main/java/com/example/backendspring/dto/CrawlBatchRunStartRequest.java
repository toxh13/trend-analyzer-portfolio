package com.example.backendspring.dto;

import jakarta.validation.constraints.NotBlank;
import jakarta.validation.constraints.NotNull;
import jakarta.validation.constraints.Size;

import java.time.OffsetDateTime;

public record CrawlBatchRunStartRequest(
        @NotBlank @Size(max = 36) String runId,
        @NotNull OffsetDateTime startedAt
) {
}

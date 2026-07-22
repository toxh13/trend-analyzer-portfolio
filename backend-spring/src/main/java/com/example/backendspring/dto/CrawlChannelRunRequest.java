package com.example.backendspring.dto;

import com.example.backendspring.entity.CrawlRunOutcome;
import jakarta.validation.constraints.NotBlank;
import jakarta.validation.constraints.NotNull;
import jakarta.validation.constraints.PositiveOrZero;
import jakarta.validation.constraints.Size;

public record CrawlChannelRunRequest(
        @NotBlank @Size(max = 20) String channel,
        @NotNull CrawlRunOutcome outcome,
        @NotNull @PositiveOrZero Long validatedArticleCount,
        @NotNull @PositiveOrZero Long sourceInvalidCount,
        @NotNull @PositiveOrZero Long successfulUnits,
        @NotNull @PositiveOrZero Long partialUnits,
        @NotNull @PositiveOrZero Long emptyUnits,
        @NotNull @PositiveOrZero Long failedUnits
) {
}

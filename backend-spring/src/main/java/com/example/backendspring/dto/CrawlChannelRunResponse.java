package com.example.backendspring.dto;

import com.example.backendspring.entity.CrawlChannelRun;
import com.example.backendspring.entity.CrawlRunOutcome;

public record CrawlChannelRunResponse(
        String channel,
        CrawlRunOutcome outcome,
        long validatedArticleCount,
        long sourceInvalidCount,
        long successfulUnits,
        long partialUnits,
        long emptyUnits,
        long failedUnits
) {
    public static CrawlChannelRunResponse from(CrawlChannelRun run) {
        return new CrawlChannelRunResponse(
                run.getChannel(), run.getOutcome(), run.getValidatedArticleCount(), run.getSourceInvalidCount(),
                run.getSuccessfulUnits(), run.getPartialUnits(), run.getEmptyUnits(), run.getFailedUnits()
        );
    }
}

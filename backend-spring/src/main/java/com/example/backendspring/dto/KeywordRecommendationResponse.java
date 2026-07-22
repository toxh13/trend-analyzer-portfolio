package com.example.backendspring.dto;

import java.math.BigDecimal;
import java.util.List;

public record KeywordRecommendationResponse(
        String modelName,
        String modelVersion,
        List<Suggestion> suggestions
) {

    public record Suggestion(
            String sourceKeyword,
            String normalizedSourceKeyword,
            Long targetGroupId,
            String targetKeyword,
            BigDecimal similarityScore,
            String reason,
            String modelName,
            String modelVersion
    ) {
    }
}

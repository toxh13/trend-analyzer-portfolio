package com.example.backendspring.dto;

import java.util.List;

public record KeywordRecommendationRequest(
        List<CandidateKeyword> candidateKeywords,
        TargetKeywordGroup selectedTargetGroup,
        double threshold,
        int topK
) {

    public record CandidateKeyword(
            String keyword,
            String normalizedKeyword
    ) {
    }

    public record TargetKeywordGroup(
            Long id,
            String canonicalKeyword
    ) {
    }
}

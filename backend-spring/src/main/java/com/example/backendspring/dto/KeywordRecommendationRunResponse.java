package com.example.backendspring.dto;

import com.example.backendspring.entity.KeywordRecommendationRun;
import com.example.backendspring.entity.KeywordRecommendationRunStatus;

import java.time.LocalDateTime;

public record KeywordRecommendationRunResponse(
        Long id,
        Long targetGroupId,
        String targetKeyword,
        KeywordRecommendationRunStatus status,
        Integer candidateCount,
        Integer requestedSuggestionCount,
        Integer savedSuggestionCount,
        String failureCode,
        LocalDateTime requestedAt,
        LocalDateTime startedAt,
        LocalDateTime completedAt
) {
    public static KeywordRecommendationRunResponse from(KeywordRecommendationRun run) {
        return new KeywordRecommendationRunResponse(
                run.getId(),
                run.getTargetGroup().getId(),
                run.getTargetGroup().getCanonicalKeyword(),
                run.getStatus(),
                run.getCandidateCount(),
                run.getRequestedSuggestionCount(),
                run.getSavedSuggestionCount(),
                run.getFailureCode(),
                run.getRequestedAt(),
                run.getStartedAt(),
                run.getCompletedAt()
        );
    }
}

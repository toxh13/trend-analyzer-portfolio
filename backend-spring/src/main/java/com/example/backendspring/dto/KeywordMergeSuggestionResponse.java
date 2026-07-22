package com.example.backendspring.dto;

import com.example.backendspring.entity.KeywordMergeSuggestion;
import com.example.backendspring.entity.KeywordMergeSuggestionStatus;

import java.math.BigDecimal;
import java.time.LocalDateTime;

/**
 * AI 병합 추천 후보 응답 DTO입니다.
 * 관리자 페이지의 "AI 병합 추천" 탭에서 사용합니다.
 */
public record KeywordMergeSuggestionResponse(
        Long id,
        String sourceKeyword,
        String normalizedSourceKeyword,
        Long targetGroupId,
        String targetKeyword,
        BigDecimal similarityScore,
        String reason,
        KeywordMergeSuggestionStatus status,
        String modelName,
        String modelVersion,
        String reviewedBy,
        LocalDateTime reviewedAt,
        LocalDateTime createdAt,
        LocalDateTime updatedAt
) {

    public static KeywordMergeSuggestionResponse from(KeywordMergeSuggestion suggestion) {
        return new KeywordMergeSuggestionResponse(
                suggestion.getId(),
                suggestion.getSourceKeyword(),
                suggestion.getNormalizedSourceKeyword(),
                suggestion.getTargetGroup().getId(),
                suggestion.getTargetKeyword(),
                suggestion.getSimilarityScore(),
                suggestion.getReason(),
                suggestion.getStatus(),
                suggestion.getModelName(),
                suggestion.getModelVersion(),
                suggestion.getReviewedBy(),
                suggestion.getReviewedAt(),
                suggestion.getCreatedAt(),
                suggestion.getUpdatedAt()
        );
    }
}
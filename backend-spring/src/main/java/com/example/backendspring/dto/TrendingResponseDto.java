package com.example.backendspring.dto;

import lombok.Builder;
import lombok.Getter;
import lombok.Setter;

@Getter
@Builder
public class TrendingResponseDto {
    private String id;
    private String keyword;      // 예: "LLM"
    private String category;     // 예: "AI"
    private float score;        // hotness_score (프론트의 score)
    private int mention_count;          // mention_count (프론트의 volume)
    private int rank;            // 순위
    private String changeType;   // "up", "down", "new", "same"
    private int changeValue;     // 순위 변동 폭
}

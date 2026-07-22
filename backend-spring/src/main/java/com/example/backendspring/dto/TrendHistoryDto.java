package com.example.backendspring.dto;

import lombok.AllArgsConstructor;
import lombok.Builder;
import lombok.Getter;

@Getter
@AllArgsConstructor
@Builder
public class TrendHistoryDto {
    private String day;
    private long articleCount;
    private double weightedScore;
    private boolean partial;
}

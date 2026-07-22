package com.example.backendspring.dto;

import lombok.AllArgsConstructor;
import lombok.Builder;
import lombok.Getter;

import java.util.List;

@Getter
@Builder
@AllArgsConstructor
public class TrendHistoryComparisonResponseDto {
    private String firstRequestedKeyword;
    private String secondRequestedKeyword;
    private String firstCanonicalKeyword;
    private String secondCanonicalKeyword;
    private int days;
    private String timezone;
    private boolean todayPartial;
    private List<TrendHistoryDto> firstHistory;
    private List<TrendHistoryDto> secondHistory;
}

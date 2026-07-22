package com.example.backendspring.dto;

import lombok.Builder;
import lombok.Getter;

/**
 * 24시간 기준 상승/하락 키워드 카드에 표시할 단일 키워드 요약 DTO입니다.
 */
@Getter
@Builder
public class TrendStatsKeywordDto {
    private String keyword;      // 변화량이 가장 큰 키워드명
    private long mentionCount;   // 최근 24시간 내 해당 키워드 언급량
    private long changeAmount;   // 최근 24시간 언급량 - 직전 24시간 언급량
}

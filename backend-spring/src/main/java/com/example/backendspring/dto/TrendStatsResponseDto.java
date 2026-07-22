package com.example.backendspring.dto;

import lombok.Builder;
import lombok.Getter;

/**
 * 프론트엔드 상단 통계 카드에 내려줄 최근 24시간 기준 트렌드 통계 DTO입니다.
 */
@Getter
@Builder
public class TrendStatsResponseDto {
    private long analyzedArticles;                 // 최근 24시간 내 분석된 기사 수
    private long trackedKeywords;                  // 최근 24시간 내 추적된 고유 키워드 수
    private TrendStatsKeywordDto risingKeyword;    // 직전 24시간 대비 가장 많이 증가한 키워드
    private TrendStatsKeywordDto fallingKeyword;   // 직전 24시간 대비 가장 많이 감소한 키워드
    private int windowHours;                       // 기준 시간 창. 현재는 24시간 고정
}

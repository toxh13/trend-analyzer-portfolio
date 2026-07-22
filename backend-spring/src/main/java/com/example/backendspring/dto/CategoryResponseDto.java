package com.example.backendspring.dto;

import lombok.Builder;
import lombok.Getter;

/**
 * 대시보드 카테고리 필터에 내려줄 카테고리 응답 DTO입니다.
 * 새 크롤링 카테고리가 DB에 저장되면 프론트엔드가 하드코딩 없이 이 값을 기준으로 버튼을 생성합니다.
 */
@Getter
@Builder
public class CategoryResponseDto {
    private String id;          // 프론트에서 선택 값으로 사용하는 카테고리 식별자
    private String label;       // 화면에 표시할 카테고리명
    private long trendCount;    // 현재 trend_metrics에 집계된 해당 카테고리 트렌드 개수
}

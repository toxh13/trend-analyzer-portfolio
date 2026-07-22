package com.example.backendspring.dto;

import java.time.LocalDateTime;

/**
 * 내정보 화면에서 사용자가 구독한 키워드 목록을 표시하기 위한 응답 DTO입니다.
 */
public record MySubscriptionResponse(
        Long id,
        String keyword,
        LocalDateTime createdAt
) {
}

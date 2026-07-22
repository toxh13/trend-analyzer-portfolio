package com.example.backendspring.dto;

import jakarta.validation.constraints.NotBlank;
import jakarta.validation.constraints.Size;

/**
 * 웹과 Discord Bot이 공유하는 관심 키워드 구독 생성 요청입니다.
 */
public record SubscriptionRequest(
        @NotBlank(message = "구독할 키워드를 입력해 주세요.")
        @Size(max = 100, message = "키워드는 100자 이하로 입력해 주세요.")
        String keyword
) {
}

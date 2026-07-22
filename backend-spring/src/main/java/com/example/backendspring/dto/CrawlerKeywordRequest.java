package com.example.backendspring.dto;

import com.example.backendspring.entity.CrawlerKeywordType;
import jakarta.validation.constraints.NotBlank;
import jakarta.validation.constraints.Size;

/**
 * 관리자 페이지에서 키워드를 등록/수정할 때 사용하는 요청 DTO입니다.
 */
public record CrawlerKeywordRequest(
        @NotBlank(message = "키워드는 필수입니다.")
        @Size(max = 100, message = "키워드는 100자 이하로 입력해주세요.")
        String keyword,

        @Size(max = 100, message = "카테고리는 100자 이하로 입력해주세요.")
        String category,

        Boolean active,
        Integer priority,
        Boolean notionEnabled,

        /**
         * TRACKING: 추적 키워드
         * BLOCKED : 의미 없는 차단 키워드
         */
        CrawlerKeywordType keywordType
) {
}

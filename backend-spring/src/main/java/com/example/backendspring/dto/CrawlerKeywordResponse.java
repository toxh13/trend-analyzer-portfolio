package com.example.backendspring.dto;

import com.example.backendspring.entity.CrawlerKeyword;
import com.example.backendspring.entity.CrawlerKeywordType;

import java.time.LocalDateTime;

/**
 * 관리자 페이지에 노출할 키워드 응답 DTO입니다.
 * Entity를 직접 반환하지 않고 필요한 필드만 전달하여 API 응답 구조를 안정화합니다.
 */
public record CrawlerKeywordResponse(
        Long id,
        String keyword,
        String category,
        Boolean active,
        Integer priority,
        Boolean notionEnabled,
        CrawlerKeywordType keywordType,
        LocalDateTime createdAt,
        LocalDateTime updatedAt
) {
    public static CrawlerKeywordResponse from(CrawlerKeyword entity) {
        return new CrawlerKeywordResponse(
                entity.getId(),
                entity.getKeyword(),
                entity.getCategory(),
                entity.getActive(),
                entity.getPriority(),
                entity.getNotionEnabled(),
                entity.getKeywordType(),
                entity.getCreatedAt(),
                entity.getUpdatedAt()
        );
    }
}

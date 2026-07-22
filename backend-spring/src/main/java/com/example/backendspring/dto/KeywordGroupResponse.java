package com.example.backendspring.dto;

import com.example.backendspring.entity.KeywordAlias;
import com.example.backendspring.entity.KeywordGroup;

import java.time.LocalDateTime;
import java.util.List;

/**
 * 대표 키워드 그룹 응답 DTO입니다.
 * 그룹 정보와 그 안에 묶인 alias 목록을 함께 내려줍니다.
 */
public record KeywordGroupResponse(
        Long id,
        String canonicalKeyword,
        String normalizedCanonicalKeyword,
        String description,
        Boolean active,
        List<KeywordAliasResponse> aliases,
        LocalDateTime createdAt,
        LocalDateTime updatedAt
) {

    public static KeywordGroupResponse from(
            KeywordGroup group,
            List<KeywordAlias> aliases
    ) {
        return new KeywordGroupResponse(
                group.getId(),
                group.getCanonicalKeyword(),
                group.getNormalizedCanonicalKeyword(),
                group.getDescription(),
                group.getActive(),
                aliases.stream()
                        .map(KeywordAliasResponse::from)
                        .toList(),
                group.getCreatedAt(),
                group.getUpdatedAt()
        );
    }
}